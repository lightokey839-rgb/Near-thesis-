"""Tests for models.py: YAML subset parser, scorecard logic, sensitivity arithmetic, lead-lag detection."""
import math
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
import models  # noqa: E402

YAML = '''# comment
claim: "A claim"
verdict_otherwise: "mixed"
signals:
  - id: a
    metric: m_a        # trailing comment
    bullish_if: ">= 0.25"
    bearish_if: "< 0.05"
  - id: b
    metric: m_b
    bullish_if: "> metric:m_ref"
    bearish_if: "< 1"
  - id: c
    metric: m_missing
    bullish_if: "> 1"
    bearish_if: "< 0"
'''


class FakeM:
    def __init__(self, values):
        self.out = {k: {"value": v, "kind": "FACT", "unit": ""} for k, v in values.items()}

    def put(self, key, value, unit, kind, sources, method):
        self.out[key] = {"value": value, "unit": unit, "kind": kind, "sources": sources, "method": method}


class YamlAndScorecard(unittest.TestCase):
    def test_parse(self):
        d = models.parse_thesis_yaml(YAML)
        self.assertEqual(d["claim"], "A claim")
        self.assertEqual([s["id"] for s in d["signals"]], ["a", "b", "c"])
        self.assertEqual(d["signals"][0]["metric"], "m_a")
        self.assertEqual(d["signals"][1]["bullish_if"], "> metric:m_ref")

    def test_scorecard(self):
        path = os.path.join(tempfile.mkdtemp(), "t.yaml")
        with open(path, "w") as f:
            f.write(YAML)
        m = FakeM({"m_a": 0.30, "m_b": 0.5, "m_ref": 10})
        models.scorecard(m, path)
        rows = {r["id"]: r["status"] for r in m.out["scorecard"]["value"]}
        self.assertEqual(rows, {"a": "green", "b": "red", "c": "not computed"})
        self.assertEqual(m.out["scorecard_counts"]["value"], [1, 0, 1])
        self.assertEqual(m.out["scorecard_verdict"]["value"], "mixed")

    def test_bad_condition_rejected(self):
        with self.assertRaises(ValueError):
            models._check("about 5", 1.0, {})


class Sensitivity(unittest.TestCase):
    def test_arithmetic(self):
        m = FakeM({"total_supply_near": 1000.0, "validator_stake_near": 500.0, "protocol_reward_rate": 0.0,
                   "near_price_usd": 2.0, "wallet_inflow_near_per_day": 25.0 / 365, "intents_volume_usd_per_day": 1000.0,
                   "wallet_inflow_usd_per_year": 50.0, "captured_revenue_take_bps": 5.0})
        models.sensitivity(m)
        top = m.out["sensitivity_net_supply"]["value"][0]           # 2.5% inflation -> 25 NEAR/yr issued
        self.assertAlmostEqual(top["issued_near_per_year"], 25.0)
        self.assertAlmostEqual(top["staking_yield_ceiling"], 0.05)
        self.assertAlmostEqual(top["net_supply_growth_at_1x"], 0.0)  # buyback 25 NEAR/yr offsets it exactly
        self.assertAlmostEqual(top["buyback_multiple_to_offset"], 1.0)
        be = m.out["sensitivity_break_even_volume"]["value"][0]["hypothetical 10 bps"]
        # issuance USD/day = 25 * 2 / 365; at 10 bps volume needed = that / 0.001
        self.assertAlmostEqual(be["volume_usd_per_day"], 25 * 2 / 365 / 0.001)


class LeadLag(unittest.TestCase):
    def test_finds_planted_lag_and_rejects_noise(self):
        rng = random.Random(1)
        n = 300
        x = [rng.gauss(0, 1) for _ in range(n)]
        y = [0.0, 0.0] + [0.8 * x[t - 2] + 0.6 * rng.gauss(0, 1) for t in range(2, n)]   # y follows x by 2 steps
        noise = [rng.gauss(0, 1) for _ in range(n)]
        best = max(range(-4, 5), key=lambda L: abs(models.pearson(*models.lagged(x, y, L))))
        self.assertEqual(best, 2)
        a, b = models.lagged(x, y, 2)
        lo, hi = models.block_bootstrap_ci(a, b, 5, 300, random.Random(7))
        self.assertGreater(lo, 0.5)
        a, b = models.lagged(x, noise, 2)
        lo, hi = models.block_bootstrap_ci(a, b, 5, 300, random.Random(7))
        self.assertTrue(lo < 0 < hi)

    def test_deterministic(self):
        a = [math.sin(i) for i in range(60)]
        b = [math.cos(i * 0.7) for i in range(60)]
        self.assertEqual(models.block_bootstrap_ci(a, b, 4, 200, random.Random(models.SEED)),
                         models.block_bootstrap_ci(a, b, 4, 200, random.Random(models.SEED)))

    def test_critical_r(self):
        crit, mde = models.critical_r(43)
        self.assertAlmostEqual(crit, math.tanh(1.96 / math.sqrt(40)), places=6)
        self.assertGreater(mde, crit)


if __name__ == "__main__":
    unittest.main()

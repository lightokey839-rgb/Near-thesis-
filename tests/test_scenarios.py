"""Tests for the five-year scenario model (pipeline/scenario_model.py) and its browser twin (dashboard/scenario_model.js)."""
import json
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import scenario_model as sm  # noqa: E402

START = {"volume_usd_per_day": 100e6, "take_bps": 5.0, "gross_fee_bps": 15.0, "supply_near": 1.3e9, "custody_near": 4e6,
         "price_usd": 4.0, "market_cap_usd": 5.2e9, "inflation_rate": 0.025, "realised_factor": 1.0}
CFG = {"years": 5, "hsp029_activation_years": 0.26, "hsp029_ramp_years": 2.0, "hsp029_end_rate": 0.016,
       "valuation_multiple_for_reverse": 50}


def sc(**kw):
    base = {"volume_cagr": 0.25, "take_bps_end": None, "hsp029": True, "custody_release_per_year": 0.0}
    base.update(kw)
    return base


class ScenarioModelTest(unittest.TestCase):
    def test_zero_growth_keeps_volume_and_revenue_flat(self):
        rows = sm.run(START, CFG, sc(volume_cagr=0.0))
        self.assertTrue(all(abs(r["volume_usd_per_day"] - 100e6) < 1e-6 for r in rows))
        self.assertTrue(all(abs(r["captured_usd"] - 100e6 * 365 * 5e-4) < 1e-3 for r in rows))

    def test_more_growth_more_buybacks(self):
        lo = sm.run(START, CFG, sc(volume_cagr=0.1))[-1]["buyback_share_of_issuance"]
        hi = sm.run(START, CFG, sc(volume_cagr=0.5))[-1]["buyback_share_of_issuance"]
        self.assertGreater(hi, lo)

    def test_take_rate_compression_lowers_revenue(self):
        flat = sm.run(START, CFG, sc())[-1]["captured_usd"]
        squeezed = sm.run(START, CFG, sc(take_bps_end=1.0))[-1]["captured_usd"]
        self.assertLess(squeezed, flat)
        self.assertAlmostEqual(sm.run(START, CFG, sc(take_bps_end=1.0))[-1]["take_bps"], 1.0)

    def test_hsp029_timing(self):
        self.assertEqual(sm.inflation_rate(0.2, True, 0.025, 0.016, 0.26, 2.0), 0.025)    # before activation
        self.assertAlmostEqual(sm.inflation_rate(1.26, True, 0.025, 0.016, 0.26, 2.0), 0.0205)  # halfway down the ramp
        self.assertEqual(sm.inflation_rate(4.5, True, 0.025, 0.016, 0.26, 2.0), 0.016)    # after the ramp
        self.assertEqual(sm.inflation_rate(4.5, False, 0.025, 0.016, 0.26, 2.0), 0.025)   # never activates

    def test_full_release_means_custody_does_not_shrink_float(self):
        held = sm.run(START, CFG, sc(custody_release_per_year=0.0))
        released = sm.run(START, CFG, sc(custody_release_per_year=1.0))
        self.assertGreater(released[-1]["float_growth"], held[-1]["float_growth"])
        self.assertAlmostEqual(released[-1]["custody_near"], released[-1]["bought_near"], places=6)

    def test_reverse_is_consistent_with_forward_model(self):
        rv = sm.reverse(START, CFG)
        rows = sm.run(START, CFG, sc(volume_cagr=rv["volume_cagr_needed_at_today_take"]))
        self.assertAlmostEqual(rows[-1]["buyback_share_of_issuance"], 1.0, places=6)
        self.assertGreater(rv["volume_cagr_needed_at_today_take"], rv["volume_cagr_needed_at_8_bps"])

    @unittest.skipUnless(shutil.which("node"), "Node.js not installed: browser model not checked")
    def test_browser_model_matches_python(self):
        js = os.path.join(ROOT, "dashboard", "scenario_model.js")
        cases = [sc(), sc(volume_cagr=-0.1, take_bps_end=3.0, hsp029=False, custody_release_per_year=0.25),
                 sc(volume_cagr=0.6, take_bps_end=8.0), sc(volume_cagr=0.5, take_bps_end=2.0, custody_release_per_year=0.5)]
        script = ("const M=require(process.argv[1]);const a=JSON.parse(process.argv[2]);"
                  "console.log(JSON.stringify(a.cases.map(c=>M.run(a.start,a.cfg,c))));")
        out = subprocess.run(["node", "-e", script, js, json.dumps({"start": START, "cfg": CFG, "cases": cases})],
                             capture_output=True, text=True, check=True).stdout
        for js_rows, case in zip(json.loads(out), cases):
            for a, b in zip(js_rows, sm.run(START, CFG, case)):
                for k, v in b.items():
                    self.assertAlmostEqual(a[k], v, delta=1e-9 * max(1.0, abs(v)), msg=k)


if __name__ == "__main__":
    unittest.main()

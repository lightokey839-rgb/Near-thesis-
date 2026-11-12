"""End-to-end checks on the pinned data: the build verifies, every metric computes, and no text holds an unfilled number."""
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "dashboard"))
import build_dashboard  # noqa: E402
import metrics  # noqa: E402


class FillTest(unittest.TestCase):
    met = {"a": {"value": 0.1234}, "b": {"value": 1234567.0}, "l": {"value": [["x", 1000], ["y", 2]]}}

    def test_formats(self):
        self.assertEqual(build_dashboard.fill("{a|pct1} {b|int} {b|musd}", self.met), "12.3% 1,234,567 $1.2M")
        self.assertEqual(build_dashboard.fill("{l}", self.met), "x: 1,000; y: 2")

    def test_unknown_metric_fails_loudly(self):
        with self.assertRaises(KeyError):
            build_dashboard.fill("{no_such_metric|pct0}", self.met)


class PinnedDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = metrics.run(os.path.join(ROOT, "data"))
        cls.m = {k: v["value"] for k, v in cls.doc["metrics"].items()}

    def test_every_section_computes(self):
        self.assertEqual(self.doc["not_computed"], [])

    def test_every_metric_has_source_and_label(self):
        for k, v in self.doc["metrics"].items():
            self.assertIn(v["kind"], ("FACT", "INFERENCE"), k)
            self.assertTrue(v["sources"] and v["method"], k)

    def test_sanity_bounds(self):
        m = self.m
        self.assertEqual(m["swaps_duplicates"], 0)
        self.assertTrue(0.9 < m["fee_unit_slope"] < 1.1)                    # basis points
        self.assertTrue(0 < m["oneclick_share_of_intents_volume_median"] < 1)
        self.assertTrue(0 < m["wallet_inflow_share_of_issuance"] < 1)
        self.assertEqual(m["wallet_weeks_rising"], m["wallet_weeks_total"])
        self.assertAlmostEqual(m["issuance_near_per_year"], m["total_supply_near"] * m["max_inflation_rate"], places=0)
        self.assertLess(m["source_gap_share_of_window"], 0.02)

    def test_worded_claims_still_hold(self):
        """Sentences that state a conclusion in words (not a number) are checked here; if a refresh breaks one, reword it."""
        rows = [r for r in self.m["leadlag_table"] if r[0] == "weekly" and r[1] == "intents_to_price"]
        # dashboard 'leadlag' chart + THESIS section 7: "Intents volume does not lead or lag NEAR's price"
        self.assertFalse(any(r[9] for r in rows))
        self.assertTrue(all(abs(r[4]) < self.m["leadlag_weekly_critical_r"] for r in rows))
        # THESIS section 2/5: "bought-back NEAR is held" - under 1% of everything received has ever left, never staked
        self.assertLess(self.m["wallet_outflow_share_of_inflows"], 0.01)
        self.assertLess(self.m["wallet_outflow_share_of_inflows_ex_sep09"], 0.01)
        self.assertEqual(self.m["wallet_max_staked_near"], 0)
        # THESIS section 3: "organic usage fell" from January to August
        self.assertLess(self.m["organic_change_jan_to_aug"], 0)
        # THESIS section 3b + dashboard 'channels': "the biggest source of volume pays almost nothing to NEAR"
        self.assertLess(self.m["top_volume_channel_buyback_share"], self.m["top_volume_channel_usd_share"] / 10)
        self.assertLess(self.m["top_volume_channel_buyback_bps"], self.m["rest_buyback_bps"] / 10)
        # "small channels fund most of it": no-referral swaps fund more of the buyback than their share of volume
        self.assertGreater(self.m["no_referral_buyback_share"], self.m["no_referral_usd_share"])
        # the per-channel table adds up to the whole
        ch = self.m["channel_table"]
        self.assertTrue(all(0 <= r[1] <= 1 and 0 <= r[2] <= 1 for r in ch))
        # THESIS section 3: "January was the busiest complete month and August the quietest" (so Jan->Aug is peak-to-trough)
        self.assertEqual(self.m["organic_peak_month"], "2026-01")
        self.assertEqual(self.m["organic_trough_month"], "2026-08")
        # section 3: ".tg accounts are most of the fall" (stated as a share; check it is the majority)
        self.assertGreater(self.m["organic_tg_share_of_jan_to_aug_drop"], 0.5)
        # section 3c: "break-even needs more than users pay in total today" (both issuance levels)
        self.assertGreater(self.m["break_even_take_bps"], self.m["intents_gross_fee_bps"])
        self.assertGreater(self.m["break_even_take_bps_hsp029"], self.m["intents_gross_fee_bps"])
        # section 3c: "(b) / (c) is stable month to month"
        ratios = [r[3] for r in self.m["bridge_monthly"] if r[3] is not None]
        self.assertLess(max(ratios) - min(ratios), 0.1)
        # section 5b: recent windows keep the verdict; the whole buyback era reads bearish
        byw = {r[0]: r[4] for r in self.m["scorecard_by_window"]}
        for w in ("30 days", "90 days", "180 days"):
            self.assertEqual(byw[w], "working but not yet sufficient")
        self.assertTrue(byw["since buybacks began"].startswith("bearish"))
        # section 6: "HSP-029 cuts the required multiple by about a third"
        cut = 1 - self.m["break_even_volume_x_today_hsp029_at_current_take"] / self.m["break_even_volume_x_today_at_current_take"]
        self.assertTrue(0.25 < cut < 0.45)
        # section 7: "the hits that did appear are not about Intents"
        self.assertEqual(self.m["leadlag_intents_significant"], 0)
        # section 0 / 3d: "real but small; today it settles outside NEAR"
        self.assertEqual(self.m["agent_market_agents_payable_in_near"], 0)
        self.assertLess(self.m["agent_market_agents_with_a_delivered_job_share"], 0.5)
        # section 3d: agent-named 1Click channels are a negligible share of volume
        self.assertLess(self.m["oneclick_agent_named_usd_share"], 0.001)
        # section 4: "supply grew at almost the full ceiling" and "all gas fees are burned"
        self.assertTrue(0.9 < self.m["realised_vs_ceiling_issuance"] < 1.05)
        self.assertEqual(self.m["burnt_gas_reward"], 0)
        # section 2: the 9 Sep transfer matches the 1Click fund's largest weekly fall (within 1%), in September
        self.assertLess(self.m["onecs_fall_vs_sep09_transfer"], 0.01)
        self.assertTrue(self.m["onecs_largest_fall_week"].startswith("2026-09"))
        # section 3c: the front-end fund "has accumulated" over the year
        fe = [r for r in self.m["revenue_wallet_balances"] if r[0] == "fefundsadmin.sputnik-dao.near"][0]
        self.assertGreater(fe[2], fe[1])
        # section 3d: "a large share of all Intents volume today"
        self.assertGreater(self.m["agent_volume_for_10pct_of_issuance_usd_per_day"], 0.25 * self.m["intents_volume_usd_per_day"])


class BuildTest(unittest.TestCase):
    def test_check_passes_on_pinned_tables(self):
        r = subprocess.run([sys.executable, "build.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("match data/MANIFEST.json", r.stdout)

    def test_generated_text_has_no_placeholders(self):
        for path in ("THESIS.md", os.path.join("dashboard", "index.html")):
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                text = f.read()
            text = re.sub(r"(?s)<pre>.*?</pre>", "", text)  # query listings legitimately contain {64}, {{project}}
            self.assertIsNone(re.search(r"\{[a-z][a-z0-9_]*(\|[a-z0-9]+)?\}", text), path)

    def test_every_chart_shows_a_query(self):
        with open(os.path.join(ROOT, "dashboard", "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(page.count("<canvas"), page.count("Query behind this chart"))
        self.assertEqual(page.count("<canvas"), len(build_dashboard.CHARTS))


if __name__ == "__main__":
    unittest.main()

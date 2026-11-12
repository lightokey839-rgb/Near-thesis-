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

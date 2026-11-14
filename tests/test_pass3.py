"""Checks for the 14 Nov 2026 additions: pseudonymized users, claims.json, verify.py, the explain panel, and the
sentences in THESIS.md that state a conclusion in words about the new metrics. Reads the metrics.json that
`python build.py` has just written, so it adds no slow recomputation."""
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import summarize_swaps  # noqa: E402


def load(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return json.load(f)


class PrivacyTest(unittest.TestCase):
    def test_top_users_are_pseudonymized(self):
        with open(os.path.join(ROOT, "data", "summary", "top_users.csv"), encoding="utf-8") as f:
            users = [line.split(",")[0] for line in f.read().splitlines()[1:] if line]
        self.assertEqual(len(users), 270)
        self.assertTrue(all(re.fullmatch(r"u_[0-9a-f]{16}", u) for u in users))
        self.assertEqual(len(set(users)), len(users))

    def test_pseudonym_is_stable(self):
        self.assertEqual(summarize_swaps.pseudonym("alice.near"), summarize_swaps.pseudonym("alice.near"))
        self.assertNotEqual(summarize_swaps.pseudonym("alice.near"), summarize_swaps.pseudonym("bob.near"))
        self.assertRegex(summarize_swaps.pseudonym("alice.near"), r"^u_[0-9a-f]{16}$")

    def test_no_api_keys_or_tokens_in_tracked_text(self):
        pat = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|(?i:bearer\s+[A-Za-z0-9._-]{30,})")
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for name in files:
                if name.endswith((".py", ".md", ".html", ".json", ".yml", ".yaml", ".csv", ".sql", ".js", ".example")):
                    with open(os.path.join(base, name), encoding="utf-8", errors="replace") as f:
                        self.assertIsNone(pat.search(f.read()), os.path.join(base, name))


class ClaimsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.met = load("data", "derived", "metrics.json")["metrics"]
        cls.claims = load("data", "derived", "claims.json")["claims"]

    def test_every_claim_traces_to_metrics(self):
        self.assertGreaterEqual(len(self.claims), 12)
        for c in self.claims:
            self.assertIn(c["label"], ("FACT", "INFERENCE", "OPEN"), c["id"])
            self.assertNotRegex(c["claim"], r"\{[a-z][a-z0-9_]*(\|[a-z0-9]+)?\}", c["id"])
            for m in c["metrics"]:
                self.assertIn(m["id"], self.met, c["id"])
                self.assertEqual(m["value"], self.met[m["id"]]["value"], c["id"])
            if c["label"] != "OPEN":
                self.assertTrue(c["metrics"], c["id"])

    def test_dashboard_has_the_panel_and_a_strict_policy(self):
        with open(os.path.join(ROOT, "dashboard", "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn('id="explain"', page)
        self.assertIn('id="ask"', page)
        csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
        self.assertIn("default-src 'none'", csp)
        self.assertEqual(re.search(r"connect-src ([^;]+)", csp).group(1).split(), ["https://api.anthropic.com", "https://cloud-api.near.ai"])
        self.assertNotIn("localStorage", page)
        self.assertNotIn("sessionStorage", page)

    def test_verify_script_passes(self):
        r = subprocess.run([sys.executable, "verify.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ALL PASS", r.stdout)


class WordedClaimsTest(unittest.TestCase):
    """Sentences added on 14 Nov that state a conclusion in words. If a data refresh breaks one, reword the sentence."""
    @classmethod
    def setUpClass(cls):
        cls.m = {k: v["value"] for k, v in load("data", "derived", "metrics.json")["metrics"].items()}

    def test_demand_step_up(self):
        # "all of the rise since January is one August step"
        self.assertGreater(self.m["recent_vs_jan"], 0)
        self.assertLess(self.m["before_step_vs_jan"], 0)
        self.assertGreater(self.m["stepup_after_usd_per_day"], 1.5 * self.m["stepup_before_usd_per_day"])
        # "gross fees rose faster than volume"
        self.assertGreater(self.m["stepup_after_gross_bps"], self.m["stepup_before_gross_bps"])

    def test_crosschain(self):
        # "Intents is the largest of the three on recent windows", "its lead is not secure"
        self.assertGreater(self.m["crosschain_near_intents_share_of_three"], self.m["crosschain_thorchain_share_of_three"])
        self.assertGreater(self.m["crosschain_near_intents_share_of_three"], self.m["crosschain_chainflip_share_of_three"])
        self.assertNotEqual(self.m["crosschain_latest7_leader"], "NEAR Intents")
        self.assertGreater(self.m["crosschain_alltime_thorchain_vs_intents"], 1)
        # "matches the table pinned on 11 Nov"
        self.assertAlmostEqual(self.m["crosschain_intents_vs_pinned"], 1.0, places=3)

    def test_weekly_trend(self):
        # "the 5.0 bps headline averages a falling series"; "still above the 3 bps bearish line"
        self.assertLess(self.m["trend_take_bps_latest_full_week"], self.m["captured_revenue_take_bps"])
        self.assertLess(self.m["trend_take_bps_latest_full_week"], self.m["trend_take_bps_peak_week"])
        self.assertGreater(self.m["trend_take_bps_latest_full_week"], 3)
        # "NEAR fell", "in NEAR the flow held up", "in dollars it fell"
        self.assertLess(self.m["trend_price_change"], 0)
        self.assertGreaterEqual(self.m["trend_inflow_near_latest_full_week"], 0.9 * self.m["trend_inflow_near_reference_week"])
        self.assertLess(self.m["trend_inflow_usd_change"], 0)

    def test_fee_layers_do_not_reconcile(self):
        # "1Click's app fees are X% of gross fees on Y% of the volume" is only a puzzle while X > Y
        self.assertGreater(self.m["recon_appfees_share_of_gross"], self.m["recon_oneclick_share_of_volume"])
        self.assertLess(self.m["recon_buyback_share_of_appfees"], 0.5)        # "mostly stay with integrators"
        self.assertGreater(self.m["recon_other_captured_share"], 0.5)        # "most captured revenue has no swap-level record"

    def test_confidential_switch(self):
        # "consistent with the docs: the Explorer kept reporting these swaps"
        self.assertGreater(self.m["oneclick_swaps_after_vs_before_switch"], 0.9)
        self.assertGreater(self.m["oneclick_usd_after_vs_before_switch"], 0.9)

    def test_release_sensitivity(self):
        sens = {r[0]: r for r in self.m["scenario_release_sensitivity"]}
        grid = self.m["scenario_release_grid"]
        for sid, own, cells, share in sens.values():
            # the cell at the scenario's own release rate is the published scenario result
            self.assertAlmostEqual(cells[grid.index(own)], self.m["scenario_%s_float_change_total" % sid], places=5)
            # more release never shrinks the float more
            self.assertEqual(cells, sorted(cells))
        # section 6b: "the bull case's float still shrinks at up to X release and grows at 100%"
        self.assertLess(sens["bull"][2][grid.index(0.5)], 0)
        self.assertGreater(sens["bull"][2][grid.index(1.0)], 0)
        self.assertEqual(self.m["scenario_bull_float_falls_up_to_release"], 0.5)

    def test_release_sensitivity_recomputes_from_scratch(self):
        sys.path.insert(0, os.path.join(ROOT, "pipeline"))
        import scenario_model as sm
        start, cfg = self.m["scenario_start"], self.m["scenario_config"]
        for sc in cfg["scenarios"]:
            row = [r for r in self.m["scenario_release_sensitivity"] if r[0] == sc["id"]][0]
            for rel, cell in zip(self.m["scenario_release_grid"], row[2]):
                cum = 1.0
                for y in sm.run(start, cfg, dict(sc, custody_release_per_year=rel)):
                    cum *= 1.0 + y["float_growth"]
                self.assertAlmostEqual(cum - 1.0, cell, places=9)

    def test_post_buyback_leadlag_reading(self):
        # section 7: "none shows Intents volume moving before NEAR's price"; "BTC 'leads' too, so read as noise"
        self.assertEqual(self.m["leadlag_post_buyback_intents_to_price_lead_significant"], 0)
        # "the Intents-price hits are at a lag of -3 weeks"
        hits = {r[3] for r in self.m["leadlag_table"] if r[0] == "weekly_post_buyback" and r[9] and r[3] != 0
                and r[1] in ("intents_to_price", "intents_to_price_ex_btc")}
        self.assertEqual(hits, {-3})
        # "the remaining Intents hit is Intents volume against organic signers four weeks later";
        # "BTC and NEAR's price leading each other ... in both directions"
        rows = [r for r in self.m["leadlag_table"] if r[0] == "weekly_post_buyback" and r[9] and r[3] != 0]
        self.assertEqual({(r[1], r[3]) for r in rows if r[1] == "intents_to_organic"}, {("intents_to_organic", 4)})
        btc = {r[3] for r in rows if r[1] == "btc_to_price"}
        self.assertTrue(any(l > 0 for l in btc) and any(l < 0 for l in btc))
        self.assertGreater(self.m["leadlag_post_buyback_btc_lag_significant"], 0)
        self.assertEqual(self.m["leadlag_intents_significant"], 0)

    def test_extra_gaps_are_small(self):
        # "too small to move any figure here"
        self.assertLess(self.m["extra_gap_expected_missing_share"], 0.01)


if __name__ == "__main__":
    unittest.main()

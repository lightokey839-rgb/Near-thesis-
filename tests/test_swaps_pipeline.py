"""Fixture tests for the swap pipeline: download_swaps.py against a local fake Explorer API, and summarize_swaps.py
on a small synthetic file. No network, no real token. Both scripts run as subprocesses, exactly as a user runs them."""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOWNLOAD = os.path.join(ROOT, "pipeline", "download_swaps.py")
SUMMARIZE = os.path.join(ROOT, "pipeline", "summarize_swaps.py")
TOKEN = "TEST-TOKEN-not-a-real-jwt-1234567890"


def swap(addr, ts, **kw):
    row = {"depositAddress": addr, "depositMemo": None, "createdAtTimestamp": ts, "status": "SUCCESS"}
    row.update(kw)
    return row


# pages keyed by the cursor the client sends (None = first page); newest first, like the real API
PAGES = {
    None: [swap("a1", 1_760_000_300), swap("a2", 1_760_000_200)],
    "a2": [swap("b1", 1_760_000_100), swap("b2", 1_760_000_000)],
    "b2": [],
}


class FakeExplorer(BaseHTTPRequestHandler):
    plan = {}          # cursor -> list of responses still to give before the real page: (code, body)
    seen_auth = []

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        cursor = q.get("lastDepositAddress", [None])[0]
        type(self).seen_auth.append(self.headers.get("Authorization"))
        queued = type(self).plan.get(cursor) or []
        code, body = queued.pop(0) if queued else (200, PAGES[cursor])
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "data")
        FakeExplorer.plan, FakeExplorer.seen_auth = {}, []
        self.srv = HTTPServer(("127.0.0.1", 0), FakeExplorer)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_dl(self, *extra):
        env = dict(os.environ, NEAR_INTENTS_JWT=TOKEN)
        return subprocess.run([sys.executable, DOWNLOAD, "--out", self.out, "--delay", "0", "--retry-wait", "0.01",
                               "--base-url", "http://127.0.0.1:%d" % self.srv.server_port] + list(extra),
                              cwd=self.tmp, env=env, capture_output=True, text=True, timeout=60)

    def rows(self):
        with open(os.path.join(self.out, "intents_swaps.jsonl"), encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def state(self):
        with open(os.path.join(self.out, "state.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_paginates_until_an_empty_page(self):
        r = self.run_dl()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([x["depositAddress"] for x in self.rows()], ["a1", "a2", "b1", "b2"])
        st = self.state()
        self.assertTrue(st["finished"])
        self.assertEqual(st["rows_saved"], 4)
        self.assertEqual(st["oldest_ts"], 1_760_000_000)

    def test_retries_a_server_error_and_a_non_list_body(self):
        FakeExplorer.plan = {None: [(500, {"error": "boom"})], "a2": [(200, {"error": "not a list"})]}
        r = self.run_dl()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("server error 500", r.stdout)
        self.assertIn("expected a list", r.stdout)
        self.assertEqual(len(self.rows()), 4)

    def test_repairs_a_half_written_line_on_resume(self):
        r = self.run_dl("--max-pages", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.out, "intents_swaps.jsonl"), "a", encoding="utf-8") as f:
            f.write('{"depositAddress":"half-writ')            # a crash in the middle of a line
        r = self.run_dl()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Repaired", r.stdout)
        self.assertEqual([x["depositAddress"] for x in self.rows()], ["a1", "a2", "b1", "b2"])

    def test_token_is_sent_but_never_written_or_printed(self):
        r = self.run_dl()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(FakeExplorer.seen_auth and all(a == "Bearer " + TOKEN for a in FakeExplorer.seen_auth))
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        for name in os.listdir(self.out):
            with open(os.path.join(self.out, name), "rb") as f:
                self.assertNotIn(TOKEN.encode(), f.read(), name)

    def test_rejected_token_stops_with_a_clear_message(self):
        FakeExplorer.plan = {None: [(401, {"error": "bad token"})]}
        r = self.run_dl()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("rejected the token (HTTP 401)", r.stderr)


BUYBACK = "buybacks.multisignature.near"
T = 1_791_194_400            # 2026-10-05 10:00 UTC, a Monday
FIXTURE = [
    swap("s1", T, amountInUsd="100", amountOutUsd="99", referral="appA", refundTo="alice.near",
         appFees=[{"recipient": BUYBACK, "fee": 20}], originAsset="nep141:usdc", destinationAsset="nep141:wrap.near"),
    swap("s1", T, amountInUsd="100", amountOutUsd="99", referral="appA", refundTo="alice.near"),      # duplicate
    swap("s2", T + 60, amountInUsd="50", amountOutUsd="49", senders=["bob.near"]),                    # no referral, no refundTo
    swap("s3", T + 120, status="REFUNDED", amountInUsd="10", refundTo="carol.near"),
    swap("s4", T + 180, status="FAILED", amountInUsd="10", refundTo="carol.near"),
    swap("s5", T + 240, referral="appA", refundTo="alice.near", appFees=[{"recipient": "x.near", "fee": 10}]),  # no amountInUsd
]


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.input = os.path.join(self.tmp, "swaps.jsonl")
        with open(self.input, "w", encoding="utf-8") as f:
            for row in FIXTURE:
                f.write(json.dumps(row) + "\n")
            f.write("{not json\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def summarize(self, out):
        r = subprocess.run([sys.executable, SUMMARIZE, "--input", self.input, "--out", out],
                           cwd=self.tmp, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return out

    def table(self, out, name):
        with open(os.path.join(out, "summary", name), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_counts_sums_fees_and_users(self):
        out = self.summarize(os.path.join(self.tmp, "o1"))
        with open(os.path.join(out, "summary.json"), encoding="utf-8") as f:
            s = json.load(f)
        self.assertEqual((s["unique_swaps"], s["duplicates_dropped"], s["unreadable_lines"]), (5, 1, 1))
        self.assertEqual(s["status_counts"], {"SUCCESS": 3, "REFUNDED": 1, "FAILED": 1})
        self.assertEqual(s["success_usd_in_total"], 150.0)

        day = self.table(out, "daily.csv")
        self.assertEqual(len(day), 1)
        d = day[0]
        self.assertEqual((d["day"], d["swaps_all_status"], d["swaps_success"], d["swaps_failed"], d["swaps_refunded"]),
                         ("2026-10-05", "5", "3", "1", "1"))
        self.assertEqual(float(d["usd_in_success"]), 150.0)

        refs = {(r["week_start_monday"], r["referral"]): (int(r["swaps_success"]), float(r["usd_in_success"]))
                for r in self.table(out, "referrals_weekly.csv")}
        self.assertEqual(refs, {("2026-10-05", "appA"): (2, 100.0), ("2026-10-05", "(none)"): (1, 50.0)})

        fees = {r["fee_recipient"]: r for r in self.table(out, "app_fees_weekly.csv")}
        self.assertEqual(float(fees[BUYBACK]["sum_fee_value_x_usd"]), 2000.0)                 # 20 x $100
        self.assertEqual(float(fees[BUYBACK]["est_fee_usd_if_fee_is_basis_points"]), 0.2)     # fee x usd / 1e4
        self.assertEqual(float(fees["x.near"]["est_fee_usd_if_fee_is_basis_points"]), 0.0)   # missing amountInUsd counts as 0

        h = lambda u: "u_" + hashlib.sha256(("near-thesis-engine/user/v1|" + u).encode()).hexdigest()[:16]
        users = {r["user_proxy"]: (int(r["swaps_success"]), float(r["usd_in_success"])) for r in self.table(out, "top_users.csv")}
        self.assertEqual(users, {h("alice.near"): (2, 100.0), h("bob.near"): (1, 50.0)})   # bob via senders[0]
        with open(os.path.join(out, "summary", "top_users.csv"), encoding="utf-8") as f:
            self.assertNotIn("alice.near", f.read())

    def test_two_runs_give_identical_tables(self):
        a = self.summarize(os.path.join(self.tmp, "a"))
        b = self.summarize(os.path.join(self.tmp, "b"))
        for name in sorted(os.listdir(os.path.join(a, "summary"))):
            with open(os.path.join(a, "summary", name), "rb") as fa, open(os.path.join(b, "summary", name), "rb") as fb:
                self.assertEqual(fa.read(), fb.read(), name)
        # summary.json also records the run time and the input path, so compare it without those two fields
        loaded = []
        for x in (a, b):
            with open(os.path.join(x, "summary.json"), encoding="utf-8") as f:
                loaded.append(json.load(f))
        ja, jb = loaded
        for j in (ja, jb):
            j.pop("seconds")
            j.pop("input_file")
        self.assertEqual(ja, jb)


if __name__ == "__main__":
    unittest.main()

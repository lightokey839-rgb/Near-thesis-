"""Tests check_gaps.py against a local mock of the Explorer API (no real token, no internet)."""
import json
import os
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
import check_gaps  # noqa: E402

GAP_END = 1794000000
GAP_START = GAP_END - 18000


class Mock(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        assert self.headers["Authorization"] == "Bearer test-token"
        cursor = q["lastDepositAddress"][0]
        if cursor == "skipped":     # API has rows inside the gap -> our download skipped them
            rows = [{"depositAddress": "x%d" % i, "createdAtTimestamp": GAP_END - 600 * (i + 1)} for i in range(3)]
        else:                       # API jumps over the gap too
            rows = [{"depositAddress": "y%d" % i, "createdAtTimestamp": GAP_START - 60 * (i + 1)} for i in range(3)]
        body = json.dumps(rows).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class CheckGapsTest(unittest.TestCase):
    def test_verdicts(self):
        srv = HTTPServer(("127.0.0.1", 0), Mock)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = "http://127.0.0.1:%d/api/v0" % srv.server_port
            end_iso = check_gaps.iso(GAP_END)
            gaps = [
                {"gap_seconds": "18000", "gap_ends_utc_newer_side": end_iso,
                 "resume_lastDepositAddress": "skipped", "resume_lastDepositMemo": ""},
                {"gap_seconds": "18000", "gap_ends_utc_newer_side": end_iso,
                 "resume_lastDepositAddress": "real", "resume_lastDepositMemo": ""},
            ]
            res = check_gaps.check(base, "test-token", gaps, delay=0)
            self.assertEqual(res[0][4], 3)
            self.assertIn("SKIPPED", res[0][6])
            self.assertEqual(res[1][4], 0)
            self.assertIn("real gap", res[1][6])
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()

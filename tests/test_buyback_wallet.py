"""Tests buyback_wallet.py against a local mock NEAR JSON-RPC (no internet)."""
import base64
import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.join(os.path.dirname(__file__), "..")
T0 = 1790000000            # timestamp of block 0 in the mock chain
HEAD = 3_000_000           # head height; 1 block per second
SKIPPED = {T0 % 7}         # pretend a few heights do not exist


def ts_of(h):
    return T0 + h


class Rpc(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        m, p = req["method"], req["params"]
        if m == "status":
            res = {"result": {"sync_info": {"latest_block_height": HEAD}}}
        elif m == "block":
            h = p["block_id"]
            if h % 1000 in SKIPPED or h > HEAD:
                res = {"error": {"name": "HANDLER_ERROR", "cause": {"name": "UNKNOWN_BLOCK"}}}
            else:
                res = {"result": {"header": {"height": h, "timestamp_nanosec": str(ts_of(h) * 10 ** 9)}}}
        elif m == "query" and p["request_type"] == "view_account":
            res = {"result": {"amount": str(p["block_id"] * 10 ** 24)}}   # balance = height NEAR
        elif m == "query" and p["request_type"] == "call_function":
            args = json.loads(base64.b64decode(p["args_base64"]))
            assert args == {"account_id": "buybacks.multisignature.near"}
            res = {"result": {"result": list(b'"5000000000000000000000000"')}}  # 5 wNEAR
        else:
            res = {"error": "unknown"}
        body = json.dumps(dict(jsonrpc="2.0", id="1", **res)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class BuybackWalletTest(unittest.TestCase):
    def test_daily_rows(self):
        srv = HTTPServer(("127.0.0.1", 0), Rpc)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        out = os.path.join(tempfile.mkdtemp(), "wallet.csv")
        try:
            from datetime import datetime, timezone
            start = datetime.fromtimestamp(T0 + 2 * 86400, tz=timezone.utc).strftime("%Y-%m-%d")
            end = datetime.fromtimestamp(T0 + 8 * 86400, tz=timezone.utc).strftime("%Y-%m-%d")
            r = subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "buyback_wallet.py"),
                                "--rpc", "http://127.0.0.1:%d" % srv.server_port,
                                "--start", start, "--end", end, "--step-days", "2", "--out", out],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(out, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 4)  # start, +2, +4, +6 days
            for row in rows:
                day_ts = datetime.strptime(row["day"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
                self.assertLess(abs(ts_of(int(row["block_height"])) - day_ts), 1800)
                self.assertEqual(float(row["native_near"]), float(row["block_height"]))
                self.assertEqual(float(row["wnear"]), 5.0)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()

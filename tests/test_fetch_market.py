"""Tests fetch_market.py against one local mock server standing in for DefiLlama, CoinGecko and NEAR RPC."""
import csv
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
import fetch_market as fm  # noqa: E402

D1, D2 = 1793836800, 1793923200  # 2026-11-05, 2026-11-06 UTC


class Mock(BaseHTTPRequestHandler):
    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path
        if "/summary/dexs/near-intents" in p:
            self._send({"totalDataChart": [[D1, 100], [D2, 200]], "methodologyURL": "x"})
        elif "/summary/fees/near-intents" in p:
            v = 7 if "dailyRevenue" in p else 30
            self._send({"totalDataChart": [[D1, v], [D2, v]], "methodology": {"Revenue": "test"}})
        elif "/summary/fees/" in p:
            self._send({"total30d": 1000 if "dailyFees" in p else 500})
        elif "/chart/coingecko:" in p:
            coin = p.split("coingecko:")[1].split("?")[0]
            self._send({"coins": {"coingecko:" + coin: {"prices": [{"timestamp": D1, "price": 3.5}, {"timestamp": D2, "price": 3.7}]}}})
        elif "/overview/dexs/solana" in p:
            self._send({"totalDataChart": [[D1, 1000], [D2, 2000]]})
        elif "/coins/markets" in p:
            self._send([{"id": gid, "current_price": 1.0, "market_cap": 10, "fully_diluted_valuation": 12,
                         "circulating_supply": 5, "last_updated": "t"} for _, gid, _ in fm.PEERS])
        else:
            self.send_error(404)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        m = req["method"]
        if m == "block":
            res = {"header": {"height": 5, "timestamp_nanosec": str(D2 * 10 ** 9), "total_supply": str(1000 * 10 ** 24)}}
        elif m == "validators":
            res = {"current_validators": [{"stake": str(300 * 10 ** 24)}, {"stake": str(100 * 10 ** 24)}]}
        else:
            res = {"max_inflation_rate": [1, 40], "protocol_reward_rate": [0, 1], "protocol_version": 88, "epoch_length": 43200}
        self._send({"jsonrpc": "2.0", "id": "1", "result": res})

    def log_message(self, *a):
        pass


class FetchMarketTest(unittest.TestCase):
    def test_run(self):
        srv = HTTPServer(("127.0.0.1", 0), Mock)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % srv.server_port
        out = tempfile.mkdtemp()
        try:
            fm.run(out, "2026-11-01", llama=base, coins=base, gecko=base, rpc=base)
        finally:
            srv.shutdown()
            srv.server_close()
        with open(os.path.join(out, "defillama_intents_daily.csv")) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["day"] for r in rows], ["2026-11-05", "2026-11-06"])
        self.assertEqual(rows[1]["intents_volume_usd"], "200")
        self.assertEqual(rows[0]["near_captured_revenue_usd"], "7")
        with open(os.path.join(out, "near_chain_snapshot.json")) as f:
            snap = json.load(f)
        self.assertEqual(snap["total_supply_near"], 1000)
        self.assertEqual(snap["current_validator_stake_near"], 400)
        self.assertEqual(snap["staked_share_of_supply"], 0.4)
        self.assertEqual(snap["max_inflation_rate"], 0.025)
        with open(os.path.join(out, "peers.csv")) as f:
            peers = list(csv.DictReader(f))
        self.assertEqual(len(peers), len(fm.PEERS))
        self.assertEqual(peers[0]["chain_fees_30d_usd"], "1000")
        self.assertTrue(os.path.exists(os.path.join(out, "_fetched.json")))
        with open(os.path.join(out, "placebo_daily.csv")) as f:
            plc = list(csv.DictReader(f))
        self.assertEqual(plc[1], {"day": "2026-11-06", "btc_usd": "3.7", "solana_dex_volume_usd": "2000"})


if __name__ == "__main__":
    unittest.main()

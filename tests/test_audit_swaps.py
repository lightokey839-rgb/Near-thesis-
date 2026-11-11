"""Tests for pipeline/audit_swaps.py on a small synthetic file (no network, no real data)."""
import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
import audit_swaps  # noqa: E402

BASE_TS = 1794182400  # 2026-11-09 00:00 UTC
SPIKE_TS = 1793836800  # 2026-11-05 00:00 UTC


def swap(i, ts, status="SUCCESS", usd_in=100.0, out_tokens=None, fees=None, referral="lifi",
         reason=None, refund_to=None):
    in_tokens = usd_in
    if out_tokens is None:
        total = sum(f["fee"] for f in (fees or []))
        out_tokens = in_tokens * (1 - total / 10000.0)  # fee in basis points, no spread
    return {
        "depositAddress": "addr%d" % i, "depositMemo": None, "createdAtTimestamp": ts,
        "status": status, "referral": referral,
        "originAsset": "nep141:usdc", "destinationAsset": "nep141:usdt",
        "amountInFormatted": str(in_tokens), "amountOutFormatted": str(out_tokens),
        "amountInUsd": str(usd_in), "amountOutUsd": str(out_tokens),
        "appFees": fees or [], "refundReason": reason, "refundTo": refund_to or "user%d" % (i % 7),
        "depositType": "ORIGIN_CHAIN", "refundType": "ORIGIN_CHAIN",
    }


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.inp = os.path.join(self.tmp, "swaps.jsonl")
        rows = []
        i = 0
        # 60 stable swaps with a 20 bps buyback fee, 60 with 1 bp, newest first
        for k in range(120):
            fee = 20 if k % 2 == 0 else 1
            rows.append(swap(i, BASE_TS + 3600 * 10 - k * 60,
                             fees=[{"recipient": audit_swaps.BUYBACK, "fee": fee}]))
            i += 1
        # spike-day refunds, 40 from one address
        for k in range(50):
            rows.append(swap(i, SPIKE_TS + 3600 - k, status="REFUNDED", usd_in=0.01,
                             reason="NO_LIQUIDITY", refund_to="bot" if k < 40 else None))
            i += 1
        with open(self.inp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.write(json.dumps(rows[0]) + "\n")  # a duplicate
            f.write("{broken\n")                   # an unreadable line

    def test_audit(self):
        out = os.path.join(self.tmp, "audit")
        a = audit_swaps.run(self.inp, out)
        self.assertEqual(a["duplicates"], 1)
        self.assertEqual(a["unreadable"], 1)
        self.assertEqual(a["success_swaps"], 120)
        self.assertEqual(a["success_share_paying_buyback"], 1.0)
        self.assertEqual(a["rows_out_of_time_order"], 0)
        fees = {r["fee"]: r for r in a["fee_unit_test"]}
        self.assertAlmostEqual(fees[20.0]["median"], 20.0, places=1)
        self.assertAlmostEqual(fees[1.0]["median"], 1.0, places=1)
        c = a["refund_spike_concentration"]["2026-11-05"]
        self.assertEqual(c["refunded"], 50)
        self.assertEqual(c["top1_share"], 0.8)
        with open(os.path.join(out, "refunds_by_day_reason.csv"), encoding="utf-8") as f:
            rows = {r["day"]: r for r in csv.DictReader(f)}
        self.assertEqual(rows["2026-11-05"]["reason_NO_LIQUIDITY"], "50")
        self.assertEqual(rows["2026-11-05"]["refund_rate"], "1.0")
        for name in ("price_ratio_bins.csv", "largest_swaps.csv", "buyback_usd_est_by_day_if_bps.csv"):
            self.assertTrue(os.path.exists(os.path.join(out, name)), name)


if __name__ == "__main__":
    unittest.main()

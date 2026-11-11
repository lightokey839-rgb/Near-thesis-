#!/usr/bin/env python3
"""
buyback_wallet.py - daily NEAR balance of the buyback wallet, read from the
public NEAR archival RPC (no key needed).

Why: if the wallet's balance keeps growing, bought-back NEAR is being HELD.
If it stays flat while buys happen, it is being moved on (or burned). The
daily change is also a rough check on the buyback inflow we estimate from swaps.

Writes data/onchain/buyback_wallet_daily.csv
    day, block_height, block_time_utc, native_near, wnear

Standard library only. About 2 RPC calls per day sampled; it waits a little
between calls to be polite to the free endpoint.

Usage:
    python pipeline/buyback_wallet.py                       # 1 Sep 2026 -> today
    python pipeline/buyback_wallet.py --start 2026-02-01 --account buybacks.multisignature.near
"""

import argparse
import base64
import csv
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_RPC = "https://archival-rpc.mainnet.fastnear.com"
YOCTO = 10 ** 24
USER_AGENT = "near-thesis-engine/0.1"


class Rpc:
    def __init__(self, url, pause=1.0):
        self.url, self.pause = url, pause

    def call(self, method, params, attempts=7):
        body = json.dumps({"jsonrpc": "2.0", "id": "1", "method": method, "params": params}).encode()
        for i in range(attempts):
            try:
                req = urllib.request.Request(self.url, data=body, headers={
                    "Content-Type": "application/json", "User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=60) as r:
                    out = json.load(r)
                time.sleep(self.pause)
                return out
            except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
                wait = 15 * (i + 1)  # free endpoints rate-limit (HTTP 429): back off generously
                print("  rpc problem (%s), retry in %ds" % (e, wait))
                time.sleep(wait)
        raise SystemExit("RPC kept failing. Run again later.")


def block_at(rpc, height):
    """Header of the first existing block at or after `height` (some heights are skipped)."""
    for h in range(height, height + 20):
        r = rpc.call("block", {"block_id": h})
        if "result" in r:
            hd = r["result"]["header"]
            return hd["height"], int(hd["timestamp_nanosec"]) / 1e9
    raise SystemExit("No block found near height %d" % height)


def find_block(rpc, target_ts, ref_h, ref_ts, rate):
    """Block within ~30 minutes of target_ts: estimate from a nearby known block, refine if needed."""
    h = int(ref_h - (ref_ts - target_ts) / rate)
    for _ in range(3):
        h, ts = block_at(rpc, h)
        diff = ts - target_ts
        if abs(diff) < 1800:
            return h, ts
        h = int(h - diff / rate)
    return h, ts


def balances(rpc, account, height):
    r = rpc.call("query", {"request_type": "view_account", "block_id": height, "account_id": account})
    native = int(r["result"]["amount"]) / YOCTO if "result" in r else None
    args = base64.b64encode(json.dumps({"account_id": account}).encode()).decode()
    r = rpc.call("query", {"request_type": "call_function", "block_id": height, "account_id": "wrap.near",
                           "method_name": "ft_balance_of", "args_base64": args})
    wnear = None
    if "result" in r and "result" in r["result"]:
        wnear = int(json.loads(bytes(r["result"]["result"]).decode())) / YOCTO
    return native, wnear


def main():
    ap = argparse.ArgumentParser(description="Daily balance of the NEAR buyback wallet.")
    ap.add_argument("--account", default="buybacks.multisignature.near")
    ap.add_argument("--start", default="2026-09-01", help="first day, YYYY-MM-DD (UTC)")
    ap.add_argument("--end", help="last day, YYYY-MM-DD (default: today)")
    ap.add_argument("--step-days", type=int, default=1, help="sample every N days (fewer RPC calls)")
    ap.add_argument("--rpc", default=DEFAULT_RPC)
    ap.add_argument("--out", default=os.path.join("data", "onchain", "buyback_wallet_daily.csv"))
    args = ap.parse_args()

    rpc = Rpc(args.rpc)
    st = rpc.call("status", [])["result"]["sync_info"]
    head_h = st["latest_block_height"]
    head_h, head_ts = block_at(rpc, head_h - 5)
    old_h, old_ts = block_at(rpc, head_h - 500000)
    rate = (head_ts - old_ts) / (head_h - old_h)  # seconds per block
    print("Head block %d, %.3f s per block" % (head_h, rate))

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = (datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.end
           else datetime.fromtimestamp(head_ts, tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    n = 0
    ref_h, ref_ts = head_h, head_ts
    d = start
    with open(args.out, "w", newline="", encoding="utf-8") as f:  # rows are saved as they arrive
        w = csv.writer(f)
        w.writerow(["day", "block_height", "block_time_utc", "native_near", "wnear"])
        while d <= end:
            h, ts = find_block(rpc, d.timestamp(), ref_h, ref_ts, rate)
            ref_h, ref_ts = h, ts  # next estimate starts from here, so usually one call is enough
            native, wnear = balances(rpc, args.account, h)
            row = [d.strftime("%Y-%m-%d"), h, datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds"),
                   None if native is None else round(native, 4), None if wnear is None else round(wnear, 4)]
            w.writerow(row)
            f.flush()
            n += 1
            print("  %s  block %d  native %s  wNEAR %s" % (row[0], h, row[3], row[4]))
            d += timedelta(days=args.step_days)
    print("Wrote %s (%d rows)" % (args.out, n))


if __name__ == "__main__":
    main()

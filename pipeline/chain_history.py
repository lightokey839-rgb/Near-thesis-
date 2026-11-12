#!/usr/bin/env python3
"""
chain_history.py - weekly on-chain samples for the accrual stage of the thesis, from the public
NEAR archival RPC (no key needed, read-only).

Why:
  * Realised supply growth. The thesis uses the protocol's MAXIMUM issuance (supply x inflation
    ceiling). The block header's total_supply shows what actually happened: new NEAR minted minus
    NEAR burned (gas), over a year.
  * All three revenue wallets. DefiLlama's "captured revenue" counts NEAR swept into
    buybacks.multisignature.near, fefundsadmin.sputnik-dao.near (front-end fund) and
    1csfundsadmin.sputnik-dao.near (1Click fund). The repo already tracks the first; this samples all three.
  * The live fee-burn parameter. runtime_config.transaction_costs.burnt_gas_reward is the share of
    burnt gas paid to contracts (the developer rebate); 0 means all gas fees are burned.

Writes
  data/onchain/chain_history.csv     week_day, block_height, block_time_utc, total_supply_near, <one column per wallet>
  data/onchain/protocol_config.json  the protocol parameters above, with the block they were read at

Standard library only. About 5 RPC calls per weekly sample with a pause between calls
(roughly 5-10 minutes for a year). Rows are saved as they arrive.

Usage:
    python pipeline/chain_history.py                      # 12 Nov 2025 -> today, weekly
    python pipeline/chain_history.py --start 2025-11-12 --step-days 7
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buyback_wallet import DEFAULT_RPC, YOCTO, Rpc, block_at, find_block  # noqa: E402  (same polite RPC client)

WALLETS = ["buybacks.multisignature.near", "fefundsadmin.sputnik-dao.near", "1csfundsadmin.sputnik-dao.near"]


def native_balance(rpc, account, height):
    r = rpc.call("query", {"request_type": "view_account", "block_id": height, "account_id": account})
    return round(int(r["result"]["amount"]) / YOCTO, 4) if "result" in r else None  # None = account did not exist yet


def total_supply(rpc, height):
    r = rpc.call("block", {"block_id": height})
    return round(int(r["result"]["header"]["total_supply"]) / YOCTO, 0)


def protocol_config(rpc):
    cfg = rpc.call("EXPERIMENTAL_protocol_config", {"finality": "final"})["result"]
    hdr = rpc.call("block", {"finality": "final"})["result"]["header"]
    tc = (cfg.get("runtime_config") or {}).get("transaction_costs") or {}
    frac = lambda v: (v[0] / v[1]) if isinstance(v, list) and len(v) == 2 and v[1] else v
    return {
        "read_at_block_height": hdr["height"],
        "read_at_utc": datetime.fromtimestamp(int(hdr["timestamp_nanosec"]) / 1e9, tz=timezone.utc).isoformat(timespec="seconds"),
        "protocol_version": cfg.get("protocol_version"),
        "max_inflation_rate": frac(cfg.get("max_inflation_rate")),
        "protocol_reward_rate": frac(cfg.get("protocol_reward_rate")),
        "burnt_gas_reward": frac(tc.get("burnt_gas_reward")),
        "raw": {"max_inflation_rate": cfg.get("max_inflation_rate"), "protocol_reward_rate": cfg.get("protocol_reward_rate"),
                "burnt_gas_reward": tc.get("burnt_gas_reward"), "epoch_length": cfg.get("epoch_length")},
    }


def main():
    ap = argparse.ArgumentParser(description="Weekly supply and revenue-wallet balances from the NEAR archival RPC.")
    ap.add_argument("--start", default="2025-11-12", help="first day, YYYY-MM-DD (UTC)")
    ap.add_argument("--end", help="last day, YYYY-MM-DD (default: today)")
    ap.add_argument("--step-days", type=int, default=7)
    ap.add_argument("--rpc", default=DEFAULT_RPC)
    ap.add_argument("--out-dir", default=os.path.join("data", "onchain"))
    args = ap.parse_args()

    rpc = Rpc(args.rpc)
    os.makedirs(args.out_dir, exist_ok=True)
    cfg = protocol_config(rpc)
    with open(os.path.join(args.out_dir, "protocol_config.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
    print("protocol config at block %d: max inflation %s, treasury cut %s, burnt_gas_reward %s"
          % (cfg["read_at_block_height"], cfg["max_inflation_rate"], cfg["protocol_reward_rate"], cfg["burnt_gas_reward"]))

    st = rpc.call("status", [])["result"]["sync_info"]
    head_h, head_ts = block_at(rpc, st["latest_block_height"] - 5)
    old_h, old_ts = block_at(rpc, head_h - 500000)
    rate = (head_ts - old_ts) / (head_h - old_h)
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = (datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.end
           else datetime.fromtimestamp(head_ts, tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
    path = os.path.join(args.out_dir, "chain_history.csv")
    ref_h, ref_ts, n = head_h, head_ts, 0
    d = start
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["week_day", "block_height", "block_time_utc", "total_supply_near"] + WALLETS)
        while d <= end:
            h, ts = find_block(rpc, d.timestamp(), ref_h, ref_ts, rate)
            ref_h, ref_ts = h, ts
            row = [d.strftime("%Y-%m-%d"), h, datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds"),
                   total_supply(rpc, h)] + [native_balance(rpc, a, h) for a in WALLETS]
            w.writerow(row)
            f.flush()
            n += 1
            print("  %s  block %d  supply %s  wallets %s" % (row[0], h, row[3], row[4:]))
            d += timedelta(days=args.step_days)
    print("Wrote %s (%d rows) and protocol_config.json" % (path, n))


if __name__ == "__main__":
    main()

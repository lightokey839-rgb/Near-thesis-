#!/usr/bin/env python3
"""
fetch_crosschain.py - daily swap volume of NEAR Intents and two other native cross-chain swap venues (no keys needed).

Writes two small, dated snapshot files to data/market/ and touches nothing else there:
  crosschain_peers_daily.csv    day, NEAR Intents, THORChain and Chainflip volume in USD (DefiLlama DEX-volume adapters)
  _fetched_crosschain.json      when each series was read, from which URL, and DefiLlama's all-time total for each

Why a separate script: `fetch_market.py` re-reads every market table, which would move every number in the thesis.
This one only adds the comparison table, so the tables pinned on 11 Nov 2026 stay byte-identical.

The three adapters are written by different people and count volume their own way, so the shares computed from this
table are shares of THESE THREE venues only. They are not "the cross-chain market".

Source and terms:  DefiLlama  https://api.llama.fi  (free public API)
Standard library only.   Usage:  python pipeline/fetch_crosschain.py [--since 2026-01-01], then python build.py --repin
"""

import argparse
import json
import os
from datetime import datetime, timezone

from fetch_market import LLAMA, chart, get_json, write_csv

VENUES = [  # (column, label, DefiLlama protocol slug)
    ("near_intents_usd", "NEAR Intents", "near-intents"),
    ("thorchain_usd", "THORChain", "thorchain-dex"),
    ("chainflip_usd", "Chainflip", "chainflip"),
]


def run(out, since, llama=LLAMA):
    os.makedirs(out, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    series, log = {}, {"fetched_utc": now, "venues": {}}
    for col, label, slug in VENUES:
        url = "%s/summary/dexs/%s?dataType=dailyVolume" % (llama, slug)
        payload = get_json(url)
        series[col] = chart(payload)
        log["venues"][col] = {"label": label, "source": url, "all_time_usd": payload.get("totalAllTime"),
                              "first_day": min(series[col]) if series[col] else None, "days": len(series[col])}
        print("%s: %d days" % (label, len(series[col])))
    days = sorted(d for d in set().union(*[set(s) for s in series.values()]) if d >= since)
    rows = [[d] + [series[col].get(d, "") for col, _, _ in VENUES] for d in days]
    write_csv(os.path.join(out, "crosschain_peers_daily.csv"), ["day"] + [col for col, _, _ in VENUES], rows)
    log["rows"] = len(rows)
    log["note"] = ("DefiLlama DEX-volume adapters; each protocol's adapter counts volume its own way, so compare levels with care. "
                   "The newest 1-2 days are often revised.")
    with open(os.path.join(out, "_fetched_crosschain.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(log, f, indent=2)
    return log


def main():
    ap = argparse.ArgumentParser(description="Fetch daily volume for NEAR Intents, THORChain and Chainflip.")
    ap.add_argument("--out", default=os.path.join("data", "market"))
    ap.add_argument("--since", default="2026-01-01")
    args = ap.parse_args()
    run(args.out, args.since)


if __name__ == "__main__":
    main()

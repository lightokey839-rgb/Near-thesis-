#!/usr/bin/env python3
"""
verify.py - recompute the thesis's headline numbers straight from the pinned CSVs and compare them with
data/derived/metrics.json. Prints PASS or FAIL per number. No network, no keys, standard library only.

This code is written separately from pipeline/metrics.py on purpose: it re-derives each number from its stated
definition, so a bug in the main pipeline would show up here as a FAIL.

    python verify.py          # exit code 0 only if every check passes
"""

import csv
import hashlib
import json
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
EXCLUDED_1CLICK_DAYS = {"2026-09-28", "2026-11-10", "2026-10-01", "2026-10-20", "2026-11-02"}  # partial first/last day, API gaps


def rows(*p):
    with open(os.path.join(DATA, *p), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    # 0. the inputs are the ones that were analysed
    with open(os.path.join(DATA, "MANIFEST.json"), encoding="utf-8") as f:
        manifest = json.load(f)["files"]
    bad = [p for p, h in manifest.items() if hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() != h]
    print("%-52s %s" % ("pinned tables match data/MANIFEST.json (%d)" % len(manifest), "PASS" if not bad else "FAIL " + ", ".join(bad)))

    with open(os.path.join(DATA, "derived", "metrics.json"), encoding="utf-8") as f:
        met = {k: v["value"] for k, v in json.load(f)["metrics"].items()}

    # 1-3. DefiLlama: 30 complete days ending 2 days before the newest day that has both volume and revenue
    ll = [r for r in rows("market", "defillama_intents_daily.csv")
          if num(r["intents_volume_usd"]) and num(r["near_captured_revenue_usd"])]
    end = date.fromisoformat(ll[-1]["day"]) - timedelta(days=2)
    win = [r for r in ll if end - timedelta(days=29) <= date.fromisoformat(r["day"]) <= end]
    vol = sum(num(r["intents_volume_usd"]) for r in win)
    rev = sum(num(r["near_captured_revenue_usd"]) for r in win)
    fees = sum(num(r["intents_gross_fees_usd"]) or 0 for r in win)

    # 4. 1Click: mean SUCCESS USD over clean full days
    oc = [num(r["usd_in_success"]) for r in rows("summary", "daily.csv") if r["day"] not in EXCLUDED_1CLICK_DAYS]

    # 5. buyback wallet: mean daily NEAR inflow 6 Oct - 8 Nov x 365 / (supply x max inflation)
    q30 = [num(r["inflow_near"]) for r in rows("bq", "q30_buyback_balance_daily.csv") if "2026-10-06" <= r["block_date"] <= "2026-11-08"]
    with open(os.path.join(DATA, "market", "near_chain_snapshot.json"), encoding="utf-8") as f:
        snap = json.load(f)
    issuance = snap["total_supply_near"] * snap["max_inflation_rate"]

    # 6. valuation: market cap / annualised captured revenue
    mcap = num([r for r in rows("market", "peers.csv") if r["chain"] == "NEAR"][0]["market_cap_usd"])

    checks = [
        ("intents_volume_usd_per_day", vol / len(win), "All-Intents volume, USD/day, %s to %s" % (win[0]["day"], win[-1]["day"])),
        ("captured_revenue_take_bps", rev / vol * 1e4, "NEAR's captured take-rate, bps"),
        ("captured_share_of_gross_fees", rev / fees, "captured revenue / gross fees"),
        ("oneclick_usd_per_day", sum(oc) / len(oc), "1Click SUCCESS volume, USD/day (%d clean days)" % len(oc)),
        ("wallet_inflow_share_of_issuance", sum(q30) / len(q30) * 365 / issuance, "buyback inflow / NEAR issued per year"),
        ("market_cap_to_captured_revenue", mcap / (rev / len(win) * 365), "market cap / captured revenue (x)"),
    ]
    failed = bool(bad)
    for key, mine, label in checks:
        ok = abs(mine - met[key]) <= 1e-6 * max(1.0, abs(mine))
        failed |= not ok
        print("%-52s %s  recomputed %.6g, metrics.json %.6g  (%s)" % (label, "PASS" if ok else "FAIL", mine, met[key], key))
    print("\nALL PASS" if not failed else "\nSOME CHECKS FAILED")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
agent_market.py - snapshot of NEAR AI Agent Market's public data (no key needed, read-only).

Why: the thesis asks whether AI agents could become a source of demand for NEAR. Agent Market
(market.near.ai) is NEAR AI's marketplace for hiring agents. It publishes an official agent catalogue and
platform totals without login, so agent activity can be measured from an identified source
(evidence tier 1: the operator's own registry) instead of guessing from "bot-like" addresses.

Writes
  data/agents/agent_market_agents.csv   one row per listed agent: id, handle, category, runtime,
                                        listing status, delivered jobs, success rate, accepted currencies, created day
  data/agents/agent_market_stats.json   platform totals from /v1/platform/stats, with the fetch time

Only public, aggregate fields are kept (no owner account ids, no descriptions).
Standard library only. About 20 requests, with a short pause between them.

Usage:
    python pipeline/agent_market.py
"""

import argparse
import csv
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

BASE = "https://market.near.ai"
USER_AGENT = "near-thesis-engine/0.1"
PAGE = 50


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    time.sleep(0.5)
    return out


def main():
    ap = argparse.ArgumentParser(description="Snapshot of NEAR AI Agent Market's public catalogue and totals.")
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--out-dir", default=os.path.join("data", "agents"))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")

    stats = get(args.base + "/v1/platform/stats")
    agents, offset = [], 0
    while True:
        page = get("%s/v1/agents?limit=%d&offset=%d&sort=delivered" % (args.base, PAGE, offset)).get("agents") or []
        agents += page
        offset += len(page)
        print("  %d agents read" % len(agents))
        if len(page) < PAGE or offset > 20000:
            break
    seen, rows = set(), []
    for a in agents:
        if a.get("agent_id") in seen:
            continue
        seen.add(a.get("agent_id"))
        rows.append([a.get("agent_id"), a.get("handle"), a.get("category"), a.get("runtime"), a.get("listing_status"),
                     int(a.get("delivered_jobs") or 0), a.get("success_rate"), "+".join(sorted(a.get("payable_with") or [])),
                     (a.get("created_at") or "")[:10]])
    rows.sort(key=lambda r: (-r[5], r[8], r[0]))   # stable order: most delivered first
    with open(os.path.join(args.out_dir, "agent_market_agents.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["agent_id", "handle", "category", "runtime", "listing_status", "delivered_jobs", "success_rate",
                    "payable_with", "created_day"])
        w.writerows(rows)
    with open(os.path.join(args.out_dir, "agent_market_stats.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"fetched_utc": fetched, "source": args.base + "/v1/platform/stats", "stats": stats,
                   "catalogue_source": args.base + "/v1/agents (public, paginated)", "catalogue_agents": len(rows)},
                  f, indent=2, sort_keys=True)
    print("Wrote %d agents and platform stats %s to %s" % (len(rows), stats, args.out_dir))


if __name__ == "__main__":
    main()

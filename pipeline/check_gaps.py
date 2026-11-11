#!/usr/bin/env python3
"""
check_gaps.py - are the multi-hour holes in our swap file real, or did the
download skip pages?

How: for each big gap, ask the API for ONE page starting right after the last
swap we have before the gap (same cursor the downloader used). If the API now
returns swaps whose time falls INSIDE the gap, our download skipped them.
If it jumps straight over the gap again, the hole is in the API's data too
(an outage or an indexing gap), and we disclose it rather than "fix" it.

Uses the same token setup as download_swaps.py (env var NEAR_INTENTS_JWT or
.env). The token is never printed. Makes one request per gap, 5.5 s apart.

Input : data/audit/integrity_gap_cursors.csv  (written by pipeline/audit_swaps.py)
Output: data/audit/gap_check.csv   (small, safe to share)

Usage (from the near-thesis folder):
    python pipeline/check_gaps.py            # checks gaps of 2 hours or more
    python pipeline/check_gaps.py --min-gap 3600
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # download_swaps.py lives next to this file
import download_swaps as dl  # noqa: E402


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def check(base_url, token, gaps, delay, page_size=20):
    results = []
    for i, g in enumerate(gaps):
        if i:
            time.sleep(delay)
        params = {"numberOfTransactions": page_size, "direction": "next",
                  "lastDepositAddress": g["resume_lastDepositAddress"]}
        if g.get("resume_lastDepositMemo"):
            params["lastDepositMemo"] = g["resume_lastDepositMemo"]
        rows = dl.fetch_page(base_url, token, params, retry_wait=10.0)
        gap_end = datetime.fromisoformat(g["gap_ends_utc_newer_side"]).timestamp()
        gap_start = gap_end - int(g["gap_seconds"])
        stamps = [int(r["createdAtTimestamp"]) for r in rows if "createdAtTimestamp" in r]
        inside = [t for t in stamps if gap_start < t < gap_end]
        verdict = ("DOWNLOAD SKIPPED ROWS - re-download this window" if inside
                   else "API ALSO HAS NO ROWS HERE - real gap, disclose it" if stamps
                   else "API returned nothing - inconclusive")
        results.append([g["gap_seconds"], iso(gap_start), iso(gap_end), len(stamps), len(inside),
                        iso(stamps[0]) if stamps else "", verdict])
        print("gap %s s ending %s -> %d rows, %d inside the gap: %s"
              % (g["gap_seconds"], iso(gap_end), len(stamps), len(inside), verdict))
    return results


def main():
    ap = argparse.ArgumentParser(description="Check whether gaps in the swap file are real.")
    ap.add_argument("--gaps", default=os.path.join("data", "audit", "integrity_gap_cursors.csv"))
    ap.add_argument("--out", default=os.path.join("data", "audit", "gap_check.csv"))
    ap.add_argument("--min-gap", type=int, default=7200, help="only check gaps at least this many seconds")
    ap.add_argument("--delay", type=float, default=5.5)
    ap.add_argument("--base-url", default=dl.DEFAULT_BASE_URL, help=argparse.SUPPRESS)
    args = ap.parse_args()

    if not os.path.exists(args.gaps):
        sys.exit("Cannot find %s. Run  python pipeline/audit_swaps.py  first." % args.gaps)
    with open(args.gaps, encoding="utf-8") as f:
        gaps = [g for g in csv.DictReader(f) if int(g["gap_seconds"]) >= args.min_gap]
    if not gaps:
        print("No gaps of %d s or more. Nothing to check." % args.min_gap)
        return
    token = dl.get_token()
    results = check(args.base_url, token, gaps, args.delay)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gap_seconds", "gap_start_utc", "gap_end_utc", "rows_returned",
                    "rows_inside_gap", "first_row_utc", "verdict"])
        w.writerows(results)
    print("Wrote %s" % args.out)


if __name__ == "__main__":
    main()

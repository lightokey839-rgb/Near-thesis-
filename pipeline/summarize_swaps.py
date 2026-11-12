#!/usr/bin/env python3
"""
summarize_swaps.py - boil the big swap file down to a few small tables.

Reads   data/intents_swaps.jsonl   (one swap per line, as downloaded)
Writes  data/summary/*.csv  and  data/summary.json,  then zips them into
        data/summary.zip   <- this small file is what you upload.

Needs only Python 3.8+ (standard library). Reads the file line by line, so a
multi-gigabyte file is fine. Expect a few minutes and a few hundred MB of RAM
per million swaps.

Definitions (also written into summary.json):
* A "day" is a UTC calendar day from createdAtTimestamp.
* Volume and user numbers use only swaps with status SUCCESS.
* "user" = the swap's refundTo address (falling back to the first sender).
  It is a PROXY for a person: one person can have many addresses.
* Duplicates (same depositAddress + depositMemo) and unreadable lines are
  dropped and counted.
* appFees "fee" units are not stated in the API docs. We store fee x USD sums;
  the est_fee_usd_if_bps column assumes basis points and may be wrong.
* Retention cohorts start at the first day a user appears IN THIS FILE, so
  people active before the file starts look "new" on the first days.

Usage:
    python pipeline/summarize_swaps.py
    python pipeline/summarize_swaps.py --input data/intents_swaps.jsonl --out data
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

DAY_BASE = 19000  # offset so a user's active days fit in a small bitmask
BUCKETS = [(1, "lt_1"), (10, "1_10"), (100, "10_100"), (1000, "100_1k"),
           (10000, "1k_10k"), (float("inf"), "gte_10k")]
BUCKET_NAMES = [name for _, name in BUCKETS]
STATUSES = ("SUCCESS", "FAILED", "REFUNDED", "PROCESSING")

_day_cache, _week_cache = {}, {}


def day_of(ts):
    n = ts // 86400
    s = _day_cache.get(n)
    if s is None:
        s = datetime.fromtimestamp(n * 86400, tz=timezone.utc).strftime("%Y-%m-%d")
        _day_cache[n] = s
    return s


def week_of(day_str):
    w = _week_cache.get(day_str)
    if w is None:
        d = date.fromisoformat(day_str)
        w = (d - timedelta(days=d.weekday())).isoformat()  # Monday
        _week_cache[day_str] = w
    return w


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def bucket(usd):
    for limit, name in BUCKETS:
        if usd < limit:
            return name
    return BUCKETS[-1][1]


def chain_guess(asset):
    """Rough chain label from an asset id. A heuristic, kept next to the raw id."""
    a = asset or ""
    if a.startswith("nep141:"):
        body = a[7:]
        if body.endswith(".omft.near"):
            return body.split("-", 1)[0].split(".")[0]
        if body.endswith(".near") or re.fullmatch(r"[0-9a-f]{64}", body):
            return "near"
        return "other"
    if a.startswith("nep245:"):
        return "nep245"
    return "unknown"


def user_of(row):
    u = row.get("refundTo")
    if u:
        return u
    senders = row.get("senders") or []
    return senders[0] if senders else None


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Summarize the downloaded swaps.")
    ap.add_argument("--input", default=os.path.join("data", "intents_swaps.jsonl"))
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        folder = os.path.dirname(args.input) or "."
        listing = ", ".join(os.listdir(folder)) if os.path.isdir(folder) else "(folder missing)"
        sys.exit("Cannot find %s\nFiles in %s: %s\nRun this from the near-thesis folder, "
                 "or use --input to point at your file." % (args.input, folder, listing))

    t0 = time.time()
    seen = set()
    total_lines = broken = dups = 0
    first_broken = None
    keys_seen = Counter()
    enum_counts = {k: Counter() for k in ("status", "depositType", "recipientType", "refundType")}

    days = defaultdict(lambda: {
        "total": 0, "SUCCESS": 0, "FAILED": 0, "REFUNDED": 0, "PROCESSING": 0, "other_status": 0,
        "usd_in": 0.0, "usd_out": 0.0, "no_fee_swaps": 0, "no_fee_usd": 0.0,
        "amounts": [], "unknown_user_swaps": 0})
    day_users = defaultdict(Counter)     # day -> user -> successful swaps
    day_recipients = defaultdict(set)    # day -> recipients seen (hashed)
    day_buckets = defaultdict(lambda: {b: [0, 0.0] for b in BUCKET_NAMES})
    day_burst = defaultdict(Counter)     # day -> same-second+same-route groups
    ref_week = defaultdict(lambda: [0, 0.0])
    fee_week = defaultdict(lambda: [0, 0.0, 0.0])  # swaps, sum(fee*usd), usd of those swaps
    fee_vals = defaultdict(Counter)
    routes = defaultdict(lambda: [0, 0.0])
    users = {}  # user -> [swaps, usd, first_daynum, last_daynum, daymask]
    ts_min = ts_max = None

    with open(args.input, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            total_lines += 1
            if total_lines % 100000 == 0:
                print("  read %d lines (%.0fs)..." % (total_lines, time.time() - t0))
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                ts = int(row["createdAtTimestamp"])
                addr = row["depositAddress"]
            except Exception:
                broken += 1
                if first_broken is None:
                    first_broken = line[:200]
                continue
            key = hash((addr, row.get("depositMemo") or ""))
            if key in seen:
                dups += 1
                continue
            seen.add(key)

            for k in row:
                keys_seen[k] += 1
            for k in enum_counts:
                enum_counts[k][str(row.get(k))] += 1
            ts_min = ts if ts_min is None else min(ts_min, ts)
            ts_max = ts if ts_max is None else max(ts_max, ts)

            day = day_of(ts)
            d = days[day]
            d["total"] += 1
            status = row.get("status")
            if status in STATUSES:
                d[status] += 1
            else:
                d["other_status"] += 1
            if status != "SUCCESS":
                continue

            usd_in = num(row.get("amountInUsd"))
            usd_out = num(row.get("amountOutUsd"))
            d["usd_in"] += usd_in
            d["usd_out"] += usd_out
            d["amounts"].append(usd_in)
            b = day_buckets[day][bucket(usd_in)]
            b[0] += 1
            b[1] += usd_in

            origin, dest = row.get("originAsset"), row.get("destinationAsset")
            day_burst[day][hash((ts, origin, dest))] += 1
            r = routes[(origin, dest)]
            r[0] += 1
            r[1] += usd_in

            week = week_of(day)
            ref = row.get("referral") or "(none)"
            rw = ref_week[(week, ref)]
            rw[0] += 1
            rw[1] += usd_in

            fees = row.get("appFees") or []
            if not fees:
                d["no_fee_swaps"] += 1
                d["no_fee_usd"] += usd_in
            for fe in fees:
                rec = fe.get("recipient") or "(unknown)"
                fval = num(fe.get("fee"))
                fw = fee_week[(week, rec)]
                fw[0] += 1
                fw[1] += fval * usd_in
                fw[2] += usd_in
                fee_vals[rec][fe.get("fee")] += 1

            if row.get("recipient"):
                day_recipients[day].add(hash(row["recipient"]))
            u = user_of(row)
            if u is None:
                d["unknown_user_swaps"] += 1
            else:
                day_users[day][u] += 1
                n = ts // 86400
                st = users.get(u)
                if st is None:
                    users[u] = [1, usd_in, n, n, 1 << (n - DAY_BASE)]
                else:
                    st[0] += 1
                    st[1] += usd_in
                    st[2] = min(st[2], n)
                    st[3] = max(st[3], n)
                    st[4] |= 1 << (n - DAY_BASE)

    unique_rows = len(seen)
    if unique_rows == 0:
        sys.exit("No readable swaps found. First unreadable line starts with:\n%s" % first_broken)
    if broken > unique_rows * 0.5:
        print("WARNING: more than half the lines were unreadable. First one starts with:\n  %s" % first_broken)

    out = args.out
    sdir = os.path.join(out, "summary")
    os.makedirs(sdir, exist_ok=True)
    print("Read %d lines in %.0fs. Writing tables..." % (total_lines, time.time() - t0))

    # ---- daily.csv
    rows = []
    for day in sorted(days):
        d = days[day]
        amounts = d["amounts"]
        uc = day_users[day]
        succ = d["SUCCESS"]
        heavy = sum(c for c in uc.values() if c >= 10)
        burst2 = sum(c for c in day_burst[day].values() if c >= 2)
        burst5 = sum(c for c in day_burst[day].values() if c >= 5)
        rows.append([
            day, d["total"], succ, d["FAILED"], d["REFUNDED"], d["PROCESSING"], d["other_status"],
            round(d["usd_in"], 2), round(d["usd_out"], 2),
            round(statistics.median(amounts), 2) if amounts else 0,
            len(uc), len(day_recipients[day]), d["unknown_user_swaps"],
            round(heavy / succ, 4) if succ else 0,
            burst2, burst5, d["no_fee_swaps"], round(d["no_fee_usd"], 2)])
    write_csv(os.path.join(sdir, "daily.csv"),
              ["day", "swaps_all_status", "swaps_success", "swaps_failed", "swaps_refunded",
               "swaps_processing", "swaps_other_status", "usd_in_success", "usd_out_success",
               "median_swap_usd", "unique_users_success", "unique_recipients_success",
               "success_swaps_user_unknown", "share_swaps_from_users_with_10plus_swaps_that_day",
               "success_swaps_in_same_second_same_route_groups_ge2",
               "success_swaps_in_same_second_same_route_groups_ge5",
               "success_swaps_with_no_app_fee", "usd_in_of_swaps_with_no_app_fee"], rows)

    # ---- size_buckets_daily.csv
    rows = []
    for day in sorted(day_buckets):
        for b in BUCKET_NAMES:
            cnt, usd = day_buckets[day][b]
            rows.append([day, b, cnt, round(usd, 2)])
    write_csv(os.path.join(sdir, "size_buckets_daily.csv"),
              ["day", "swap_size_usd_bucket", "swaps_success", "usd_in_success"], rows)

    # ---- referrals_weekly.csv
    rows = [[w, ref, v[0], round(v[1], 2)] for (w, ref), v in sorted(ref_week.items())]
    write_csv(os.path.join(sdir, "referrals_weekly.csv"),
              ["week_start_monday", "referral", "swaps_success", "usd_in_success"], rows)

    # ---- app_fees_weekly.csv
    rows = []
    for (w, rec), v in sorted(fee_week.items()):
        rows.append([w, rec, v[0], round(v[2], 2), round(v[1], 2), round(v[1] / 10000.0, 2)])
    write_csv(os.path.join(sdir, "app_fees_weekly.csv"),
              ["week_start_monday", "fee_recipient", "swaps_success_with_fee", "usd_in_of_those_swaps",
               "sum_fee_value_x_usd", "est_fee_usd_if_fee_is_basis_points"], rows)

    # ---- routes_top.csv
    top_routes = sorted(routes.items(), key=lambda kv: kv[1][1], reverse=True)[:300]
    write_csv(os.path.join(sdir, "routes_top.csv"),
              ["origin_asset", "destination_asset", "origin_chain_guess", "destination_chain_guess",
               "swaps_success", "usd_in_success"],
              [[o, de, chain_guess(o), chain_guess(de), v[0], round(v[1], 2)] for (o, de), v in top_routes])

    # ---- top_users.csv and user_retention.csv
    by_usd = sorted(users.items(), key=lambda kv: kv[1][1], reverse=True)[:150]
    by_cnt = sorted(users.items(), key=lambda kv: kv[1][0], reverse=True)[:150]
    chosen = {}
    for u, st in by_usd + by_cnt:
        chosen[u] = st
    rows = [[u, st[0], round(st[1], 2),
             day_of(st[2] * 86400), day_of(st[3] * 86400), bin(st[4]).count("1")]
            for u, st in sorted(chosen.items(), key=lambda kv: kv[1][1], reverse=True)]
    write_csv(os.path.join(sdir, "top_users.csv"),
              ["user_proxy", "swaps_success", "usd_in_success", "first_day", "last_day", "active_days"], rows)

    last_n = max((st[3] for st in users.values()), default=0)
    cohorts = defaultdict(lambda: [0, 0, 0, 0, 0])  # users, d1, d7, d14, one_day_only
    for st in users.values():
        first = st[2]
        mask = st[4] >> (first - DAY_BASE)  # bit 0 = first day
        c = cohorts[first]
        c[0] += 1
        c[1] += (mask >> 1) & 1
        c[2] += 1 if (mask >> 1) & ((1 << 7) - 1) else 0
        c[3] += 1 if (mask >> 1) & ((1 << 14) - 1) else 0
        c[4] += 1 if bin(mask).count("1") == 1 else 0
    rows = [[day_of(n * 86400), c[0], c[1], c[2], c[3], c[4], last_n - n] for n, c in sorted(cohorts.items())]
    write_csv(os.path.join(sdir, "user_retention.csv"),
              ["cohort_first_day_in_file", "users", "active_next_day", "active_within_days_1_to_7",
               "active_within_days_1_to_14", "active_on_one_day_only", "days_observable_after_cohort_day"], rows)

    # ---- summary.json
    top_share = {}
    total_usd = sum(st[1] for st in users.values())
    ranked = sorted((st[1] for st in users.values()), reverse=True)
    for k in (10, 100, 1000):
        top_share["top_%d_users_share_of_usd" % k] = round(sum(ranked[:k]) / total_usd, 4) if total_usd else None
    summary = {
        "input_file": args.input,
        "lines_read": total_lines,
        "unreadable_lines": broken,
        "duplicates_dropped": dups,
        "unique_swaps": unique_rows,
        "first_swap_utc": datetime.fromtimestamp(ts_min, tz=timezone.utc).isoformat(),
        "last_swap_utc": datetime.fromtimestamp(ts_max, tz=timezone.utc).isoformat(),
        "status_counts": dict(enum_counts["status"]),
        "depositType_counts": dict(enum_counts["depositType"]),
        "recipientType_counts": dict(enum_counts["recipientType"]),
        "refundType_counts": dict(enum_counts["refundType"]),
        "fields_seen": dict(keys_seen),
        "success_users_proxy_total": len(users),
        "success_usd_in_total": round(total_usd, 2),
        **top_share,
        "app_fee_values_by_recipient_top8": {
            rec: [[k, v] for k, v in cnt.most_common(8)] for rec, cnt in
            sorted(fee_vals.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:25]},
        "notes": [
            "Day = UTC. Volume/user figures use SUCCESS swaps only.",
            "user = refundTo (fallback first sender): a proxy for a person, not a person.",
            "appFees fee unit is not stated in the API docs; est_fee_usd_if_bps assumes basis points.",
            "Retention cohorts start at first appearance in this file; early cohorts include older users.",
            "chain_guess columns are a heuristic from asset ids."],
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2)

    # ---- zip
    zpath = os.path.join(out, "summary.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(out, "summary.json"), "summary.json")
        for name in sorted(os.listdir(sdir)):
            z.write(os.path.join(sdir, name), "summary/" + name)

    print("\nDone in %.0fs." % (time.time() - t0))
    print("  unique swaps: %d  (duplicates dropped: %d, unreadable lines: %d)" % (unique_rows, dups, broken))
    print("  from %s  to  %s" % (summary["first_swap_utc"][:16], summary["last_swap_utc"][:16]))
    print("  upload this file to the chat:  %s  (%.1f MB)" % (zpath, os.path.getsize(zpath) / 1e6))


if __name__ == "__main__":
    main()

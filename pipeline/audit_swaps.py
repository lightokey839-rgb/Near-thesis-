#!/usr/bin/env python3
"""
audit_swaps.py - red-team checks on the raw swap file (round 2).

Reads   data/intents_swaps.jsonl  (one swap per line, as downloaded)
Writes  data/audit/*.csv  and  data/audit/audit.json   (small files, safe to commit)

Checks
  1. Integrity: rows in time order, gaps between consecutive swaps (missing pages?),
     which UTC days are only partly covered.
  2. Pricing sanity: swaps whose USD-out / USD-in is far from 1 (bad price feed?)
     and how much volume they carry; the 20 largest swaps.
  3. Fee unit test: on stablecoin-to-stablecoin swaps, compare the haircut the
     user actually took (1 - tokens out / tokens in) with the sum of appFees.fee.
     If fee is in basis points, haircut_bps ~= fee_sum + small spread.
  4. Refunds: refundReason by day, by referral, by route, by deposit type,
     and how concentrated refunds were among refund addresses on spike days.
  5. Buyback fee: share of SUCCESS swaps that pay buybacks.multisignature.near,
     fee values per referral, USD estimate under the basis-point assumption.

Standard library only (Python 3.8+). Streams the file, so size is not a problem.

Usage:
    python pipeline/audit_swaps.py
    python pipeline/audit_swaps.py --input data/intents_swaps.jsonl --out data/audit
"""

import argparse
import csv
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

BUYBACK = "buybacks.multisignature.near"
SPIKE_DAYS = ("2026-11-04", "2026-11-05")


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def day_of(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def hour_of(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:00")


def unit_price(row, side):
    """USD per token for one side of a swap, or None if not computable."""
    usd = num(row.get("amount%sUsd" % side))
    amt = num(row.get("amount%sFormatted" % side))
    if usd <= 0 or amt <= 0:
        return None
    return usd / amt


def is_stable_pair(row):
    """Both sides priced within 2% of $1 -> treat as a stablecoin-to-stablecoin swap."""
    pin, pout = unit_price(row, "In"), unit_price(row, "Out")
    return pin is not None and pout is not None and 0.98 <= pin <= 1.02 and 0.98 <= pout <= 1.02


def week_of(day_str):
    d = datetime.strptime(day_str, "%Y-%m-%d")
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")  # Monday


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def run(input_path, out_dir):
    if not os.path.exists(input_path):
        sys.exit("Cannot find %s. Run from the near-thesis folder or pass --input." % input_path)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()

    n = broken = out_of_order = 0
    prev_ts = None
    prev_cursor = None
    gap_edges = []                   # (gap_s, newer_ts, cursor of the row just newer than the gap)
    same_asset = [0, 0.0]            # SUCCESS swaps with origin == destination asset
    aurora_day = Counter()           # (day, referral, status) for referral codes starting "aurora"
    bb_week_value = Counter()        # (week, fee value) -> swaps
    bb_week_value_usd = Counter()    # (week, fee value) -> usd_in
    stamps = []                      # all timestamps (ints) for gap analysis
    seen = set()
    dups = 0
    hourly = Counter()

    # pricing sanity
    ratio_bins = Counter()           # bin -> [count]
    ratio_usd = Counter()            # bin -> usd_in
    big = []                         # (usd_in, row summary)
    success_usd = 0.0
    success_usd_min_side = 0.0

    # fee unit test: total_fee -> list of haircut bps (stable pairs, SUCCESS, >= $50)
    haircut = defaultdict(list)
    haircut_by_combo = defaultdict(list)

    # refunds
    ref_day_reason = Counter()
    ref_day_reason_usd = Counter()
    day_status = Counter()
    ref_spike_referral = Counter()
    ref_spike_route = Counter()
    ref_spike_deptype = Counter()
    ref_spike_refundto = Counter()
    ref_spike_hour = Counter()
    ref_spike_usd = []
    ref_spike_origin = Counter()
    base_referral_all = Counter()    # all swaps on spike days by referral (denominator)
    ref_reason_overall = Counter()

    # buyback
    succ = 0
    succ_with_bb = 0
    bb_value_by_ref = defaultdict(Counter)
    bb_usd_est_by_day = Counter()
    fee_sum_by_ref = defaultdict(Counter)

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            if n % 200000 == 0:
                print("  read %d rows (%.0fs)..." % (n, time.time() - t0))
            try:
                row = json.loads(line)
                ts = int(row["createdAtTimestamp"])
                key = (row["depositAddress"], row.get("depositMemo") or "")
            except Exception:
                broken += 1
                continue
            if key in seen:
                dups += 1
                continue
            seen.add(key)
            if prev_ts is not None and ts > prev_ts:
                out_of_order += 1      # file is newest -> oldest; a later stamp is out of order
            if prev_ts is not None and prev_ts - ts >= 900:
                gap_edges.append((prev_ts - ts, prev_ts, prev_cursor))
            prev_ts = ts
            prev_cursor = key
            stamps.append(ts)
            hourly[hour_of(ts)] += 1

            day = day_of(ts)
            status = row.get("status") or "None"
            day_status[(day, status)] += 1
            referral = row.get("referral") or "(none)"
            origin, dest = row.get("originAsset"), row.get("destinationAsset")
            usd_in, usd_out = num(row.get("amountInUsd")), num(row.get("amountOutUsd"))
            fees = row.get("appFees") or []

            if referral.startswith("aurora"):
                aurora_day[(day, referral, status)] += 1
            if day in SPIKE_DAYS:
                base_referral_all[(day, referral)] += 1

            if status == "REFUNDED":
                reason = str(row.get("refundReason"))
                ref_day_reason[(day, reason)] += 1
                ref_day_reason_usd[(day, reason)] += usd_in
                ref_reason_overall[reason] += 1
                if day in SPIKE_DAYS:
                    ref_spike_referral[(day, referral, reason)] += 1
                    ref_spike_route[(day, origin, dest)] += 1
                    ref_spike_deptype[(day, row.get("depositType"), row.get("refundType"))] += 1
                    ref_spike_refundto[(day, row.get("refundTo"))] += 1
                    ref_spike_hour[hour_of(ts)] += 1
                    ref_spike_usd.append(usd_in)
                    ref_spike_origin[(day, origin)] += 1

            if status != "SUCCESS":
                continue
            succ += 1
            success_usd += usd_in
            success_usd_min_side += min(usd_in, usd_out) if usd_out > 0 else 0.0
            if origin == dest:
                same_asset[0] += 1
                same_asset[1] += usd_in

            if usd_in > 0 and usd_out > 0:
                r = usd_out / usd_in
                b = ("<0.5" if r < 0.5 else "0.5-0.9" if r < 0.9 else "0.9-0.98" if r < 0.98
                     else "0.98-1.02" if r <= 1.02 else "1.02-1.1" if r <= 1.1
                     else "1.1-2" if r <= 2 else ">2")
            else:
                b = "missing_usd"
            ratio_bins[b] += 1
            ratio_usd[b] += usd_in
            if usd_in >= 1_000_000 or len(big) < 20:
                big.append((usd_in, usd_out, day, origin, dest, referral))

            total_fee = 0.0
            has_bb = False
            combo = []
            for fe in fees:
                v = num(fe.get("fee"))
                total_fee += v
                rec = fe.get("recipient") or "(unknown)"
                combo.append("%s=%g" % ("buybacks" if rec == BUYBACK else "app", v))
                if rec == BUYBACK:
                    has_bb = True
                    bb_value_by_ref[referral][fe.get("fee")] += 1
                    bb_usd_est_by_day[day] += v / 10000.0 * usd_in
                    wk = week_of(day)
                    bb_week_value[(wk, fe.get("fee"))] += 1
                    bb_week_value_usd[(wk, fe.get("fee"))] += usd_in
            fee_sum_by_ref[referral][total_fee] += 1
            if has_bb:
                succ_with_bb += 1

            if usd_in >= 50 and is_stable_pair(row):
                ain, aout = num(row.get("amountInFormatted")), num(row.get("amountOutFormatted"))
                if ain > 0:
                    hc = (1 - aout / ain) * 10000.0
                    if -500 < hc < 2000:
                        haircut[total_fee].append(hc)
                        haircut_by_combo[",".join(sorted(combo)) or "(no fees)"].append(hc)

    if not stamps:
        sys.exit("No readable swaps found.")
    print("Read %d rows in %.0fs. Writing tables..." % (n, time.time() - t0))

    # ---- 1. integrity
    stamps.sort()
    gaps = sorted(((stamps[i + 1] - stamps[i], stamps[i]) for i in range(len(stamps) - 1)), reverse=True)[:15]
    first_day, last_day = day_of(stamps[0]), day_of(stamps[-1])
    hours = sorted(hourly)
    hour_counts = [hourly[h] for h in hours[1:-1]]
    med_hour = statistics.median(hour_counts) if hour_counts else 0
    empty_or_thin = [h for h in hours[1:-1] if hourly[h] < 0.2 * med_hour]
    write_csv(os.path.join(out_dir, "integrity_largest_gaps.csv"),
              ["gap_seconds", "gap_starts_utc"],
              [[g, datetime.fromtimestamp(s, tz=timezone.utc).isoformat()] for g, s in gaps])
    write_csv(os.path.join(out_dir, "hourly_counts.csv"), ["hour_utc", "swaps_all_status"],
              [[h, hourly[h]] for h in hours])

    gap_edges.sort(reverse=True)
    write_csv(os.path.join(out_dir, "integrity_gap_cursors.csv"),
              ["gap_seconds", "gap_ends_utc_newer_side", "resume_lastDepositAddress", "resume_lastDepositMemo"],
              [[g, datetime.fromtimestamp(t, tz=timezone.utc).isoformat(), c[0], c[1]] for g, t, c in gap_edges[:15]])

    # ---- 2. pricing sanity
    order = ["<0.5", "0.5-0.9", "0.9-0.98", "0.98-1.02", "1.02-1.1", "1.1-2", ">2", "missing_usd"]
    write_csv(os.path.join(out_dir, "price_ratio_bins.csv"),
              ["usd_out_over_usd_in", "swaps_success", "usd_in_success", "share_of_usd"],
              [[b, ratio_bins[b], round(ratio_usd[b], 2), round(ratio_usd[b] / success_usd, 5) if success_usd else 0]
               for b in order])
    big.sort(reverse=True)
    write_csv(os.path.join(out_dir, "largest_swaps.csv"),
              ["usd_in", "usd_out", "day", "origin_asset", "destination_asset", "referral"],
              [[round(a, 2), round(b, 2), c, d, e, g] for a, b, c, d, e, g in big[:40]])

    # ---- 3. fee unit test
    rows = []
    for fee in sorted(haircut):
        vals = sorted(haircut[fee])
        if len(vals) < 30:
            continue
        rows.append([fee, len(vals), round(pct(vals, 0.1), 2), round(statistics.median(vals), 2),
                     round(pct(vals, 0.9), 2), round(statistics.median(vals) - fee, 2)])
    write_csv(os.path.join(out_dir, "fee_unit_test_stable_pairs.csv"),
              ["sum_of_appFees_fee", "swaps", "haircut_bps_p10", "haircut_bps_median",
               "haircut_bps_p90", "median_minus_fee"], rows)
    fee_test_rows = rows
    combo_rows = []
    for combo, vals in sorted(haircut_by_combo.items(), key=lambda kv: -len(kv[1]))[:25]:
        vals = sorted(vals)
        combo_rows.append([combo, len(vals), round(statistics.median(vals), 2)])
    write_csv(os.path.join(out_dir, "fee_unit_test_by_fee_combo.csv"),
              ["fee_combo", "swaps", "haircut_bps_median"], combo_rows)

    # ---- 4. refunds
    days = sorted({d for d, _ in day_status})
    reasons = sorted({r for _, r in ref_day_reason})
    rows = []
    for d in days:
        total = sum(v for (dd, _), v in day_status.items() if dd == d)
        refunded = day_status[(d, "REFUNDED")]
        rows.append([d, total, refunded, round(refunded / total, 4) if total else 0]
                    + [ref_day_reason[(d, r)] for r in reasons])
    write_csv(os.path.join(out_dir, "refunds_by_day_reason.csv"),
              ["day", "swaps_all_status", "refunded", "refund_rate"] + ["reason_" + r for r in reasons], rows)
    rows = [[d, ref, reason, c, base_referral_all[(d, ref)]]
            for (d, ref, reason), c in sorted(ref_spike_referral.items(), key=lambda kv: -kv[1])[:60]]
    write_csv(os.path.join(out_dir, "refunds_spike_by_referral.csv"),
              ["day", "referral", "refundReason", "refunded", "all_swaps_that_referral_that_day"], rows)
    write_csv(os.path.join(out_dir, "refunds_spike_by_route.csv"),
              ["day", "origin_asset", "destination_asset", "refunded"],
              [[d, o, de, c] for (d, o, de), c in sorted(ref_spike_route.items(), key=lambda kv: -kv[1])[:60]])
    write_csv(os.path.join(out_dir, "refunds_spike_by_type.csv"),
              ["day", "depositType", "refundType", "refunded"],
              [[d, a, b, c] for (d, a, b), c in sorted(ref_spike_deptype.items())])
    write_csv(os.path.join(out_dir, "refunds_spike_by_hour.csv"), ["hour_utc", "refunded"],
              [[h, ref_spike_hour[h]] for h in sorted(ref_spike_hour)])
    conc = {}
    for d in SPIKE_DAYS:
        counts = sorted((c for (dd, _), c in ref_spike_refundto.items() if dd == d), reverse=True)
        tot = sum(counts)
        conc[d] = {
            "refunded": tot,
            "distinct_refund_addresses": len(counts),
            "top1_share": round(counts[0] / tot, 4) if tot else None,
            "top10_share": round(sum(counts[:10]) / tot, 4) if tot else None,
            "top100_share": round(sum(counts[:100]) / tot, 4) if tot else None,
        }
    us = sorted(ref_spike_usd)
    spike_usd = {"refunded_usd_in_sum": round(sum(us), 2),
                 "median_usd": round(statistics.median(us), 4) if us else None,
                 "p90_usd": round(pct(us, 0.9), 2) if us else None,
                 "share_under_1_usd": round(sum(1 for x in us if x < 1) / len(us), 4) if us else None}

    # ---- 5. buyback fee
    rows = []
    for ref, cnt in sorted(bb_value_by_ref.items(), key=lambda kv: -sum(kv[1].values()))[:30]:
        rows.append([ref, sum(cnt.values())] + ["%s:%d" % (k, v) for k, v in cnt.most_common(4)])
    write_csv(os.path.join(out_dir, "buyback_fee_values_by_referral.csv"),
              ["referral", "success_swaps_paying_buyback", "top_fee_values(value:count)"], rows)
    write_csv(os.path.join(out_dir, "buyback_fee_value_by_week.csv"),
              ["week_start_monday", "buyback_fee_bps", "success_swaps", "usd_in_success"],
              [[w, v, c, round(bb_week_value_usd[(w, v)], 2)]
               for (w, v), c in sorted(bb_week_value.items(), key=lambda kv: (kv[0][0], -kv[1]))])
    write_csv(os.path.join(out_dir, "aurora_referrals_by_day.csv"), ["day", "referral", "status", "swaps"],
              [[d, r, st, c] for (d, r, st), c in sorted(aurora_day.items())])
    write_csv(os.path.join(out_dir, "buyback_usd_est_by_day_if_bps.csv"), ["day", "buyback_usd_if_bps"],
              [[d, round(bb_usd_est_by_day[d], 2)] for d in sorted(bb_usd_est_by_day)])

    audit = {
        "input_file": input_path,
        "rows": n, "unreadable": broken, "duplicates": dups,
        "rows_out_of_time_order": out_of_order,
        "first_swap_utc": datetime.fromtimestamp(stamps[0], tz=timezone.utc).isoformat(),
        "last_swap_utc": datetime.fromtimestamp(stamps[-1], tz=timezone.utc).isoformat(),
        "partial_days": [first_day, last_day],
        "largest_gap_seconds": gaps[0][0] if gaps else 0,
        "median_swaps_per_hour": med_hour,
        "hours_below_20pct_of_median": empty_or_thin[:50],
        "success_swaps": succ,
        "success_usd_in": round(success_usd, 2),
        "success_usd_min_of_in_out": round(success_usd_min_side, 2),
        "success_same_asset_swaps": same_asset[0],
        "success_same_asset_usd_in": round(same_asset[1], 2),
        "success_share_paying_buyback": round(succ_with_bb / succ, 4) if succ else None,
        "fee_unit_test": [dict(zip(["fee", "swaps", "p10", "median", "p90", "median_minus_fee"], r))
                          for r in fee_test_rows],
        "refund_reasons_overall": dict(ref_reason_overall),
        "refund_spike_concentration": conc,
        "refund_spike_usd": spike_usd,
        "refund_spike_top_origin_assets": [[d, o, c] for (d, o), c in ref_spike_origin.most_common(10)],
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(out_dir, "audit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(audit, f, indent=2)
    print("Done in %.0fs. Wrote %s" % (time.time() - t0, out_dir))
    return audit


def main():
    ap = argparse.ArgumentParser(description="Red-team checks on the raw swap file.")
    ap.add_argument("--input", default=os.path.join("data", "intents_swaps.jsonl"))
    ap.add_argument("--out", default=os.path.join("data", "audit"))
    args = ap.parse_args()
    run(args.input, args.out)


if __name__ == "__main__":
    main()

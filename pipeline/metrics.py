#!/usr/bin/env python3
"""
metrics.py - compute every headline number from the pinned snapshot tables.

Reads only small files that are committed to the repo (data/summary, data/audit,
data/bq, data/onchain, data/market). Writes data/derived/metrics.json, where every
metric has: value, unit, kind (FACT = measured / INFERENCE = derived by arithmetic
or modelling), source files and the method in one line.

If an input file is missing, the metric is recorded as "not computed" with the
reason - it is never filled with a guess. THESIS.md and the dashboard read only
this file, so every number in them can be traced back to a source.

Usage:  python pipeline/metrics.py [--data data]
"""

import argparse
import csv
import json
import math
import os
import statistics as st
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PARTIAL_OR_GAP_DAYS = {"2026-09-28", "2026-11-10",              # partial first/last day of the download
                       "2026-10-01", "2026-10-20", "2026-11-02"}  # multi-hour gaps in the source API
HSP029_RATE = 0.016  # issuance ceiling after HSP-029's 24-month schedule (passed 2 Nov 2026, not yet in force)


class Metrics:
    def __init__(self, data):
        self.data = data
        self.out = {}
        self.missing = []

    def path(self, *p):
        return os.path.join(self.data, *p)

    def csv(self, *p):
        with open(self.path(*p), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def json(self, *p):
        with open(self.path(*p), encoding="utf-8") as f:
            return json.load(f)

    def put(self, key, value, unit, kind, sources, method):
        if isinstance(value, float):
            value = round(value, 6)
        self.out[key] = {"value": value, "unit": unit, "kind": kind, "sources": sources, "method": method}

    def section(self, name, fn):
        try:
            fn(self)
        except (FileNotFoundError, KeyError, ValueError, ZeroDivisionError, IndexError, st.StatisticsError) as e:
            self.missing.append({"section": name, "reason": "%s: %s" % (type(e).__name__, e)})
            print("  not computed: %s (%s)" % (name, e))


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


# ----------------------------------------------------------------------------- swaps (1Click)
def swaps(m):
    s = m.json("summary.json")
    src = ["data/summary.json"]
    m.put("swaps_first_utc", s["first_swap_utc"], "", "FACT", src, "earliest createdAt in the download")
    m.put("swaps_last_utc", s["last_swap_utc"], "", "FACT", src, "latest createdAt in the download")
    m.put("swaps_total", s["unique_swaps"], "swaps", "FACT", src, "unique depositAddress+memo rows, all statuses")
    m.put("swaps_duplicates", s["duplicates_dropped"], "rows", "FACT", src, "rows dropped as duplicates")
    m.put("swaps_success", s["status_counts"]["SUCCESS"], "swaps", "FACT", src, "status = SUCCESS")
    m.put("swaps_refunded", s["status_counts"].get("REFUNDED", 0), "swaps", "FACT", src, "status = REFUNDED")
    m.put("success_usd_total", s["success_usd_in_total"], "USD", "FACT", src, "sum of amountInUsd, SUCCESS swaps")
    m.put("user_proxies_total", s["success_users_proxy_total"], "addresses", "FACT", src,
          "distinct refundTo (fallback first sender) on SUCCESS swaps - a proxy, not people")
    m.put("top1000_users_usd_share", s["top_1000_users_share_of_usd"], "share", "FACT", src,
          "USD share of the 1,000 largest user proxies")

    daily = m.csv("summary", "daily.csv")
    clean = [r for r in daily if r["day"] not in PARTIAL_OR_GAP_DAYS]
    m.put("clean_full_days", len(clean), "days", "FACT", ["data/summary/daily.csv"],
          "days excluding the partial first/last day and the 3 days with source-API gaps")
    m.put("oneclick_usd_per_day", st.mean(f(r["usd_in_success"]) for r in clean), "USD/day", "FACT",
          ["data/summary/daily.csv"], "mean daily SUCCESS amountInUsd over clean full days")
    users = [int(r["unique_users_success"]) for r in clean]
    m.put("oneclick_users_per_day_median", st.median(users), "addresses/day", "FACT", ["data/summary/daily.csv"],
          "median daily distinct user proxies, clean full days")
    heavy = [f(r["share_swaps_from_users_with_10plus_swaps_that_day"]) for r in clean]
    m.put("heavy_user_share_first_week", st.mean(heavy[:7]), "share", "FACT", ["data/summary/daily.csv"],
          "share of SUCCESS swaps from addresses with 10+ swaps that day, first 7 clean days")
    m.put("heavy_user_share_last_week", st.mean(heavy[-7:]), "share", "FACT", ["data/summary/daily.csv"],
          "same, last 7 clean days")

    b = m.csv("summary", "size_buckets_daily.csv")
    cnt, usd = {}, {}
    for r in b:
        cnt[r["swap_size_usd_bucket"]] = cnt.get(r["swap_size_usd_bucket"], 0) + int(r["swaps_success"])
        usd[r["swap_size_usd_bucket"]] = usd.get(r["swap_size_usd_bucket"], 0) + f(r["usd_in_success"])
    tc, tu = sum(cnt.values()), sum(usd.values())
    big, small = ["gte_10k"], ["lt_1", "1_10", "10_100"]
    src = ["data/summary/size_buckets_daily.csv"]
    m.put("swaps_10k_plus_share_of_swaps", sum(cnt[k] for k in big) / tc, "share", "FACT", src, "swaps >= $10k / all SUCCESS swaps")
    m.put("swaps_10k_plus_share_of_usd", sum(usd[k] for k in big) / tu, "share", "FACT", src, "USD of swaps >= $10k / all USD")
    m.put("swaps_under_100_share_of_swaps", sum(cnt[k] for k in small) / tc, "share", "FACT", src, "swaps < $100 / all")
    m.put("swaps_under_100_share_of_usd", sum(usd[k] for k in small) / tu, "share", "FACT", src, "USD of swaps < $100 / all USD")

    ref = {}
    for r in m.csv("summary", "referrals_weekly.csv"):
        ref[r["referral"]] = ref.get(r["referral"], 0) + f(r["usd_in_success"])
    tot = sum(ref.values())
    ranked = sorted(ref.items(), key=lambda kv: -kv[1])
    src = ["data/summary/referrals_weekly.csv"]
    m.put("top_referral", ranked[0][0], "", "FACT", src, "referral code with the most SUCCESS USD")
    m.put("top_referral_usd_share", ranked[0][1] / tot, "share", "FACT", src, "its share of SUCCESS USD")
    m.put("top5_referrals_usd_share", sum(v for _, v in ranked[:5]) / tot, "share", "FACT", src, "top 5 referral codes' share")
    m.put("referral_ranking_top10", [[k, round(v / tot, 4)] for k, v in ranked[:10]], "share", "FACT", src, "top 10 codes by USD share")


def audit(m):
    a = m.json("audit", "audit.json")
    src = ["data/audit/audit.json"]
    bins = {r["usd_out_over_usd_in"]: f(r["share_of_usd"]) for r in m.csv("audit", "price_ratio_bins.csv")}
    m.put("usd_share_priced_within_2pct", bins["0.98-1.02"], "share", "FACT", ["data/audit/price_ratio_bins.csv"],
          "share of SUCCESS USD in swaps whose USD out / USD in is within +-2%")
    m.put("same_asset_usd_share", a["success_same_asset_usd_in"] / a["success_usd_in"], "share", "FACT", src,
          "SUCCESS USD in swaps where origin asset = destination asset (transfers, not trades)")
    m.put("buyback_fee_swap_share", a["success_share_paying_buyback"], "share", "FACT", src,
          "share of SUCCESS swaps with buybacks.multisignature.near in appFees")

    pts = [(f(r["sum_of_appFees_fee"]), f(r["haircut_bps_median"]), int(r["swaps"]))
           for r in m.csv("audit", "fee_unit_test_stable_pairs.csv") if int(r["swaps"]) >= 200]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    mx, my = st.mean(xs), st.mean(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    m.put("fee_unit_slope", slope, "bps per fee unit", "FACT", ["data/audit/fee_unit_test_stable_pairs.csv"],
          "least-squares slope of median user haircut (bps) on summed appFees.fee, stablecoin pairs, fee groups with 200+ swaps; 1.0 = basis points")
    m.put("fee_unit_groups", len(pts), "groups", "FACT", ["data/audit/fee_unit_test_stable_pairs.csv"], "fee groups used")

    rows = m.csv("audit", "refunds_by_day_reason.csv")
    spike = [r for r in rows if r["day"] in ("2026-11-04", "2026-11-05")]
    normal = [f(r["refund_rate"]) for r in rows if r["day"] not in ("2026-11-04", "2026-11-05")]
    ref_spike = sum(int(r["refunded"]) for r in spike)
    isf = sum(int(r.get("reason_INTENT_SUBMIT_FAILED", 0)) for r in spike)
    src = ["data/audit/refunds_by_day_reason.csv"]
    m.put("refund_rate_normal_median", st.median(normal), "share", "FACT", src, "median daily refund rate excluding 4-5 Nov")
    m.put("refund_spike_refunded", ref_spike, "swaps", "FACT", src, "refunds on 4-5 Nov")
    m.put("refund_spike_intent_submit_failed_share", isf / ref_spike, "share", "FACT", src,
          "share of 4-5 Nov refunds with refundReason INTENT_SUBMIT_FAILED")
    aur = m.csv("audit", "aurora_referrals_by_day.csv")
    aur_ref = sum(int(r["swaps"]) for r in aur if r["day"] in ("2026-11-04", "2026-11-05") and r["status"] == "REFUNDED")
    aur_succ = [sum(int(r["swaps"]) for r in aur if r["day"] == d and r["status"] == "SUCCESS") for d in ("2026-11-04", "2026-11-05")]
    m.put("refund_spike_aurora_share", aur_ref / ref_spike, "share", "FACT", ["data/audit/aurora_referrals_by_day.csv"],
          "share of 4-5 Nov refunds from referral codes starting 'aurora'")
    m.put("aurora_success_on_spike_days", aur_succ, "swaps/day", "FACT", ["data/audit/aurora_referrals_by_day.csv"],
          "Aurora SUCCESS swaps on 4 and 5 Nov (normal is ~1,000/day)")

    gaps = m.csv("audit", "gap_check.csv")
    hours = sum(int(r["gap_seconds"]) for r in gaps) / 3600
    m.put("source_gap_hours", hours, "hours", "FACT", ["data/audit/gap_check.csv"],
          "hours with zero swaps in the Explorer API itself (re-checked with the API)")
    t0 = datetime.fromisoformat(a["first_swap_utc"]).timestamp()
    t1 = datetime.fromisoformat(a["last_swap_utc"]).timestamp()
    m.put("source_gap_share_of_window", hours * 3600 / (t1 - t0), "share", "FACT", ["data/audit/gap_check.csv", "data/audit/audit.json"],
          "gap hours / hours in the download window")

    bb = {r["day"]: f(r["buyback_usd_if_bps"]) for r in m.csv("audit", "buyback_usd_est_by_day_if_bps.csv")}
    days = [d for d in bb if d not in PARTIAL_OR_GAP_DAYS]
    m.put("oneclick_buyback_fee_usd_per_year", st.mean(bb[d] for d in days) * 365, "USD/yr", "INFERENCE",
          ["data/audit/buyback_usd_est_by_day_if_bps.csv"],
          "mean daily (fee/10,000 x amountInUsd) to buybacks.multisignature.near on clean days x 365; 1Click only")


# ----------------------------------------------------------------------------- who funds the buyback (1Click)
def channels(m):
    """Volume vs buyback fees by referral code (the app that sent the swap). Buyback USD = fee bps x amountInUsd."""
    rows = m.csv("audit", "buyback_by_referral.csv")
    src = ["data/audit/buyback_by_referral.csv"]
    usd = {r["referral"]: f(r["usd_in_success"]) for r in rows}
    bb = {r["referral"]: f(r["buyback_usd_if_bps"]) for r in rows}
    tu, tb = sum(usd.values()), sum(bb.values())
    by_usd = sorted(usd, key=lambda k: (-usd[k], k))
    by_bb = sorted(bb, key=lambda k: (-bb[k], -usd[k], k))
    top = by_usd[0]
    rest_bps = (tb - bb[top]) / (tu - usd[top]) * 1e4
    m.put("channels_total", len(rows), "referral codes", "FACT", src, "distinct referral codes on SUCCESS 1Click swaps ('(none)' = no code)")
    m.put("channels_paying_buyback", sum(1 for k in bb if bb[k] >= 0.01), "referral codes", "FACT", src,
          "referral codes whose swaps paid at least $0.01 in total to buybacks.multisignature.near (the table is rounded to cents)")
    m.put("oneclick_buyback_bps", tb / tu * 1e4, "bps", "INFERENCE", src,
          "all buyback fees / all SUCCESS volume, 1Click download window (fee bps x amountInUsd at swap time)")
    m.put("oneclick_buyback_usd_per_million", tb / tu * 1e6, "USD per $1M", "INFERENCE", src,
          "buyback fees per $1M of 1Click volume")
    m.put("top_volume_channel", top, "", "FACT", src, "referral code with the most SUCCESS volume")
    m.put("top_volume_channel_usd_share", usd[top] / tu, "share", "FACT", src, "its share of 1Click volume")
    m.put("top_volume_channel_buyback_share", bb[top] / tb, "share", "INFERENCE", src, "its share of 1Click buyback fees")
    m.put("top_volume_channel_buyback_bps", bb[top] / usd[top] * 1e4, "bps", "INFERENCE", src, "its buyback fees / its volume")
    m.put("rest_buyback_bps", rest_bps, "bps", "INFERENCE", src, "buyback fees / volume for all other referral codes together")
    m.put("buyback_uplift_if_top_channel_paid_rest_rate", (usd[top] * rest_bps / 1e4 - bb[top]) / tb, "share", "INFERENCE", src,
          "HYPOTHETICAL: extra 1Click buyback fees if the top-volume code paid the other codes' average rate, as a share of today's")
    if "(none)" in usd:
        m.put("no_referral_usd_share", usd["(none)"] / tu, "share", "FACT", src, "share of 1Click volume with no referral code")
        m.put("no_referral_buyback_share", bb["(none)"] / tb, "share", "INFERENCE", src, "their share of 1Click buyback fees")
    m.put("buyback_top5_channels_share", sum(bb[k] for k in by_bb[:5]) / tb, "share", "INFERENCE", src,
          "share of buyback fees paid through the 5 referral codes that pay the most")
    m.put("buyback_top5_channels_usd_share", sum(usd[k] for k in by_bb[:5]) / tu, "share", "FACT", src,
          "share of volume those same 5 codes carry")
    m.put("usd_share_paying_no_buyback", sum(usd[k] for k in usd if bb[k] < 0.01) / tu, "share", "FACT", src,
          "share of volume from referral codes that paid less than $0.01 in buyback fees over the whole download")
    keys = sorted(set(by_usd[:6]) | set(by_bb[:6]), key=lambda k: (-usd[k], k))
    m.put("channel_table", [[k, round(usd[k] / tu, 4), round(bb[k] / tb, 4), round(bb[k] / usd[k] * 1e4, 2) if usd[k] else 0]
                            for k in keys], "", "INFERENCE", src,
          "referral code, share of volume, share of buyback fees, buyback bps (top 6 by volume and top 6 by buyback)")

    wk = m.csv("audit", "buyback_by_week_referral.csv")
    src = ["data/audit/buyback_by_week_referral.csv"]
    weeks = sorted({r["week_start_monday"] for r in wk})
    series = []
    for w in weeks:
        rs = [r for r in wk if r["week_start_monday"] == w]
        wu, wb = sum(f(r["usd_in_success"]) for r in rs), sum(f(r["buyback_usd_if_bps"]) for r in rs)
        t = [r for r in rs if r["referral"] == top]
        tu_w, tb_w = (f(t[0]["usd_in_success"]), f(t[0]["buyback_usd_if_bps"])) if t else (0.0, 0.0)
        series.append([w, round(tu_w / wu, 4) if wu else 0, round(tb_w / wb, 4) if wb else 0, round(wb / wu * 1e4, 3) if wu else 0])
    m.put("top_volume_channel_weekly", series, "", "INFERENCE", src,
          "per week: top-volume code's share of volume, its share of buyback fees, all-1Click buyback bps")
    m.put("top_volume_channel_weekly_usd_share_min", min(s[1] for s in series), "share", "FACT", src, "lowest weekly volume share of the top code")
    m.put("top_volume_channel_weekly_usd_share_max", max(s[1] for s in series), "share", "FACT", src, "highest weekly volume share of the top code")
    m.put("top_volume_channel_weekly_buyback_share_max", max(s[2] for s in series), "share", "INFERENCE", src,
          "highest weekly buyback share of the top code")


# ----------------------------------------------------------------------------- market and chain
def market(m):
    snap = m.json("market", "near_chain_snapshot.json")
    src = ["data/market/near_chain_snapshot.json"]
    supply, stake, rate = snap["total_supply_near"], snap["current_validator_stake_near"], snap["max_inflation_rate"]
    m.put("snapshot_block_time_utc", snap["block_time_utc"], "", "FACT", src, "time of the RPC snapshot")
    m.put("total_supply_near", supply, "NEAR", "FACT", src, "block header total_supply")
    m.put("validator_stake_near", stake, "NEAR", "FACT", src, "sum of current validators' stake")
    m.put("staked_share", stake / supply, "share", "FACT", src, "validator stake / total supply")
    m.put("max_inflation_rate", rate, "per year", "FACT", src, "protocol config max_inflation_rate")
    m.put("protocol_reward_rate", snap["protocol_reward_rate"], "share", "FACT", src, "protocol config protocol_reward_rate (treasury cut)")
    issuance = supply * rate
    m.put("issuance_near_per_year", issuance, "NEAR/yr", "INFERENCE", src, "total supply x max inflation rate (ceiling; assumes full uptime)")
    m.put("issuance_near_per_year_hsp029", supply * HSP029_RATE, "NEAR/yr", "INFERENCE", src,
          "total supply x 1.6% (HSP-029 end state, not yet in force)")
    m.put("staking_yield_ceiling", issuance * (1 - snap["protocol_reward_rate"]) / stake, "per year", "INFERENCE", src,
          "issuance to validators / validator stake, before commission")
    m.put("staking_yield_ceiling_hsp029", supply * HSP029_RATE * (1 - snap["protocol_reward_rate"]) / stake, "per year",
          "INFERENCE", src, "same at 1.6%")

    peers = m.csv("market", "peers.csv")
    near = [p for p in peers if p["chain"] == "NEAR"][0]
    price, mcap = f(near["price_usd"]), f(near["market_cap_usd"])
    src = ["data/market/peers.csv"]
    m.put("near_price_usd", price, "USD", "FACT", src, "CoinGecko current price at fetch time")
    m.put("near_market_cap_usd", mcap, "USD", "FACT", src, "CoinGecko market cap at fetch time")
    m.put("issuance_usd_per_year", issuance * price, "USD/yr", "INFERENCE", src + ["data/market/near_chain_snapshot.json"],
          "issuance NEAR/yr x current price")
    m.put("peer_table", [[p["chain"], f(p["market_cap_usd"]), f(p["fdv_usd"]), f(p["chain_fees_30d_usd"]),
                          f(p["chain_revenue_30d_usd"])] for p in peers], "USD", "FACT", src,
          "chain, market cap, FDV, DefiLlama chain fees 30d, chain revenue 30d")

    prices = m.csv("market", "near_price_daily.csv")
    m.put("near_price_2026_01_01", f(prices[0]["near_usd"]), "USD", "FACT", ["data/market/near_price_daily.csv"], "first daily price in 2026")
    m.put("near_price_change_ytd", f(prices[-1]["near_usd"]) / f(prices[0]["near_usd"]) - 1, "share", "FACT",
          ["data/market/near_price_daily.csv"], "last daily price / 1 Jan 2026 price - 1")

    ll = m.csv("market", "defillama_intents_daily.csv")
    done = [r for r in ll if f(r["near_captured_revenue_usd"]) and f(r["intents_volume_usd"])]
    # DefiLlama's last 1-2 days are often incomplete: stop 2 days before the newest row
    last = date.fromisoformat(done[-1]["day"]) - timedelta(days=2)
    win = [r for r in done if last - timedelta(days=29) <= date.fromisoformat(r["day"]) <= last]
    src = ["data/market/defillama_intents_daily.csv"]
    rev30 = sum(f(r["near_captured_revenue_usd"]) for r in win)
    vol30 = sum(f(r["intents_volume_usd"]) for r in win)
    fees30 = sum(f(r["intents_gross_fees_usd"]) or 0 for r in win)
    m.put("defillama_window", "%s to %s" % (win[0]["day"], win[-1]["day"]), "", "FACT", src, "30 complete days used")
    m.put("intents_volume_usd_per_day", vol30 / len(win), "USD/day", "FACT", src, "DefiLlama all-Intents volume, 30-day mean")
    m.put("near_captured_revenue_usd_per_year", rev30 / len(win) * 365, "USD/yr", "INFERENCE", src,
          "DefiLlama 'Revenue' (NEAR swept into revenue wallets), 30-day mean x 365")
    m.put("intents_gross_fees_usd_per_year", fees30 / len(win) * 365, "USD/yr", "INFERENCE", src, "DefiLlama gross fees, 30-day mean x 365")
    m.put("captured_revenue_take_bps", rev30 / vol30 * 1e4, "bps", "INFERENCE", src, "captured revenue / volume, same 30 days")
    m.put("captured_revenue_to_issuance_usd", rev30 / len(win) * 365 / (issuance * price), "ratio", "INFERENCE",
          src + ["data/market/near_chain_snapshot.json", "data/market/peers.csv"], "annualised captured revenue / issuance in USD")
    m.put("market_cap_to_captured_revenue", mcap / (rev30 / len(win) * 365), "x", "INFERENCE", src + ["data/market/peers.csv"],
          "market cap / annualised captured revenue")
    # The take-rate lever has a ceiling: NEAR cannot capture more than the gross fees users pay.
    gross_yr = fees30 / len(win) * 365
    m.put("intents_gross_fee_bps", fees30 / vol30 * 1e4, "bps", "INFERENCE", src, "DefiLlama gross fees / volume, same 30 days")
    m.put("captured_share_of_gross_fees", rev30 / fees30, "share", "INFERENCE", src,
          "captured revenue / gross fees, same 30 days (the rest goes to integrators and solvers)")
    m.put("gross_fees_to_issuance_usd", gross_yr / (issuance * price), "ratio", "INFERENCE",
          src + ["data/market/near_chain_snapshot.json", "data/market/peers.csv"],
          "CEILING: if NEAR captured 100% of today's gross fees, annualised / issuance in USD at 2.5%")
    m.put("gross_fees_to_issuance_usd_hsp029", gross_yr / (supply * HSP029_RATE * price), "ratio", "INFERENCE",
          src + ["data/market/near_chain_snapshot.json", "data/market/peers.csv"], "same against 1.6% issuance")
    m.put("break_even_take_bps", issuance * price / (vol30 / len(win) * 365) * 1e4, "bps", "INFERENCE",
          src + ["data/market/near_chain_snapshot.json", "data/market/peers.csv"],
          "take-rate on today's all-Intents volume at which captured revenue would equal 2.5% issuance in USD")
    m.put("break_even_take_bps_hsp029", supply * HSP029_RATE * price / (vol30 / len(win) * 365) * 1e4, "bps", "INFERENCE",
          src + ["data/market/near_chain_snapshot.json", "data/market/peers.csv"], "same at 1.6% issuance")

    daily = {r["day"]: f(r["usd_in_success"]) for r in m.csv("summary", "daily.csv")}
    vol = {r["day"]: f(r["intents_volume_usd"]) for r in ll}
    days = [d for d in sorted(daily) if d not in PARTIAL_OR_GAP_DAYS and vol.get(d)]
    ratios = [daily[d] / vol[d] for d in days]
    src = ["data/summary/daily.csv", "data/market/defillama_intents_daily.csv"]
    m.put("oneclick_share_of_intents_volume_median", st.median(ratios), "share", "FACT", src, "median daily 1Click USD / DefiLlama all-Intents USD")
    m.put("oneclick_vs_intents_daily_corr", corr([daily[d] for d in days], [vol[d] for d in days]), "r", "FACT", src,
          "Pearson correlation of daily levels, clean days")


# ----------------------------------------------------------------------------- buyback wallet
def wallet(m):
    w = [r for r in m.csv("onchain", "buyback_wallet_daily.csv") if f(r["native_near"]) is not None]
    src = ["data/onchain/buyback_wallet_daily.csv"]
    vals = [f(r["native_near"]) for r in w]
    start = next(i for i, v in enumerate(vals) if v > 1000) - 1
    rises = [vals[i + 1] > vals[i] for i in range(start, len(vals) - 1)]
    m.put("wallet_balance_near", vals[-1], "NEAR", "FACT", src, "native balance at the last weekly sample")
    m.put("wallet_balance_day", w[-1]["day"], "", "FACT", src, "date of that sample")
    m.put("wallet_weeks_rising", sum(rises), "weeks", "FACT", src, "weekly samples higher than the week before, since inflows began")
    m.put("wallet_weeks_total", len(rises), "weeks", "FACT", src, "weekly intervals since inflows began")

    q = m.csv("bq", "q30_buyback_balance_daily.csv")
    src = ["data/bq/q30_buyback_balance_daily.csv", "sql/q30_buyback_balance_daily.sql"]
    m.put("wallet_outflow_near_since_jul", sum(f(r["outflow_near"]) for r in q), "NEAR", "FACT", src, "sum of balance decreases, 1 Jul - 9 Nov")
    outs = [r["block_date"] for r in q if f(r["outflow_near"]) > 10]
    m.put("wallet_outflow_days_over_10_near", outs, "days", "FACT", src, "days with more than 10 NEAR leaving")
    m.put("wallet_max_staked_near", max(f(r["max_staked_near"]) or 0 for r in q), "NEAR", "FACT", src, "largest staked balance seen")
    steady = [f(r["inflow_near"]) for r in q if "2026-10-06" <= r["block_date"] <= "2026-11-08"]
    m.put("wallet_inflow_near_per_day", st.mean(steady), "NEAR/day", "FACT", src, "mean daily inflow 6 Oct - 8 Nov (5 full weeks, no one-off transfers)")
    s9 = m.csv("bq", "q33_buyback_sep09_moves.csv")
    m.put("wallet_sep09_treasury_transfer_near", sum(f(r["delta_near"]) for r in s9), "NEAR", "FACT",
          ["data/bq/q33_buyback_sep09_moves.csv"], "9 Sep inflow from a Trezu DAO 'Transfer' proposal (tx CMfn15uT...)")
    cp = m.csv("bq", "q32_buyback_counterparties.csv")
    ins = [r for r in cp if r["direction"] == "in"]
    m.put("wallet_inflows_from_intents_share", sum(int(r["actions"]) for r in ins if r["counterparty"] == "intents.near")
          / sum(int(r["actions"]) for r in ins), "share", "FACT", ["data/bq/q32_buyback_counterparties.csv"],
          "share of inbound receipts (1 Sep - 9 Nov) sent by intents.near")
    if "issuance_near_per_year" in m.out:
        yr = st.mean(steady) * 365
        m.put("wallet_inflow_share_of_issuance", yr / m.out["issuance_near_per_year"]["value"], "share", "INFERENCE",
              src + ["data/market/near_chain_snapshot.json"], "steady inflow x 365 / issuance NEAR/yr (no price needed)")
        m.put("wallet_inflow_share_of_issuance_hsp029", yr / m.out["issuance_near_per_year_hsp029"]["value"], "share",
              "INFERENCE", src, "same against 1.6% issuance")
        if "near_price_usd" in m.out:
            m.put("wallet_inflow_usd_per_year", yr * m.out["near_price_usd"]["value"], "USD/yr", "INFERENCE",
                  src + ["data/market/peers.csv"], "steady inflow x 365 x current price")


# ----------------------------------------------------------------------------- accounts (BigQuery)
def accounts(m):
    q10 = m.csv("bq", "q10_daily_signers_by_segment.csv")
    src = ["data/bq/q10_daily_signers_by_segment.csv", "sql/q10_daily_signers_by_segment.sql"]

    def month_mean(col, mon):
        return st.mean(int(r[col]) for r in q10 if r["block_date"].startswith(mon))
    last_month = q10[-1]["block_date"][:7]
    for key, mon in (("jan", "2026-01"), ("aug", "2026-08"), ("latest", last_month)):
        m.put("organic_signers_per_day_" + key, month_mean("organic_signers", mon), "accounts/day", "FACT", src,
              "mean daily organic signers in %s (sent >=1 tx to something other than game.hot.tg or itself; not *.users.kaiching)" % mon)
        m.put("game_signers_per_day_" + key, month_mean("game_signers", mon), "accounts/day", "FACT", src, "mean daily game.hot.tg signers in " + mon)
    m.put("organic_change_jan_to_aug", m.out["organic_signers_per_day_aug"]["value"] / m.out["organic_signers_per_day_jan"]["value"] - 1,
          "share", "FACT", src, "Aug mean / Jan mean - 1")
    m.put("organic_change_jan_to_latest", m.out["organic_signers_per_day_latest"]["value"] / m.out["organic_signers_per_day_jan"]["value"] - 1,
          "share", "FACT", src, "latest month mean / Jan mean - 1")
    months = sorted({r["block_date"][:7] for r in q10})
    monthly = [[mo, round(month_mean("organic_signers", mo))] for mo in months]
    m.put("organic_monthly", monthly, "accounts/day", "FACT", src, "mean daily organic signers per calendar month (last month partial)")
    full = monthly[:-1]  # the last month is partial
    m.put("organic_peak_month", max(full, key=lambda x: x[1])[0], "", "FACT", src, "complete month with the most organic signers")
    m.put("organic_trough_month", min(full, key=lambda x: x[1])[0], "", "FACT", src, "complete month with the fewest organic signers")
    # Who the organic signers are: account families (q10 splits them by name pattern)
    fam_cols = [("Telegram (.tg)", "organic_tg"), ("named .near", "organic_dot_near"),
                ("implicit (64-hex)", "organic_hex_implicit")]
    table = []
    for label, col in fam_cols:
        table.append([label] + [round(month_mean(col, mo)) for mo in ("2026-01", "2026-08", last_month)])
    tot = [round(month_mean("organic_signers", mo)) for mo in ("2026-01", "2026-08", last_month)]
    table.append(["other"] + [tot[i] - sum(r[i + 1] for r in table) for i in range(3)])
    m.put("organic_family_table", table, "accounts/day", "FACT", src,
          "mean daily organic signers by account family: January, August, latest month")
    tg = table[0]
    m.put("organic_tg_share_of_jan_to_aug_drop", (tg[1] - tg[2]) / (tot[0] - tot[1]), "share", "FACT", src,
          "Telegram (.tg) accounts' part of the January-to-August fall in organic signers")
    m.put("organic_tg_share_jan", tg[1] / tot[0], "share", "FACT", src, ".tg accounts' share of January organic signers")
    m.put("organic_ex_tg_change_jan_to_latest", (tot[2] - tg[3]) / (tot[0] - tg[1]) - 1, "share", "FACT", src,
          "organic signers excluding .tg accounts: latest month / January - 1")
    near = table[1]
    m.put("organic_dot_near_change_jan_to_latest", near[3] / near[1] - 1, "share", "FACT", src,
          "named .near organic signers: latest month / January - 1")
    m.put("organic_family_monthly", [[mo] + [round(month_mean(c, mo)) for _, c in fam_cols] for mo in months],
          "accounts/day", "FACT", src, "per month: .tg, .near, implicit hex organic signers")
    by = {r["block_date"]: r for r in q10}
    m.put("nov03_organic_hex", [int(by[d]["organic_hex_implicit"]) for d in ("2026-11-02", "2026-11-03", "2026-11-04")],
          "accounts/day", "FACT", src, "organic implicit-hex signers on 2, 3, 4 Nov")
    m.put("nov03_game_signers", [int(by[d]["game_signers"]) for d in ("2026-11-02", "2026-11-03", "2026-11-04")],
          "accounts/day", "FACT", src, "game.hot.tg signers on 2, 3, 4 Nov")

    q11 = m.csv("bq", "q11_real_active_weekly.csv")
    full = q11[1:-1]  # first and last weeks are partial
    src = ["data/bq/q11_real_active_weekly.csv", "sql/q11_real_active_weekly.sql"]
    jan = [int(r["l4_engaged_and_returning"]) for r in full if "2026-01-05" <= r["week"] <= "2026-01-26"]
    aug = [int(r["l4_engaged_and_returning"]) for r in full if "2026-08-03" <= r["week"] <= "2026-08-24"]
    last2 = [int(r["l4_engaged_and_returning"]) for r in full[-2:]]
    m.put("strict_weekly_active_jan", st.mean(jan), "accounts/week", "FACT", src, "mean L4 (engaged and returning) over January's full weeks")
    m.put("strict_weekly_active_aug", st.mean(aug), "accounts/week", "FACT", src, "mean L4 over August's full weeks")
    m.put("strict_weekly_active_latest", st.mean(last2), "accounts/week", "FACT", src, "mean L4 over the last 2 full weeks")
    peak = max(full, key=lambda r: int(r["l4_engaged_and_returning"]))
    m.put("strict_weekly_active_peak", [peak["week"], int(peak["l4_engaged_and_returning"])], "accounts/week", "FACT", src, "highest L4 week")

    q12 = m.csv("bq", "q12_retention_cohorts.csv")
    mid = [r for r in q12 if "2026-02-02" <= r["cohort"] <= "2026-08-31"]
    m.put("retention_next_week_median", st.median(int(r["active_week_1"]) / int(r["accounts"]) for r in mid), "share", "FACT",
          ["data/bq/q12_retention_cohorts.csv"], "median share of a weekly cohort active again the next week, Feb-Aug cohorts")
    m.put("retention_weeks_1_4_median", st.median(int(r["active_weeks_1_to_4"]) / int(r["accounts"]) for r in mid), "share", "FACT",
          ["data/bq/q12_retention_cohorts.csv"], "same, active at least once in weeks 1-4")

    q29 = m.csv("bq", "q29_self_only_bursts.csv")
    get = lambda b, fam: int(next(r["accounts"] for r in q29 if r["burst"] == b and r["account_family"] == fam))
    src = ["data/bq/q29_self_only_bursts.csv"]
    m.put("burst_feb_implicit_self_only", get("feb_2026", "(implicit_hex)"), "accounts", "FACT", src, "Feb 2026 implicit accounts that only sent txs to themselves")
    m.put("burst_oct_kaiching_self_only", get("oct_02_08", "users.kaiching"), "accounts", "FACT", src, "2-8 Oct *.users.kaiching self-only accounts")
    m.put("burst_nov03_implicit_self_only", get("nov_03", "(implicit_hex)"), "accounts", "FACT", src, "3 Nov implicit self-only accounts")

    q20 = m.csv("bq", "q20_oct27_senders.csv")
    r27 = [r for r in q20 if r["block_date"] == "2026-10-27"][0]
    src = ["data/bq/q20_oct27_senders.csv"]
    m.put("oct27_senders", int(r27["signers"]), "accounts", "FACT", src, "accounts sending to 282acb...47ef on 27 Oct")
    m.put("oct27_near_total", f(r27["deposit_near"]), "NEAR", "FACT", src, "NEAR attached in total")
    m.put("oct27_near_median", f(r27["median_deposit_near"]), "NEAR", "FACT", src, "median NEAR per transfer")
    q27 = m.csv("bq", "q27_oct27_senders_history.csv")
    never = sum(int(r["accounts"]) for r in q27 if not r["last_active_month_before_oct27"])
    m.put("oct27_senders_never_active_2026_share", never / int(q27[0]["senders_total"]), "share", "FACT",
          ["data/bq/q27_oct27_senders_history.csv"], "share of senders with no signed tx in 2026 before 27 Oct")
    q21 = m.csv("bq", "q21_oct27_target_balance.csv")
    r29 = [r for r in q21 if r["block_date"] == "2026-10-29"][0]
    m.put("oct27_target_outflow_oct29", f(r29["outflow_near"]), "NEAR", "FACT", ["data/bq/q21_oct27_target_balance.csv"],
          "NEAR leaving the address on 29 Oct")

    q26 = m.csv("bq", "q26_game_methods_daily.csv")
    cl = {r["block_date"]: int(r["callers"]) for r in q26 if r["method"] == "l2_claim"}
    m.put("game_claim_callers", [[d, cl[d]] for d in sorted(cl)], "accounts/day", "FACT",
          ["data/bq/q26_game_methods_daily.csv"], "distinct callers of game.hot.tg l2_claim on sample days")
    calls = [r for r in q26 if r["block_date"] == "2026-07-07"]
    m.put("game_claim_share_of_calls", sum(int(r["calls"]) for r in calls if r["method"] == "l2_claim") /
          sum(int(r["calls"]) for r in calls), "share", "FACT", ["data/bq/q26_game_methods_daily.csv"], "l2_claim share of game calls on 7 Jul")


# ----------------------------------------------------------------------------- the agent economy (pillar C)
AGENT_NAME_WORDS = ("agent", "bot", "claw", "outlayer")   # self-chosen referral names: evidence tier 4 only


def agents(m):
    """AI agents, measured only from identified sources.
    Tier 1: NEAR AI Agent Market's own public catalogue and platform totals (data/agents, pipeline/agent_market.py).
    Tier 4: 1Click referral codes whose self-chosen names mention agents or bots (a name proves nothing).
    Tier 3 (automation, not agents): the repeat-swapper share is in the swaps section."""
    js = m.json("agents", "agent_market_stats.json")
    st_ = js["stats"]
    src = ["data/agents/agent_market_stats.json"]
    m.put("agent_market_fetched_utc", js["fetched_utc"], "", "FACT", src, "time the Agent Market snapshot was taken")
    m.put("agent_market_live_agents", st_["live_agents"], "agents", "FACT", src, "/v1/platform/stats live_agents")
    m.put("agent_market_jobs_total", st_["jobs_total"], "jobs", "FACT", src, "/v1/platform/stats jobs_total (all time)")
    m.put("agent_market_jobs_this_week", st_["jobs_this_week"], "jobs", "FACT", src, "/v1/platform/stats jobs_this_week")
    m.put("agent_market_delivered_jobs", st_["delivered_jobs"], "jobs", "FACT", src, "/v1/platform/stats delivered_jobs (all time)")

    rows = m.csv("agents", "agent_market_agents.csv")
    src = ["data/agents/agent_market_agents.csv"]
    n = len(rows)
    dj = sorted((int(r["delivered_jobs"]) for r in rows), reverse=True)
    tot = sum(dj)
    m.put("agent_market_catalogue_agents", n, "agents", "FACT", src, "agents in the public catalogue (/v1/agents)")
    m.put("agent_market_agents_with_a_delivered_job", sum(1 for x in dj if x > 0), "agents", "FACT", src,
          "catalogue agents with at least one delivered job")
    m.put("agent_market_agents_with_a_delivered_job_share", sum(1 for x in dj if x > 0) / n, "share", "FACT", src, "same, as a share")
    m.put("agent_market_top10_share_of_delivered", sum(dj[:10]) / tot if tot else 0.0, "share", "FACT", src,
          "share of the catalogue's delivered jobs done by its 10 busiest agents")
    pay = [set((r["payable_with"] or "").split("+")) for r in rows]
    m.put("agent_market_agents_payable_in_near", sum(1 for p in pay if "NEAR" in p), "agents", "FACT", src,
          "catalogue agents that accept NEAR as payment")
    m.put("agent_market_agents_usdc_only", sum(1 for p in pay if p == {"USDC"}), "agents", "FACT", src, "accept USDC only")
    m.put("agent_market_agents_usd_and_usdc", sum(1 for p in pay if p == {"USD", "USDC"}), "agents", "FACT", src, "accept USD (card) or USDC")
    since = sum(1 for r in rows if r["created_day"] >= "2026-10-01")
    m.put("agent_market_listed_since_oct_share", since / n, "share", "FACT", src,
          "share of catalogue agents created on or after 1 Oct 2026 (the hackathon was announced 19 Oct)")
    months = sorted({r["created_day"][:7] for r in rows if r["created_day"]})
    m.put("agent_market_listed_by_month", [[mo, sum(1 for r in rows if r["created_day"].startswith(mo)),
                                            sum(1 for r in rows if r["created_day"].startswith(mo) and int(r["delivered_jobs"]) > 0)]
                                           for mo in months], "agents", "FACT", src,
          "per month: agents created, and how many of them have delivered at least one job")

    ch = m.csv("audit", "buyback_by_referral.csv")
    src = ["data/audit/buyback_by_referral.csv"]
    named = [r for r in ch if any(w in r["referral"].lower() for w in AGENT_NAME_WORDS)]
    tu = sum(f(r["usd_in_success"]) for r in ch)
    m.put("oneclick_agent_named_codes", sorted(r["referral"] for r in named), "", "FACT", src,
          "1Click referral codes whose names contain: " + ", ".join(AGENT_NAME_WORDS))
    m.put("oneclick_agent_named_usd", sum(f(r["usd_in_success"]) for r in named), "USD", "FACT", src,
          "their SUCCESS volume over the whole download")
    m.put("oneclick_agent_named_swaps", sum(int(r["success_swaps"]) for r in named), "swaps", "FACT", src, "their SUCCESS swaps")
    m.put("oneclick_agent_named_usd_share", sum(f(r["usd_in_success"]) for r in named) / tu, "share", "FACT", src,
          "their share of 1Click SUCCESS volume")

    # What would it take? Agent payments routed through Intents at today's captured take-rate.
    if "issuance_usd_per_year" in m.out and "captured_revenue_take_bps" in m.out:
        need = 0.10 * m.out["issuance_usd_per_year"]["value"] / (m.out["captured_revenue_take_bps"]["value"] / 1e4)
        m.put("agent_volume_for_10pct_of_issuance_usd_per_day", need / 365, "USD/day", "INFERENCE",
              ["data/derived/metrics.json"],
              "HYPOTHETICAL: agent payments per day routed through NEAR Intents, at today's captured take-rate, that would add "
              "captured revenue worth 10% of today's issuance in USD")


# ----------------------------------------------------------------------------- accrual: realised supply and all revenue wallets
REVENUE_WALLETS = ["buybacks.multisignature.near", "fefundsadmin.sputnik-dao.near", "1csfundsadmin.sputnik-dao.near"]


def chain(m):
    """Realised supply growth and the three revenue wallets, from weekly archival-RPC samples (pipeline/chain_history.py)."""
    cfg = m.json("onchain", "protocol_config.json")
    src = ["data/onchain/protocol_config.json"]
    m.put("protocol_config_read_utc", cfg["read_at_utc"], "", "FACT", src, "when the protocol parameters were read")
    m.put("burnt_gas_reward", cfg["burnt_gas_reward"], "share", "FACT", src,
          "runtime_config.transaction_costs.burnt_gas_reward: share of burnt gas paid to contracts (0 = all gas fees burned)")
    m.put("protocol_reward_rate_live", cfg["protocol_reward_rate"], "share", "FACT", src, "protocol_reward_rate (treasury cut of issuance)")

    rows = [r for r in m.csv("onchain", "chain_history.csv") if f(r["total_supply_near"])]
    src = ["data/onchain/chain_history.csv", "pipeline/chain_history.py"]
    a, b = rows[0], rows[-1]
    days = (date.fromisoformat(b["week_day"]) - date.fromisoformat(a["week_day"])).days
    s0, s1 = f(a["total_supply_near"]), f(b["total_supply_near"])
    m.put("supply_history_window", "%s to %s (%d days)" % (a["week_day"], b["week_day"], days), "", "FACT", src, "first and last weekly sample")
    m.put("realised_supply_growth", (s1 / s0 - 1) * 365 / days, "share", "FACT", src,
          "total_supply (block header) growth between the first and last sample, annualised: new NEAR minted minus NEAR burned")
    m.put("realised_new_near_per_year", (s1 - s0) * 365 / days, "NEAR/yr", "FACT", src, "same in NEAR per year")
    ceiling = st.mean([f(r["total_supply_near"]) for r in rows]) * m.out["max_inflation_rate"]["value"] * days / 365
    m.put("realised_vs_ceiling_issuance", (s1 - s0) / ceiling, "ratio", "INFERENCE", src + ["data/market/near_chain_snapshot.json"],
          "net supply added / (mean supply x max inflation rate x years): 1.0 = the maximum, all of it net of burns")

    bal = {w: [f(r[w]) for r in rows] for w in REVENUE_WALLETS}
    latest = {w: (bal[w][-1] or 0.0) for w in REVENUE_WALLETS}
    first = {w: (bal[w][0] or 0.0) for w in REVENUE_WALLETS}
    m.put("revenue_wallet_balances", [[w, round(first[w]), round(latest[w])] for w in REVENUE_WALLETS], "NEAR", "FACT", src,
          "native NEAR balance of each revenue wallet at the first and last weekly sample")
    m.put("fefunds_balance_near", latest["fefundsadmin.sputnik-dao.near"], "NEAR", "FACT", src,
          "fefundsadmin.sputnik-dao.near (front-end fund, a Sputnik DAO) at the last sample")
    fe = [x for x in bal["fefundsadmin.sputnik-dao.near"] if x is not None]
    drops = [(fe[i] - fe[i + 1]) for i in range(len(fe) - 1) if fe[i + 1] < fe[i] - 1]
    m.put("fefunds_weeks_falling", len(drops), "weeks", "FACT", src, "weekly samples where the front-end fund's balance fell by more than 1 NEAR")
    m.put("fefunds_largest_weekly_fall_near", max(drops) if drops else 0.0, "NEAR", "FACT", src, "its largest weekly fall")
    # The 1Click fund: where captured revenue went before the buyback wallet existed, and the 9 Sep transfer.
    oc = [(r["week_day"], f(r["1csfundsadmin.sputnik-dao.near"])) for r in rows if f(r["1csfundsadmin.sputnik-dao.near"]) is not None]
    peak = max(oc, key=lambda x: x[1])
    falls = [(oc[i + 1][0], oc[i][1] - oc[i + 1][1]) for i in range(len(oc) - 1)]
    big = max(falls, key=lambda x: x[1])
    m.put("onecs_peak_near", peak[1], "NEAR", "FACT", src, "highest weekly balance of 1csfundsadmin.sputnik-dao.near (the 1Click fund)")
    m.put("onecs_peak_week", peak[0], "", "FACT", src, "week of that peak")
    m.put("onecs_largest_fall_near", big[1], "NEAR", "FACT", src, "largest week-on-week fall in the 1Click fund's balance")
    m.put("onecs_largest_fall_week", big[0], "", "FACT", src, "the weekly sample right after that fall")
    if "wallet_sep09_treasury_transfer_near" in m.out:
        t = m.out["wallet_sep09_treasury_transfer_near"]["value"]
        m.put("onecs_fall_vs_sep09_transfer", abs(big[1] - t) / t, "share", "INFERENCE", src + ["data/bq/q33_buyback_sep09_moves.csv"],
              "|1Click fund's largest weekly fall - the 9 Sep transfer into the buyback wallet| / that transfer (0 = identical)")
    held = sum(latest.values())
    m.put("revenue_wallets_total_near", held, "NEAR", "FACT", src, "NEAR held across the three revenue wallets at the last sample")
    m.put("revenue_wallets_share_of_supply", held / s1, "share", "FACT", src, "same, as a share of total supply")
    added = held - sum(first.values())
    m.put("revenue_wallets_added_near_per_year", added * 365 / days, "NEAR/yr", "FACT", src,
          "growth of NEAR held across the three wallets between the samples, annualised (moves between the three wallets cancel out)")
    m.put("custody_share_of_realised_new_supply", added / (s1 - s0), "share", "INFERENCE", src,
          "NEAR added to the revenue wallets / net new NEAR supply, same days: the part of dilution parked in custody, if it stays there")


# ----------------------------------------------------------------------------- recent weekly trend and the August step-up
TREND_FROM = "2026-08-10"       # first Monday shown in the weekly table
INFLOW_FROM = "2026-09-14"      # buyback-wallet inflow is shown from this Monday on (the 9 Sep one-off transfer falls before it)
REFERENCE_WEEK = "2026-10-12"   # the week the NEAR price was near its autumn high
STEP_BEFORE = ("2026-08-01", "2026-08-14")   # the two weeks before the August volume step-up
STEP_AFTER = ("2026-08-19", "2026-08-25")    # the first week after it


def _monday(day):
    d = date.fromisoformat(day)
    return (d - timedelta(days=d.weekday())).isoformat()


def trend(m):
    ll = m.csv("market", "defillama_intents_daily.csv")
    px = {r["day"]: f(r["near_usd"]) for r in m.csv("market", "near_price_daily.csv")}
    inflow = {r["block_date"]: f(r["inflow_near"]) for r in m.csv("bq", "q30_buyback_balance_daily.csv")}
    src = ["data/market/defillama_intents_daily.csv", "data/market/near_price_daily.csv", "data/bq/q30_buyback_balance_daily.csv"]
    weeks = {}
    for r in ll:
        w = _monday(r["day"])
        if w < TREND_FROM:
            continue
        a = weeks.setdefault(w, {"days": 0, "vol": 0.0, "gross": 0.0, "cap": 0.0, "in_near": 0.0, "in_usd": 0.0, "in_days": 0, "px": []})
        a["days"] += 1
        a["vol"] += f(r["intents_volume_usd"])
        a["gross"] += f(r["intents_gross_fees_usd"]) or 0
        a["cap"] += f(r["near_captured_revenue_usd"]) or 0
        if r["day"] in px:
            a["px"].append(px[r["day"]])
        if w >= INFLOW_FROM and r["day"] in inflow and r["day"] in px:
            a["in_near"] += inflow[r["day"]]
            a["in_usd"] += inflow[r["day"]] * px[r["day"]]
            a["in_days"] += 1
    rows = []
    for w in sorted(weeks):
        a = weeks[w]
        rows.append([w, a["days"], round(a["vol"] / a["days"], 2), round(a["gross"] / a["vol"] * 1e4, 3),
                     round(a["cap"] / a["vol"] * 1e4, 3), round(a["cap"] / a["days"], 2),
                     round(a["in_near"] / a["in_days"], 2) if a["in_days"] else None,
                     round(st.mean(a["px"]), 4) if a["px"] else None,
                     round(a["in_usd"] / a["in_days"], 2) if a["in_days"] else None])
    m.put("trend_weekly", rows, "", "FACT", src,
          "per Monday-Sunday week: days in DefiLlama's data, all-Intents volume/day, gross-fee bps, captured take-rate bps, captured revenue/day, "
          "buyback-wallet inflow NEAR/day, mean NEAR price, inflow USD/day (inflow only from %s, because the 9 Sep one-off transfer is before it)" % INFLOW_FROM)
    full = [r for r in rows if r[1] == 7]
    by = {r[0]: r for r in rows}
    ref, last_full = by[REFERENCE_WEEK], full[-1]
    since = [r for r in full if r[0] >= INFLOW_FROM]
    peak = max(since, key=lambda r: r[4])
    m.put("trend_reference_week", REFERENCE_WEEK, "", "FACT", src, "week used as the 'autumn high' reference (the week of the NEAR price peak)")
    m.put("trend_latest_full_week", last_full[0], "", "FACT", src, "latest week with all seven days in DefiLlama's data")
    m.put("trend_take_bps_reference_week", ref[4], "bps", "FACT", src, "captured revenue / all-Intents volume in the reference week")
    m.put("trend_take_bps_latest_full_week", last_full[4], "bps", "FACT", src, "same in the latest full week")
    m.put("trend_take_bps_peak_week", peak[4], "bps", "FACT", src, "highest weekly take-rate among full weeks from %s" % INFLOW_FROM)
    m.put("trend_take_bps_peak_week_label", peak[0], "", "FACT", src, "its week")
    partial = [r for r in rows if r[1] < 7]
    if partial:
        m.put("trend_partial_week", [partial[-1][0], partial[-1][1], partial[-1][4]], "", "FACT", src,
              "the newest, incomplete week: start, days, take-rate bps (DefiLlama's last 1-2 days are often revised)")
    last_day = max(px)
    m.put("trend_price_reference_day", px[REFERENCE_WEEK], "USD", "FACT", src, "NEAR price on the reference Monday")
    m.put("trend_price_last", px[last_day], "USD", "FACT", src, "newest NEAR price in the daily table")
    m.put("trend_price_last_day", last_day, "", "FACT", src, "its date")
    m.put("trend_price_change", px[last_day] / px[REFERENCE_WEEK] - 1, "share", "FACT", src, "newest price / reference-Monday price - 1")
    m.put("trend_inflow_near_reference_week", ref[6], "NEAR/day", "FACT", src, "buyback-wallet inflow, reference week")
    m.put("trend_inflow_near_latest_full_week", last_full[6], "NEAR/day", "FACT", src, "same, latest full week")
    m.put("trend_inflow_usd_reference_week", ref[8], "USD/day", "FACT", src, "inflow x each day's price, reference week")
    m.put("trend_inflow_usd_latest_full_week", last_full[8], "USD/day", "FACT", src, "same, latest full week")
    m.put("trend_inflow_usd_change", last_full[8] / ref[8] - 1, "share", "FACT", src, "latest full week / reference week - 1")
    m.put("trend_captured_usd_per_day_reference_week", ref[5], "USD/day", "FACT", src, "DefiLlama captured revenue/day, reference week")
    m.put("trend_captured_usd_per_day_latest_full_week", last_full[5], "USD/day", "FACT", src, "same, latest full week")

    # the August step-up: what the daily series shows, and nothing about its cause
    vol = {r["day"]: f(r["intents_volume_usd"]) for r in ll}
    gross = {r["day"]: f(r["intents_gross_fees_usd"]) or 0 for r in ll}
    span = lambda a, b: [d for d in sorted(vol) if a <= d <= b]
    pre, post = span(*STEP_BEFORE), span(*STEP_AFTER)
    m.put("stepup_before_window", "%s to %s" % STEP_BEFORE, "", "FACT", src[:1], "window before the step-up")
    m.put("stepup_after_window", "%s to %s" % STEP_AFTER, "", "FACT", src[:1], "window after the step-up")
    m.put("stepup_before_usd_per_day", st.mean(vol[d] for d in pre), "USD/day", "FACT", src[:1], "mean all-Intents volume before")
    m.put("stepup_after_usd_per_day", st.mean(vol[d] for d in post), "USD/day", "FACT", src[:1], "mean all-Intents volume after")
    m.put("stepup_before_gross_bps", sum(gross[d] for d in pre) / sum(vol[d] for d in pre) * 1e4, "bps", "FACT", src[:1], "gross fees / volume before")
    m.put("stepup_after_gross_bps", sum(gross[d] for d in post) / sum(vol[d] for d in post) * 1e4, "bps", "FACT", src[:1], "gross fees / volume after")
    m.put("stepup_aug19_usd", vol["2026-08-19"], "USD", "FACT", src[:1], "volume on 19 Aug")
    m.put("stepup_aug21_usd", vol["2026-08-21"], "USD", "FACT", src[:1], "volume on 21 Aug")
    jan = [vol[d] for d in span("2026-01-01", "2026-01-31")]
    m.put("jan_avg_usd_per_day", st.mean(jan), "USD/day", "FACT", src[:1], "mean all-Intents volume in January 2026")
    m.put("before_step_vs_jan", st.mean(vol[d] for d in pre) / st.mean(jan) - 1, "share", "FACT", src[:1], "pre-step mean / January mean - 1")
    if "intents_volume_usd_per_day" in m.out:
        m.put("recent_vs_jan", m.out["intents_volume_usd_per_day"]["value"] / st.mean(jan) - 1, "share", "FACT", src[:1],
              "latest 30-day mean / January mean - 1")


# ----------------------------------------------------------------------------- fee-layer reconciliation (four full weeks)
RECON_WEEKS = ("2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02")   # Monday-Sunday weeks, 12 Oct - 8 Nov
BUYBACK_RECIPIENT = "buybacks.multisignature.near"


def reconcile(m):
    ll = m.csv("market", "defillama_intents_daily.csv")
    oc = m.csv("summary", "daily.csv")
    af = m.csv("summary", "app_fees_weekly.csv")
    src = ["data/market/defillama_intents_daily.csv", "data/summary/daily.csv", "data/summary/app_fees_weekly.csv"]
    days = [d for w in RECON_WEEKS for d in [(date.fromisoformat(w) + timedelta(days=i)).isoformat() for i in range(7)]]
    dayset = set(days)
    n = len(days)
    pick = lambda rows, key, col: sum(f(r[col]) or 0 for r in rows if r[key] in dayset)
    allv = pick(ll, "day", "intents_volume_usd")
    gross = pick(ll, "day", "intents_gross_fees_usd")
    cap = pick(ll, "day", "near_captured_revenue_usd")
    ocv = pick(oc, "day", "usd_in_success")
    wk_af = [r for r in af if r["week_start_monday"] in RECON_WEEKS]
    appfees = sum(f(r["est_fee_usd_if_fee_is_basis_points"]) or 0 for r in wk_af)
    bb = sum(f(r["est_fee_usd_if_fee_is_basis_points"]) or 0 for r in wk_af if r["fee_recipient"] == BUYBACK_RECIPIENT)
    yr = 365.0 / n
    m.put("recon_window", "%s to %s (%d days, four full weeks)" % (days[0], days[-1], n), "", "FACT", src,
          "Monday-Sunday weeks, because the 1Click app-fee table is weekly")
    m.put("recon_allintents_usd_per_day", allv / n, "USD/day", "FACT", src[:1], "(1) DefiLlama all-Intents volume")
    m.put("recon_oneclick_usd_per_day", ocv / n, "USD/day", "FACT", src[1:2], "(2) 1Click SUCCESS volume, same days (source-API gap hours are not added back)")
    m.put("recon_oneclick_share_of_volume", ocv / allv, "share", "FACT", src[:2], "(2) / (1)")
    m.put("recon_gross_usd_per_year", gross * yr, "USD/yr", "FACT", src[:1], "(3) DefiLlama gross fees, annualised from this window")
    m.put("recon_gross_bps", gross / allv * 1e4, "bps", "FACT", src[:1], "(3) / (1)")
    m.put("recon_appfees_usd_per_year", appfees * yr, "USD/yr", "INFERENCE", src[2:], "(4) 1Click partner-set appFees: sum of fee x amountInUsd, annualised (assumes the fee field is in basis points)")
    m.put("recon_appfees_bps_on_oneclick", appfees / ocv * 1e4, "bps", "INFERENCE", src[1:], "(4) / (2)")
    m.put("recon_appfees_share_of_gross", appfees / gross, "share", "INFERENCE", src, "(4) / (3): different scopes, see THESIS.md")
    m.put("recon_gross_bps_outside_oneclick", (gross - appfees) / (allv - ocv) * 1e4, "bps", "INFERENCE", src,
          "((3) - (4)) / ((1) - (2)); assumes DefiLlama's gross fees include all 1Click app fees, which is not verified")
    m.put("recon_buyback_usd_per_year", bb * yr, "USD/yr", "INFERENCE", src[2:], "(6) appFees paid to the buyback wallet, annualised")
    m.put("recon_buyback_share_of_appfees", bb / appfees, "share", "INFERENCE", src[2:], "(6) / (4), this window")
    m.put("recon_captured_usd_per_year", cap * yr, "USD/yr", "INFERENCE", src[:1], "(8c) DefiLlama captured revenue, annualised from this window")
    m.put("recon_captured_share_of_gross", cap / gross, "share", "INFERENCE", src[:1], "(8c) / (3)")
    m.put("recon_buyback_share_of_captured", bb / cap, "share", "INFERENCE", src, "(6) / (8c)")
    m.put("recon_other_captured_usd_per_year", (cap - bb) * yr, "USD/yr", "INFERENCE", src, "(8c) - (6): captured revenue with no swap-level attribution here")
    m.put("recon_other_captured_share", (cap - bb) / cap, "share", "INFERENCE", src, "1 - (6)/(8c)")
    tot = {}
    for r in af:
        tot[r["fee_recipient"]] = tot.get(r["fee_recipient"], 0.0) + (f(r["est_fee_usd_if_fee_is_basis_points"]) or 0)
    grand = sum(tot.values())
    top = sorted(tot.items(), key=lambda kv: -kv[1])
    m.put("recon_allfile_appfees_usd", grand, "USD", "INFERENCE", src[2:], "all weeks in the 1Click download (from 28 Sep), est. appFees")
    m.put("recon_allfile_buyback_share_of_appfees", tot.get(BUYBACK_RECIPIENT, 0.0) / grand, "share", "INFERENCE", src[2:],
          "buyback-wallet share of all est. appFees over the whole download")
    m.put("recon_allfile_top_recipient", top[0][0], "", "FACT", src[2:], "recipient with the most est. appFees over the whole download")
    m.put("recon_allfile_top_recipient_share", top[0][1] / grand, "share", "INFERENCE", src[2:], "its share")
    m.put("recon_allfile_top3_recipient_share", sum(v for _, v in top[:3]) / grand, "share", "INFERENCE", src[2:], "share of the top three recipients")


# ----------------------------------------------------------------------------- additional source-gap candidates
ANOMALY_SHARE = 0.25        # an hour is flagged when it holds less than this share of its hour-of-day median
SUBHOUR_MIN_SECONDS = 600   # list gaps between consecutive swaps of 10 minutes or more


def gaps_extra(m):
    cnt = {r["hour_utc"]: int(r["swaps_all_status"]) for r in m.csv("audit", "hourly_counts.csv")}
    confirmed = m.csv("audit", "gap_check.csv")
    largest = m.csv("audit", "integrity_largest_gaps.csv")
    src = ["data/audit/hourly_counts.csv", "data/audit/gap_check.csv", "data/audit/integrity_largest_gaps.csv"]
    first, last = datetime.fromisoformat(min(cnt)), datetime.fromisoformat(max(cnt))
    grid, t = [], first + timedelta(hours=1)          # the first and last hours of the download are partial: dropped
    while t < last:
        grid.append(t)
        t += timedelta(hours=1)
    key = lambda x: x.strftime("%Y-%m-%d %H:%M")
    by_hour = {}
    for t in grid:
        by_hour.setdefault(t.hour, []).append(cnt.get(key(t), 0))    # an hour with no rows at all counts as zero
    med = {h: st.median(v) for h, v in by_hour.items()}
    flagged = [t for t in grid if cnt.get(key(t), 0) < ANOMALY_SHARE * med[t.hour]]
    win = [(datetime.fromisoformat(g["gap_start_utc"]), datetime.fromisoformat(g["gap_end_utc"])) for g in confirmed]
    in_confirmed = lambda a, b: any(s.replace(tzinfo=None) < b and e.replace(tzinfo=None) > a for s, e in win)
    groups, cur = [], []
    for t in flagged:
        if cur and t - cur[-1] == timedelta(hours=1):
            cur.append(t)
        else:
            if cur:
                groups.append(cur)
            cur = [t]
    if cur:
        groups.append(cur)
    hourly = []
    for g in groups:
        a, b = g[0], g[-1] + timedelta(hours=1)
        hourly.append([key(a), key(b), len(g), sum(cnt.get(key(x), 0) for x in g), int(sum(med[x.hour] for x in g)),
                       "confirmed: the API has no rows here" if in_confirmed(a, b) else "UNCONFIRMED: not re-queried"])
    m.put("hourly_anomaly_rule", "an hour is flagged when it holds fewer than %d%% of the median count for the same UTC hour of day across the download; "
          "hours with no rows count as zero; the first and last (partial) hours are not tested" % int(ANOMALY_SHARE * 100), "", "FACT", src[:1], "rule")
    m.put("hourly_anomaly_table", hourly, "", "INFERENCE", src, "flagged runs of hours: start, end, hours, swaps seen, swaps expected, status")
    m.put("hourly_anomaly_unconfirmed", sum(1 for r in hourly if r[5].startswith("UNCONFIRMED")), "runs", "INFERENCE", src, "flagged runs not confirmed as API gaps")
    conf_starts = {datetime.fromisoformat(g["gap_start_utc"]).replace(tzinfo=None) for g in confirmed}
    sub = []
    for r in largest:
        secs = int(r["gap_seconds"])
        if secs < SUBHOUR_MIN_SECONDS:
            continue
        start = datetime.fromisoformat(r["gap_starts_utc"]).replace(tzinfo=None)
        is_conf = any(abs((start - c).total_seconds()) < 2 for c in conf_starts)
        exp = secs / 3600.0 * med.get(start.hour, 0)
        sub.append([start.strftime("%Y-%m-%d %H:%M"), round(secs / 60.0, 1), "confirmed: the API has no rows here" if is_conf else "UNCONFIRMED: not re-queried",
                    int(round(exp))])
    m.put("extra_gap_table", sub, "", "INFERENCE", src, "gaps of 10+ minutes between consecutive swaps: start (UTC), minutes, status, swaps expected at the typical rate")
    un = [r for r in sub if r[2].startswith("UNCONFIRMED")]
    m.put("extra_gap_count", len(un), "gaps", "INFERENCE", src[1:], "unconfirmed gaps of 10+ minutes in the largest-gaps file")
    m.put("extra_gap_hours", sum(r[1] for r in un) / 60.0, "hours", "INFERENCE", src[1:], "their total length")
    total_swaps = sum(cnt.get(key(t), 0) for t in grid)
    m.put("extra_gap_expected_missing_swaps", sum(r[3] for r in un), "swaps", "INFERENCE", src,
          "swaps expected inside those gaps at the median rate for their hour of day (an estimate, not a count)")
    m.put("extra_gap_expected_missing_share", sum(r[3] for r in un) / total_swaps, "share", "INFERENCE", src,
          "that estimate / swaps in the hours tested")
    m.put("extra_gap_listed_floor_minutes", min(r[1] for r in sub) if sub else 0.0, "minutes", "FACT", src[2:],
          "the largest-gaps file keeps only the 15 largest gaps, so gaps shorter than this are not visible")


# ----------------------------------------------------------------------------- other native cross-chain swap venues
CROSSCHAIN = [("near_intents_usd", "NEAR Intents"), ("thorchain_usd", "THORChain"), ("chainflip_usd", "Chainflip")]


def crosschain(m):
    rows = m.csv("market", "crosschain_peers_daily.csv")
    meta = m.json("market", "_fetched_crosschain.json")
    src = ["data/market/crosschain_peers_daily.csv", "data/market/_fetched_crosschain.json", "pipeline/fetch_crosschain.py"]
    cols = [c for c, _ in CROSSCHAIN]
    full = [r for r in rows if all(f(r[c]) is not None for c in cols)]     # days on which all three venues have a value
    a, b = m.out["defillama_window"]["value"].split(" to ")                 # the same 30 days as every other DefiLlama figure
    how = "DefiLlama DEX-volume adapters, one per venue; each counts volume its own way, so this is a share of these three venues, not of a market"

    def span(lo, hi):
        sel = [r for r in full if lo <= r["day"] <= hi]
        return sel, {c: sum(f(r[c]) for r in sel) for c in cols}

    win, tot = span(a, b)
    three = sum(tot.values())
    m.put("crosschain_window", "%s to %s (%d days)" % (a, b, len(win)), "", "FACT", src[:1], "the 30-day DefiLlama window used throughout")
    m.put("crosschain_fetched_utc", meta["fetched_utc"], "", "FACT", src[1:2], "when the three series were read")
    for c, label in CROSSCHAIN:
        short = c[:-4]
        m.put("crosschain_%s_usd_per_day" % short, tot[c] / len(win), "USD/day", "FACT", src[:1], "%s mean daily volume in the window" % label)
        m.put("crosschain_%s_share_of_three" % short, tot[c] / three, "share", "INFERENCE", src[:1], "%s / sum of the three, in the window; %s" % (label, how))
        m.put("crosschain_alltime_%s_usd" % short, meta["venues"][c]["all_time_usd"], "USD", "FACT", src[1:2],
              "DefiLlama's all-time total for %s at fetch time (its series starts %s)" % (label, meta["venues"][c]["first_day"]))
    m.put("crosschain_intents_vs_thorchain", tot["near_intents_usd"] / tot["thorchain_usd"], "ratio", "INFERENCE", src[:1], "NEAR Intents / THORChain volume in the window")
    m.put("crosschain_alltime_thorchain_vs_intents", meta["venues"]["thorchain_usd"]["all_time_usd"] / meta["venues"]["near_intents_usd"]["all_time_usd"],
          "ratio", "INFERENCE", src[1:2], "THORChain all-time volume / NEAR Intents all-time volume (THORChain's series is older)")
    pinned = {r["day"]: f(r["intents_volume_usd"]) for r in m.csv("market", "defillama_intents_daily.csv")}
    m.put("crosschain_intents_vs_pinned", tot["near_intents_usd"] / sum(pinned[r["day"]] for r in win), "ratio", "FACT",
          src[:1] + ["data/market/defillama_intents_daily.csv"],
          "NEAR Intents volume in this table (read 14 Nov) / the same days in the table pinned on 11 Nov; 1.00 means DefiLlama did not revise them")
    jan, jtot = span("2026-01-01", "2026-01-31")
    m.put("crosschain_jan_near_intents_share_of_three", jtot["near_intents_usd"] / sum(jtot.values()), "share", "INFERENCE", src[:1],
          "NEAR Intents / sum of the three, January 2026")
    ytd, ytot = span("2026-01-01", b)
    m.put("crosschain_ytd_window", "2026-01-01 to %s" % b, "", "FACT", src[:1], "year to the end of the 30-day window")
    m.put("crosschain_ytd_near_intents_share_of_three", ytot["near_intents_usd"] / sum(ytot.values()), "share", "INFERENCE", src[:1],
          "NEAR Intents / sum of the three, 1 Jan 2026 to the end of the window")
    # the newest 7 complete days (DefiLlama's last 1-2 days are often revised, so stop 2 days before the newest full row)
    last_ok = (date.fromisoformat(full[-1]["day"]) - timedelta(days=2)).isoformat()
    l7, ltot = span((date.fromisoformat(last_ok) - timedelta(days=6)).isoformat(), last_ok)
    lead = max(CROSSCHAIN, key=lambda cl: ltot[cl[0]])[1]
    m.put("crosschain_latest7_window", "%s to %s" % (l7[0]["day"], l7[-1]["day"]), "", "FACT", src[:1], "newest 7 days, ending 2 days before the newest full row")
    m.put("crosschain_latest7_near_intents_share_of_three", ltot["near_intents_usd"] / sum(ltot.values()), "share", "INFERENCE", src[:1],
          "NEAR Intents / sum of the three in those 7 days")
    m.put("crosschain_latest7_leader", lead, "", "FACT", src[:1], "venue with the most volume in those 7 days")
    weeks = {}
    for r in full:
        if r["day"] <= last_ok:
            weeks.setdefault(_monday(r["day"]), []).append(r)
    table = []
    for w in sorted(weeks):
        if len(weeks[w]) != 7:
            continue
        s = [sum(f(r[c]) for r in weeks[w]) for c in cols]
        table.append([w] + [round(x / 7.0, 2) for x in s] + [round(s[0] / sum(s), 4)])
    m.put("crosschain_weekly", table, "", "FACT", src[:1],
          "full Monday-Sunday weeks of 2026: week, NEAR Intents, THORChain and Chainflip volume per day, NEAR Intents share of the three")
    m.put("crosschain_weeks_total", len(table), "weeks", "FACT", src[:1], "full weeks in that table")
    m.put("crosschain_weeks_intents_largest", sum(1 for r in table if r[1] > r[2] and r[1] > r[3]), "weeks", "FACT", src[:1],
          "weeks in which NEAR Intents had the most volume of the three")
    m.put("crosschain_weeks_intents_largest_last12", sum(1 for r in table[-12:] if r[1] > r[2] and r[1] > r[3]), "weeks", "FACT", src[:1],
          "same, among the newest 12 full weeks")


# ----------------------------------------------------------------------------- 1Click around the confidential-settlement switch
CONFIDENTIAL_FROM = "2026-10-27"   # docs changelog: from this day 1Click swaps settle confidentially (typed fact, THESIS.md section 12)


def confidential(m):
    daily = [r for r in m.csv("summary", "daily.csv") if r["day"] not in PARTIAL_OR_GAP_DAYS]
    src = ["data/summary/daily.csv"]
    d0 = date.fromisoformat(CONFIDENTIAL_FROM)
    before = [r for r in daily if d0 - timedelta(days=14) <= date.fromisoformat(r["day"]) < d0]
    after = [r for r in daily if d0 <= date.fromisoformat(r["day"]) < d0 + timedelta(days=14)]
    how = "clean full days only (days with source-API gaps are left out)"
    m.put("confidential_switch_day", CONFIDENTIAL_FROM, "", "FACT", src, "first day on which 1Click swaps settle confidentially, per the docs changelog")
    m.put("confidential_days_before", len(before), "days", "FACT", src, "clean days in the 14 days before the switch")
    m.put("confidential_days_after", len(after), "days", "FACT", src, "clean days in the 14 days from the switch (the download ends 10 Nov)")
    sb, sa = st.mean(f(r["swaps_success"]) for r in before), st.mean(f(r["swaps_success"]) for r in after)
    ub, ua = st.mean(f(r["usd_in_success"]) for r in before), st.mean(f(r["usd_in_success"]) for r in after)
    m.put("oneclick_swaps_per_day_before_switch", sb, "swaps/day", "FACT", src, "mean SUCCESS swaps per day, 14 days before the switch; " + how)
    m.put("oneclick_swaps_per_day_after_switch", sa, "swaps/day", "FACT", src, "same, from the switch")
    m.put("oneclick_swaps_after_vs_before_switch", sa / sb, "ratio", "FACT", src, "after / before")
    m.put("oneclick_usd_per_day_before_switch", ub, "USD/day", "FACT", src, "mean SUCCESS amountInUsd per day, 14 days before the switch; " + how)
    m.put("oneclick_usd_per_day_after_switch", ua, "USD/day", "FACT", src, "same, from the switch")
    m.put("oneclick_usd_after_vs_before_switch", ua / ub, "ratio", "FACT", src, "after / before")


def run(data):
    import models
    m = Metrics(data)
    yaml_path = os.path.join(os.path.dirname(os.path.abspath(data)), "thesis.yaml")
    for name, fn in (("swaps", swaps), ("audit", audit), ("channels", channels), ("market", market), ("wallet", wallet), ("trend", trend), ("reconcile", reconcile), ("gaps_extra", gaps_extra), ("crosschain", crosschain), ("confidential", confidential), ("accounts", accounts), ("agents", agents), ("chain", chain),
                     ("extra", models.extra), ("windows", models.windows), ("sensitivity", models.sensitivity),
                     ("leadlag", models.leadlag),
                     ("scenarios", lambda mm: models.scenarios(mm, os.path.join(os.path.dirname(os.path.abspath(data)), "scenarios.json"))),
                     ("scorecard", lambda mm: models.scorecard(mm, yaml_path))):
        m.section(name, fn)
    os.makedirs(os.path.join(data, "derived"), exist_ok=True)
    doc = {"generated_from": "pinned snapshot tables in data/ (see data/MANIFEST.json)",
           "metrics": m.out, "not_computed": m.missing}
    with open(os.path.join(data, "derived", "metrics.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2)
    print("metrics: %d computed, %d sections not computed" % (len(m.out), len(m.missing)))
    return doc


def main():
    ap = argparse.ArgumentParser(description="Compute headline metrics from snapshot tables.")
    ap.add_argument("--data", default="data")
    run(ap.parse_args().data)


if __name__ == "__main__":
    main()

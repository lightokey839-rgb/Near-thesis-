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


def run(data):
    import models
    m = Metrics(data)
    yaml_path = os.path.join(os.path.dirname(os.path.abspath(data)), "thesis.yaml")
    for name, fn in (("swaps", swaps), ("audit", audit), ("market", market), ("wallet", wallet), ("accounts", accounts),
                     ("extra", models.extra), ("sensitivity", models.sensitivity), ("leadlag", models.leadlag),
                     ("scorecard", lambda mm: models.scorecard(mm, yaml_path))):
        m.section(name, fn)
    os.makedirs(os.path.join(data, "derived"), exist_ok=True)
    doc = {"generated_from": "pinned snapshot tables in data/ (see data/MANIFEST.json)",
           "metrics": m.out, "not_computed": m.missing}
    with open(os.path.join(data, "derived", "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    print("metrics: %d computed, %d sections not computed" % (len(m.out), len(m.missing)))
    return doc


def main():
    ap = argparse.ArgumentParser(description="Compute headline metrics from snapshot tables.")
    ap.add_argument("--data", default="data")
    run(ap.parse_args().data)


if __name__ == "__main__":
    main()

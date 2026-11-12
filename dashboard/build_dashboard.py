#!/usr/bin/env python3
"""
build_dashboard.py - write dashboard/index.html from the pinned snapshot tables.

Every chart shows: a title, one plain sentence, the chart, whether it is FACT or
INFERENCE, the source files, and (in a fold-out) the exact query or code behind it:
the SQL file for BigQuery charts, the Python function for everything else.

Standard library only. Chart.js 4.4.1 is loaded from cdnjs in the browser.
Usage:  python dashboard/build_dashboard.py [--data data] [--out dashboard/index.html]
"""

import argparse
import csv
import html
import inspect
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from render import fmt_value  # noqa: E402  (same number style as THESIS.md)
GAP_DAYS = {"2026-10-01", "2026-10-20", "2026-11-02"}
PARTIAL = {"2026-09-28", "2026-11-10"}
COLORS = ["#2f6fde", "#e07b28", "#1a9e8f", "#8a5cd1", "#d64545", "#8a8f98"]


def rd(data, *p):
    with open(os.path.join(data, *p), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sql_meta(name):
    with open(os.path.join(ROOT, "sql", name + ".sql"), encoding="utf-8") as f:
        text = f.read()
    meta = dict(re.findall(r"^--\s*(title|sentence):\s*(.+)$", text, flags=re.M))
    return text, meta


def line(labels, series, y_title="", log=False, y2=None):
    ds = []
    for i, (name, vals) in enumerate(series):
        d = {"label": name, "data": vals, "borderColor": COLORS[i % 6], "backgroundColor": COLORS[i % 6],
             "pointRadius": 0, "borderWidth": 2, "tension": 0.15, "spanGaps": True}
        if y2 and name in y2:
            d["yAxisID"] = "y2"
        ds.append(d)
    scales = {"y": {"type": "logarithmic" if log else "linear", "title": {"display": bool(y_title), "text": y_title}}}
    if y2:
        scales["y2"] = {"position": "right", "grid": {"drawOnChartArea": False}, "title": {"display": True, "text": y2[list(y2)[0]]}}
    return {"type": "line", "data": {"labels": labels, "datasets": ds}, "options": {"scales": scales}}


def bar(labels, series, y_title="", stacked=False, horizontal=False):
    ds = [{"label": n, "data": v, "backgroundColor": COLORS[i % 6]} for i, (n, v) in enumerate(series)]
    opts = {"scales": {"x": {"stacked": stacked}, "y": {"stacked": stacked, "title": {"display": bool(y_title), "text": y_title}}}}
    if horizontal:
        opts["indexAxis"] = "y"
    return {"type": "bar", "data": {"labels": labels, "datasets": ds}, "options": opts}


# ----------------------------------------------------------------------------- chart series
# Each function returns (chart_config, source_files). Its source code is shown under the chart.

def s_volume(data):
    ours = {r["day"]: float(r["usd_in_success"]) for r in rd(data, "summary", "daily.csv") if r["day"] not in PARTIAL}
    ll = {r["day"]: float(r["intents_volume_usd"] or 0) for r in rd(data, "market", "defillama_intents_daily.csv")}
    days = sorted(ours)
    return line(days, [("1Click swaps (our download, SUCCESS)", [round(ours[d] / 1e6, 2) for d in days]),
                       ("All NEAR Intents (DefiLlama)", [round(ll.get(d, 0) / 1e6, 2) or None for d in days])], "USD millions per day"), \
        ["data/summary/daily.csv", "data/market/defillama_intents_daily.csv"]


def s_sizes(data):
    order = ["lt_1", "1_10", "10_100", "100_1k", "1k_10k", "gte_10k"]
    cnt, usd = dict.fromkeys(order, 0), dict.fromkeys(order, 0.0)
    for r in rd(data, "summary", "size_buckets_daily.csv"):
        cnt[r["swap_size_usd_bucket"]] += int(r["swaps_success"])
        usd[r["swap_size_usd_bucket"]] += float(r["usd_in_success"])
    tc, tu = sum(cnt.values()), sum(usd.values())
    labels = ["< $1", "$1-10", "$10-100", "$100-1k", "$1k-10k", ">= $10k"]
    return bar(labels, [("% of swaps", [round(100 * cnt[k] / tc, 2) for k in order]),
                        ("% of USD volume", [round(100 * usd[k] / tu, 2) for k in order])], "%"), \
        ["data/summary/size_buckets_daily.csv"]


def s_referrals(data):
    tot = {}
    for r in rd(data, "summary", "referrals_weekly.csv"):
        tot[r["referral"]] = tot.get(r["referral"], 0) + float(r["usd_in_success"])
    s = sum(tot.values())
    top = sorted(tot.items(), key=lambda kv: -kv[1])[:10]
    return bar([k for k, _ in top], [("% of 1Click USD volume", [round(100 * v / s, 2) for _, v in top])], "%", horizontal=True), \
        ["data/summary/referrals_weekly.csv"]


def s_refunds(data):
    rows = rd(data, "audit", "refunds_by_day_reason.csv")
    rows = [r for r in rows if r["day"] not in PARTIAL]
    isf = [round(100 * int(r.get("reason_INTENT_SUBMIT_FAILED", 0)) / int(r["swaps_all_status"]), 2) for r in rows]
    other = [round(100 * float(r["refund_rate"]) - a, 2) for r, a in zip(rows, isf)]
    return bar([r["day"] for r in rows], [("INTENT_SUBMIT_FAILED", isf), ("all other refund reasons", other)],
               "% of all swaps that day", stacked=True), ["data/audit/refunds_by_day_reason.csv"]


def s_feeunit(data):
    pts = [(float(r["sum_of_appFees_fee"]), float(r["haircut_bps_median"])) for r in rd(data, "audit", "fee_unit_test_stable_pairs.csv")
           if int(r["swaps"]) >= 200]
    mx = max(p[0] for p in pts)
    cfg = {"type": "scatter", "data": {"datasets": [
        {"label": "fee groups (200+ stablecoin swaps each)", "data": [{"x": x, "y": y} for x, y in pts], "backgroundColor": COLORS[0]},
        {"label": "if fee = basis points (y = x)", "data": [{"x": 0, "y": 0}, {"x": mx, "y": mx}], "type": "line",
         "borderColor": COLORS[5], "borderDash": [6, 4], "pointRadius": 0}]},
        "options": {"scales": {"x": {"title": {"display": True, "text": "sum of appFees.fee on the swap"}},
                               "y": {"title": {"display": True, "text": "median haircut users took (bps)"}}}}}
    return cfg, ["data/audit/fee_unit_test_stable_pairs.csv"]


def s_wallet(data):
    w = [r for r in rd(data, "onchain", "buyback_wallet_daily.csv") if r["native_near"]]
    return line([r["day"] for r in w], [("buybacks.multisignature.near balance", [round(float(r["native_near"]) / 1e6, 4) for r in w])],
                "million NEAR"), ["data/onchain/buyback_wallet_daily.csv"]


def s_inflow(data):
    q = rd(data, "bq", "q30_buyback_balance_daily.csv")
    return bar([r["block_date"] for r in q], [("NEAR in", [round(float(r["inflow_near"])) for r in q]),
                                              ("NEAR out", [-round(float(r["outflow_near"])) for r in q])], "NEAR per day"), \
        ["data/bq/q30_buyback_balance_daily.csv"]


def s_capture(data):
    met = json.load(open(os.path.join(data, "derived", "metrics.json"), encoding="utf-8"))["metrics"]
    v = lambda k: round(met[k]["value"] / 1e6, 2)
    return bar(["New NEAR issued per year (2.5%, today)", "New NEAR issued per year (1.6%, HSP-029 end state)",
                "NEAR flowing into the buyback wallet per year (Oct pace)"],
               [("million NEAR per year", [v("issuance_near_per_year"), v("issuance_near_per_year_hsp029"),
                                           round(met["wallet_inflow_near_per_day"]["value"] * 365 / 1e6, 2)])], "million NEAR / year"), \
        ["data/derived/metrics.json"]


def _short(code):
    return code[:8] + "..." if len(code) > 20 else code


def s_channels(data):
    met = _metrics(data)
    rows = met["channel_table"]["value"]
    return bar([_short(r[0]) for r in rows], [("% of 1Click volume", [round(100 * r[1], 2) for r in rows]),
                                             ("% of buyback fees", [round(100 * r[2], 2) for r in rows])], "%", horizontal=True), \
        ["data/audit/buyback_by_referral.csv", "data/derived/metrics.json (channel_table)"]


def s_channels_weekly(data):
    met = _metrics(data)
    s = met["top_volume_channel_weekly"]["value"]
    top = met["top_volume_channel"]["value"]
    return line([r[0] for r in s], [(top + ": % of 1Click volume", [round(100 * r[1], 2) for r in s]),
                                    (top + ": % of buyback fees", [round(100 * r[2], 2) for r in s]),
                                    ("all 1Click: buyback bps", [r[3] for r in s])], "%",
                y2={"all 1Click: buyback bps": "bps"}), \
        ["data/audit/buyback_by_week_referral.csv", "data/derived/metrics.json (top_volume_channel_weekly)"]


def s_signers(data):
    q = rd(data, "bq", "q10_daily_signers_by_segment.csv")
    return line([r["block_date"] for r in q], [("HOT game signers", [int(r["game_signers"]) for r in q]),
                                               ("organic signers", [int(r["organic_signers"]) for r in q]),
                                               ("self-transaction-only signers", [max(1, int(r["self_only_signers"])) for r in q])],
                "accounts per day (log scale)", log=True), ["data/bq/q10_daily_signers_by_segment.csv"]


def s_weekly(data):
    q = rd(data, "bq", "q11_real_active_weekly.csv")[1:-1]
    cols = [("L1 organic", "l1_organic"), ("L2 engaged", "l2_engaged"), ("L3 returning", "l3_returning"),
            ("L4 engaged and returning", "l4_engaged_and_returning")]
    return line([r["week"] for r in q], [(n, [int(r[c]) for r in q]) for n, c in cols], "accounts per week"), \
        ["data/bq/q11_real_active_weekly.csv"]


def s_retention(data):
    q = [r for r in rd(data, "bq", "q12_retention_cohorts.csv") if int(r["weeks_observable"]) >= 4]
    return line([r["cohort"] for r in q], [
        ("back the next week", [round(100 * int(r["active_week_1"]) / int(r["accounts"]), 2) for r in q]),
        ("back within 4 weeks", [round(100 * int(r["active_weeks_1_to_4"]) / int(r["accounts"]), 2) for r in q])],
        "% of the cohort"), ["data/bq/q12_retention_cohorts.csv"]


def s_price(data):
    price = {r["day"]: float(r["near_usd"]) for r in rd(data, "market", "near_price_daily.csv")}
    org = {r["block_date"]: int(r["organic_signers"]) for r in rd(data, "bq", "q10_daily_signers_by_segment.csv")}
    days = sorted(d for d in price if d in org)
    avg = [round(sum(org[x] for x in days[max(0, i - 6):i + 1]) / len(days[max(0, i - 6):i + 1])) for i in range(len(days))]
    return line(days, [("NEAR price (USD)", [price[d] for d in days]), ("organic signers, 7-day average", avg)],
                "USD", y2={"organic signers, 7-day average": "accounts per day"}), \
        ["data/market/near_price_daily.csv", "data/bq/q10_daily_signers_by_segment.csv"]


def s_peers(data):
    p = rd(data, "market", "peers.csv")
    return bar([r["chain"] for r in p], [("market cap / annualised chain fees (x)",
                [round(float(r["market_cap_usd"]) / (float(r["chain_fees_30d_usd"]) * 365 / 30)) for r in p])],
               "x (log scale)"), ["data/market/peers.csv"]


def _metrics(data):
    with open(os.path.join(data, "derived", "metrics.json"), encoding="utf-8") as f:
        return json.load(f)["metrics"]


def s_leadlag(data):
    met = _metrics(data)
    rows = [r for r in met["leadlag_table"]["value"] if r[0] == "weekly"]
    lags = sorted({r[3] for r in rows})
    get = lambda pid, i: [next(r[i] for r in rows if r[1] == pid and r[3] == l) for l in lags]
    crit = round(met["leadlag_weekly_critical_r"]["value"], 3)
    cfg = {"type": "bar", "data": {"labels": ["%+d wk" % l for l in lags], "datasets": [
        {"label": "Intents volume -> NEAR price: 95% bootstrap CI",
         "data": [[lo, hi] for lo, hi in zip(get("intents_to_price", 5), get("intents_to_price", 6))],
         "backgroundColor": "rgba(47,111,222,0.25)", "borderColor": "rgba(47,111,222,0.6)", "borderWidth": 1},
        {"type": "line", "label": "Intents volume -> NEAR price: r", "data": get("intents_to_price", 4),
         "borderColor": COLORS[0], "backgroundColor": COLORS[0], "pointRadius": 4, "showLine": False},
        {"type": "line", "label": "organic signers -> NEAR price: r", "data": get("organic_to_price", 4),
         "borderColor": COLORS[1], "backgroundColor": COLORS[1], "pointRadius": 4, "showLine": False},
        {"type": "line", "label": "PLACEBO Solana DEX volume -> NEAR price: r", "data": get("solana_dex_to_price", 4),
         "borderColor": COLORS[5], "backgroundColor": COLORS[5], "pointRadius": 4, "pointStyle": "rect", "showLine": False},
        {"type": "line", "label": "noise threshold (+/- r for p < 0.05)", "data": [crit] * len(lags),
         "borderColor": COLORS[4], "borderDash": [5, 4], "pointRadius": 0, "borderWidth": 1},
        {"type": "line", "label": "", "data": [-crit] * len(lags), "borderColor": COLORS[4], "borderDash": [5, 4],
         "pointRadius": 0, "borderWidth": 1}]},
        "options": {"scales": {"y": {"min": -1, "max": 1, "title": {"display": True, "text": "correlation r of weekly changes"}},
                               "x": {"title": {"display": True, "text": "lag (positive = first series moves first)"}}},
                    "plugins": {"legend": {"labels": {"filter": "nonempty"}}}}}
    return cfg, ["data/derived/metrics.json (leadlag_table)", "pipeline/models.py :: leadlag"]


def s_breakeven(data):
    met = _metrics(data)
    be = met["sensitivity_break_even_volume"]["value"]
    takes = [k for k in be[0] if k != "inflation"]
    labels = ["%s (%.1f bps)" % (t, be[0][t]["take_bps"]) for t in takes]
    series = [("issuance %.1f%%" % (100 * r["inflation"]), [round(r[t]["x_today"], 2) for t in takes]) for r in be]
    cfg = bar(labels, series, "x today's all-Intents volume needed")
    cfg["data"]["datasets"].append({"type": "line", "label": "today's volume (1x)", "data": [1] * len(takes),
                                    "borderColor": COLORS[5], "borderDash": [5, 4], "pointRadius": 0, "borderWidth": 1})
    return cfg, ["data/derived/metrics.json (sensitivity_break_even_volume)", "pipeline/models.py :: sensitivity"]


def s_game(data):
    q = [r for r in rd(data, "bq", "q26_game_methods_daily.csv") if r["method"] == "l2_claim"]
    return bar([r["block_date"] for r in q], [("distinct callers of l2_claim", [int(r["callers"]) for r in q])], "accounts"), \
        ["data/bq/q26_game_methods_daily.csv"]


def s_oct27(data):
    q = rd(data, "bq", "q21_oct27_target_balance.csv")
    return bar([r["block_date"] for r in q], [("NEAR in", [round(float(r["inflow_near"]), 1) for r in q]),
                                              ("NEAR out", [-round(float(r["outflow_near"]), 1) for r in q])], "NEAR"), \
        ["data/bq/q21_oct27_target_balance.csv"]


# ----------------------------------------------------------------------------- page
CHARTS = [
    # (id, section, series fn, kind, title, sentence, sql file or None, extra note)
    ("volume", "Demand", s_volume, "FACT", "Daily swap volume: 1Click vs all NEAR Intents",
     "1Click swaps are a steady ~{oneclick_share_of_intents_volume_median|pct0} slice of all NEAR Intents volume and move with it day to day (correlation {oneclick_vs_intents_daily_corr|r2}).",
     None, "Days 1 Oct, 20 Oct and 2 Nov contain multi-hour gaps in the source API ({source_gap_hours|int} hours, {source_gap_share_of_window|pct1} of the window)."),
    ("sizes", "Demand", s_sizes, "FACT", "Who carries the volume: swap size",
     "{swaps_under_100_share_of_swaps|pct0} of swaps are under $100, but swaps of $10k or more ({swaps_10k_plus_share_of_swaps|pct1} of swaps) carry {swaps_10k_plus_share_of_usd|pct0} of the dollars.", None, ""),
    ("referrals", "Demand", s_referrals, "FACT", "Which apps send the volume",
     "A handful of aggregators and wallets bring most of the 1Click volume: the top 5 referral codes carry {top5_referrals_usd_share|pct0}, {top_referral} alone {top_referral_usd_share|pct0}.", None,
     "'(none)' = swaps with no referral code."),
    ("refunds", "Demand", s_refunds, "FACT", "Refund rate per day",
     "Refunds are normally about {refund_rate_normal_median|pct1} of swaps; {refund_spike_intent_submit_failed_share|pct0} of the 4-5 Nov spike is one failure type, and {refund_spike_aurora_share|pct0} comes from Aurora referral codes, on top of their normal successful traffic.",
     None, ""),
    ("feeunit", "Value capture", s_feeunit, "FACT", "Is appFees.fee in basis points? (yes)",
     "On stablecoin-to-stablecoin swaps, what users actually lost tracks the fee field one-for-one (slope {fee_unit_slope|r2}), so the fee is in basis points, as the docs say.",
     None, ""),
    ("wallet", "Value capture", s_wallet, "FACT", "Buyback wallet balance, weekly",
     "The NEAR buyback wallet grew in {wallet_weeks_rising} of {wallet_weeks_total} weeks since inflows began; the step in mid-September is a one-off treasury transfer of {wallet_sep09_treasury_transfer_near|int} NEAR.",
     None, "Read from the public NEAR archival RPC by pipeline/buyback_wallet.py."),
    ("inflow", "Value capture", s_inflow, "FACT", "Buyback wallet: NEAR in and out per day",
     None, "q30_buyback_balance_daily", "Days with more than 10 NEAR leaving since 1 Jul: {wallet_outflow_days_over_10_near} (total out {wallet_outflow_near_since_jul|int} NEAR)."),
    ("capture", "Value capture", s_capture, "INFERENCE", "Buybacks vs new NEAR issued",
     "At October's pace the buyback wallet takes in about {wallet_inflow_share_of_issuance|pct0} of the NEAR issued each year today, and would take in about {wallet_inflow_share_of_issuance_hsp029|pct0} at HSP-029's lower 1.6% rate.",
     None, "Issuance = total supply x inflation ceiling (assumes full validator uptime). Held NEAR could be sold later; this is not a burn."),
    ("channels", "Value capture", s_channels, "INFERENCE", "Volume is not value: who pays for the buyback",
     "{top_volume_channel} sends {top_volume_channel_usd_share|pct0} of 1Click volume but only {top_volume_channel_buyback_share|pct1} of the buyback fees; swaps with no referral code are {no_referral_usd_share|pct0} of volume and {no_referral_buyback_share|pct0} of the buyback.",
     None, "Buyback fees = appFees fee to buybacks.multisignature.near (bps) x amountInUsd. 1Click only. A referral code is an app, not a user. Codes over 20 characters are shortened."),
    ("channels_weekly", "Value capture", s_channels_weekly, "INFERENCE", "Volume is not value, week by week",
     "Every week, {top_volume_channel} carried {top_volume_channel_weekly_usd_share_min|pct0}-{top_volume_channel_weekly_usd_share_max|pct0} of 1Click volume while its share of the buyback stayed at or below {top_volume_channel_weekly_buyback_share_max|pct1}.",
     None, "First and last weeks are partial (download 28 Sep 06:45 to 10 Nov 12:48 UTC)."),
    ("signers", "Usage", s_signers, "FACT", "Daily signing accounts by type (log scale)",
     None, "q10_daily_signers_by_segment", "Spikes in the self-transaction line are account factories ({burst_feb_implicit_self_only|int} accounts in Feb, {burst_oct_kaiching_self_only|int} kaiching accounts in Oct)."),
    ("weekly", "Usage", s_weekly, "FACT", "Weekly real active accounts, four strictness levels",
     None, "q11_real_active_weekly", "L4 (engaged and returning) is the most conservative count of real users."),
    ("retention", "Usage", s_retention, "FACT", "Do new organic accounts come back?",
     None, "q12_retention_cohorts", "Cohorts with fewer than 4 weeks of follow-up are left out."),
    ("game", "Usage", s_game, "FACT", "HOT game: mining-claim callers on sample days",
     None, "q26_game_methods_daily", "Seven sample days, to keep query cost low."),
    ("oct27", "Usage", s_oct27, "FACT", "27 Oct event: the receiving address",
     None, "q21_oct27_target_balance", "{oct27_senders|int} accounts ({oct27_senders_never_active_2026_share|pct0} never active in 2026 before) sent it {oct27_near_total|int} NEAR on 27 Oct; it sent {oct27_target_outflow_oct29|int} NEAR out on 29 Oct."),
    ("breakeven", "Model", s_breakeven, "INFERENCE", "How much Intents volume would make buybacks equal issuance?",
     "At today's buyback take-rate ({wallet_take_bps|d1} bps), Intents volume would need to be {break_even_volume_x_today_at_current_take|d1}x today's to offset 2.5% issuance, or {break_even_volume_x_today_hsp029_at_current_take|d1}x at HSP-029's 1.6%.",
     None, "Holds supply and NEAR price at today's values and assumes bought-back NEAR stays held. A sensitivity, not a forecast."),
    ("leadlag", "Model", s_leadlag, "INFERENCE", "Does Intents volume lead NEAR's price? (weekly, 2026)",
     "No: at every lag, Intents volume's correlation with NEAR's price stays inside the noise band, like the placebo's. Across all pairs, {leadlag_weekly_nonzero_lag_significant} of {leadlag_weekly_nonzero_lag_tests} lead/lag tests cleared it, about what chance gives ({leadlag_weekly_expected_false_positives|d1}). Organic signers (orange) move with price mainly in the same week.",
     None, "{leadlag_weeks} weekly changes; effects smaller than r = {leadlag_weekly_min_detectable_r|r2} would usually be missed. Daily and ex-incentive versions are in THESIS.md section 7."),
    ("price", "Valuation", s_price, "FACT", "NEAR price vs organic usage, 2026",
     "NEAR's price changed {near_price_change_ytd|pctsigned} since 1 Jan while organic signers changed {organic_change_jan_to_aug|pctsigned} from January to August; they do not move together in this sample.",
     None, "Descriptive only. No lead-lag or causal claim is made here."),
    ("peers", "Valuation", s_peers, "FACT", "Market cap per dollar of chain fees, vs peers",
     "Measured on base-layer gas fees, all of these chains trade at very high multiples; NEAR's figure ignores NEAR Intents revenue, which is shown in the tiles above.",
     None, "Chain fees = DefiLlama 30-day L1 fees x 365/30. Market cap from CoinGecko at fetch time. Methodologies differ across chains."),
]


FORMATS = {
    "pct0": lambda v: "%.0f%%" % (100 * v), "pct1": lambda v: "%.1f%%" % (100 * v), "pct2": lambda v: "%.2f%%" % (100 * v),
    "pctsigned": lambda v: "%+.0f%%" % (100 * v), "pctabs": lambda v: "%.0f%%" % abs(100 * v), "int": lambda v: "{:,.0f}".format(v), "r2": lambda v: "%.2f" % v,
    "d1": lambda v: "%.1f" % v, "musd": lambda v: "$%.1fM" % (v / 1e6), "busd": lambda v: "$%.2fB" % (v / 1e9),
    "mnear": lambda v: "%.1fM" % (v / 1e6), "x0": lambda v: "%.0fx" % v, "usd2": lambda v: "$%.2f" % v,
}


def fill(text, met):
    """Replace {metric_key|format} with values from metrics.json. Unknown keys fail loudly - never guess."""
    def sub(mo):
        key, fmt = mo.group(1), mo.group(2)
        if key not in met:
            raise KeyError("text refers to metric '%s', which metrics.json does not have" % key)
        v = met[key]["value"]
        if isinstance(v, list):
            if not v:
                return "none"
            if all(isinstance(x, list) and len(x) == 2 for x in v):          # [[label, number], ...]
                return "; ".join("%s: %s" % (x[0], num(x[1])) for x in v)
            if len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], (int, float)):  # [label, number]
                return "%s: %s" % (v[0], num(v[1]))
            return ", ".join(num(x) for x in v)
        return FORMATS[fmt](v) if fmt else num(v)
    return re.sub(r"\{([a-z][a-z0-9_]*)(?:\|([a-z0-9]+))?\}", sub, text or "")


def num(x):
    """Default number style: thousands separators for big numbers, 2 decimals for small fractional ones."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return str(x)
    if isinstance(x, int) or abs(x) >= 100:
        return "{:,.0f}".format(x)
    return "%.2f" % (x + 0.0)  # + 0.0 turns -0.0 into 0.0


def tile(met, key, fmt, label):
    m = met.get(key)
    if not m:
        return '<div class="tile"><div class="v">not computed</div><div class="l">%s</div></div>' % html.escape(label)
    return '<div class="tile"><div class="v">%s</div><div class="l">%s</div><div class="k">%s &middot; <code>%s</code></div></div>' % (
        html.escape(fmt(m["value"])), html.escape(label), m["kind"], key)


def build(data, out):
    met = json.load(open(os.path.join(data, "derived", "metrics.json"), encoding="utf-8"))["metrics"]
    musd = lambda v: "$%.1fM" % (v / 1e6)
    pct = lambda v: "%.1f%%" % (100 * v)
    tiles = "".join([
        tile(met, "oneclick_usd_per_day", lambda v: musd(v) + "/day", "1Click swap volume (SUCCESS, clean days)"),
        tile(met, "intents_volume_usd_per_day", lambda v: musd(v) + "/day", "All NEAR Intents volume (DefiLlama, 30 days)"),
        tile(met, "near_captured_revenue_usd_per_year", lambda v: musd(v) + "/yr", "NEAR's captured Intents revenue (DefiLlama, annualised)"),
        tile(met, "wallet_inflow_share_of_issuance", pct, "Buyback inflow as a share of new NEAR issued"),
        tile(met, "top_volume_channel_buyback_share", pct, "Share of 1Click buyback fees from the app with the most volume"),
        tile(met, "organic_signers_per_day_latest", lambda v: "%.0f/day" % v, "Organic NEAR signers, latest month"),
        tile(met, "organic_change_jan_to_aug", pct, "Organic signers, Jan to Aug 2026"),
        tile(met, "strict_weekly_active_latest", lambda v: "%.0f/wk" % v, "Strict weekly active accounts (L4), last 2 weeks"),
        tile(met, "market_cap_to_captured_revenue", lambda v: "%.0fx" % v, "Market cap / captured Intents revenue"),
        tile(met, "scorecard_verdict", str, "Scorecard verdict (thesis.yaml)"),
    ])
    sc = met["scorecard"]["value"]
    srows = "".join(
        '<tr><td><code>%s</code><br><span class="q">%s</span></td><td>%s</td><td>%s</td><td>%s</td><td><span class="st %s">%s</span></td></tr>' % (
            html.escape(r["id"]), html.escape(r["question"]),
            html.escape(fmt_value(r.get("value"), met.get(r["metric"], {}).get("unit", ""))),
            html.escape(r["bullish_if"]), html.escape(r["bearish_if"]), r["status"].replace(" ", "-"), r["status"].upper())
        for r in sc)
    with open(os.path.join(ROOT, "thesis.yaml"), encoding="utf-8") as f:
        yaml_text = f.read()
    g, y, rd_ = met["scorecard_counts"]["value"]
    scorecard = SCORECARD % (html.escape(met["scorecard_verdict"]["value"]), g, y, rd_, srows, html.escape(yaml_text))
    sections, data_js = {}, {}
    for cid, section, fn, kind, title, sentence, sqlname, note in CHARTS:
        cfg, sources = fn(data)
        sentence, note = fill(sentence, met), fill(note, met)
        data_js[cid] = cfg
        if sqlname:
            code, meta = sql_meta(sqlname)
            sentence = sentence or meta.get("sentence", "")
            query = "-- sql/%s.sql  (run with: python pipeline/bq_run.py %s)\n%s" % (sqlname, sqlname.split("_")[0], code)
            sources = ["sql/%s.sql" % sqlname] + sources
        else:
            query = "# dashboard/build_dashboard.py :: %s  (reads the files listed above)\n%s" % (fn.__name__, inspect.getsource(fn))
        card = """
<section class="card" id="%s">
  <h3>%s</h3>
  <p class="sentence">%s</p>
  <div class="chart"><canvas id="cv-%s"></canvas></div>
  <p class="meta"><span class="kind %s">%s</span> Source: %s%s</p>
  <details><summary>Query behind this chart</summary><pre><code>%s</code></pre></details>
</section>""" % (cid, html.escape(title), html.escape(sentence), cid, kind.lower(), kind,
                 ", ".join("<code>%s</code>" % html.escape(s) for s in sources),
                 (" &middot; " + html.escape(note)) if note else "", html.escape(query))
        sections.setdefault(section, []).append(card)
    body = "".join('<h2>%s</h2><div class="grid">%s</div>' % (html.escape(s), "".join(c)) for s, c in sections.items())
    page = PAGE.replace("{{TILES}}", tiles).replace("{{BODY}}", scorecard + body).replace(
        "{{DATA}}", json.dumps(data_js).replace("</", "<\\/")).replace(
        "{{STAMP}}", html.escape("%s; NEAR price %s at %s" % (
            met.get("swaps_last_utc", {}).get("value", "?"), met.get("near_price_usd", {}).get("value", "?"),
            met.get("snapshot_block_time_utc", {}).get("value", "?"))))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("dashboard: %d charts -> %s" % (len(CHARTS), out))


SCORECARD = """<h2>Scorecard</h2><section class="card"><h3>Verdict: %s</h3>
<p class="sentence">%d green, %d yellow, %d red. Each signal is a measured or derived metric with a bullish and a bearish threshold set in <code>thesis.yaml</code>; it is re-scored on every build.</p>
<div class="tablewrap"><table><thead><tr><th>Signal</th><th>Today</th><th>Bullish if</th><th>Bearish if</th><th>Status</th></tr></thead><tbody>%s</tbody></table></div>
<p class="meta"><span class="kind inference">INFERENCE</span> Source: <code>thesis.yaml</code>, <code>data/derived/metrics.json</code> (scorecard)</p>
<details><summary>Rules behind this scorecard (thesis.yaml)</summary><pre><code>%s</code></pre></details></section>"""


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEAR Intents Thesis</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1b1d21;--muted:#5d636e;--line:#e3e3df;--fact:#1a7f5a;--inf:#a35b00;--code:#f1f1ee}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#141518;--card:#1d1f23;--ink:#e9eaec;--muted:#a2a7b0;--line:#30333a;--fact:#5fd1a2;--inf:#f0a64a;--code:#26292e}}
:root[data-theme="dark"]{--bg:#141518;--card:#1d1f23;--ink:#e9eaec;--muted:#a2a7b0;--line:#30333a;--fact:#5fd1a2;--inf:#f0a64a;--code:#26292e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:16px;margin:0 0 4px}.lead{color:var(--muted);margin:0 0 18px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile .v{font-size:22px;font-weight:650}.tile .l{color:var(--ink);font-size:13px}.tile .k{color:var(--muted);font-size:11px;margin-top:4px;word-break:break-all}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0}
.sentence{margin:0 0 10px}.chart{position:relative;height:280px}.meta{color:var(--muted);font-size:12px;margin:10px 0 6px;word-break:break-word}
.kind{font-weight:700;font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid currentColor;margin-right:6px}.kind.fact{color:var(--fact)}.kind.inference{color:var(--inf)}
details summary{cursor:pointer;font-size:13px;color:var(--muted)}pre{background:var(--code);padding:10px;border-radius:6px;overflow:auto;max-height:340px;font-size:12px}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px}a{color:inherit}
footer{color:var(--muted);font-size:12px;margin-top:40px}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.q{color:var(--muted);font-size:12px}.st{font-weight:700;font-size:11px;padding:2px 7px;border-radius:4px;color:#fff}
.st.green{background:#1a7f5a}.st.yellow{background:#a87900}.st.red{background:#c23b3b}.st.not-computed{background:#6b7079}
</style></head><body><main>
<h1>NEAR Intents: is the demand real, and does NEAR capture it?</h1>
<p class="lead">Every number comes from pinned tables in this repo (<code>data/</code>) and is rebuilt by <code>python build.py</code>. Each chart shows its query. FACT = measured; INFERENCE = derived by arithmetic or modelling. Data as of {{STAMP}}.</p>
<div class="tiles">{{TILES}}</div>
{{BODY}}
<footer>Built by dashboard/build_dashboard.py. Sources: NEAR Intents Explorer API (1Click swaps), Google BigQuery public dataset crypto_near_mainnet_us, NEAR JSON-RPC, DefiLlama, CoinGecko. Not investment advice.</footer>
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const CHARTS = {{DATA}};
const css = getComputedStyle(document.documentElement);
if (window.Chart) {
  Chart.defaults.color = css.getPropertyValue('--muted').trim();
  Chart.defaults.borderColor = css.getPropertyValue('--line').trim();
  Chart.defaults.maintainAspectRatio = false;
  for (const [id, cfg] of Object.entries(CHARTS)) {
    cfg.options = Object.assign({interaction: {mode: 'index', intersect: false}, plugins: {legend: {position: 'bottom'}}}, cfg.options || {});
    if (id === 'peers') cfg.options.scales.y.type = 'logarithmic';
    const lg = cfg.options.plugins && cfg.options.plugins.legend;
    if (lg && lg.labels && lg.labels.filter === 'nonempty') lg.labels.filter = (item) => item.text !== '';
    const el = document.getElementById('cv-' + id);
    if (el) new Chart(el, cfg);
  }
} else {
  document.querySelectorAll('.chart').forEach(c => c.innerHTML = '<p class="meta">Chart library could not load (offline?). The data and query are still below.</p>');
}
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Build the dashboard HTML.")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out", default=os.path.join(HERE, "index.html"))
    args = ap.parse_args()
    build(args.data, args.out)


if __name__ == "__main__":
    main()

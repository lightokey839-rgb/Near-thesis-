"""
models.py - the modelling layer: HSP-029 sensitivity, lead-lag statistics and the
thesis scorecard. Called by metrics.py after the measured metrics exist, so
everything lands in data/derived/metrics.json with its sources and method.

Standard library only. Random numbers use a fixed seed, so results are identical
on every rebuild.
"""

import csv
import math
import os
import random
import re
import statistics as st
from datetime import date, timedelta

SEED = 20261111
INFLATION_RATES = [0.025, 0.020, 0.016]          # today, a midpoint, HSP-029 end state
BUYBACK_MULTIPLES = [0.0, 0.5, 1.0, 2.0, 4.0]    # x today's buyback-wallet inflow
EXTRA_TAKE_BPS = [10.0, 20.0]                    # hypothetical take-rates beside today's measured ones
INCENTIVE_WEEKS = ("2026-09-14", "2026-10-19")   # Sep-Oct incentive period incl. the change out of it
RELEASE_GRID = (0.0, 0.25, 0.5, 1.0)             # custody released back to the market per year, for the sensitivity table


# ----------------------------------------------------------------------------- small helpers
def _csv(m, *p):
    with open(m.path(*p), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _v(m, key):
    return m.out[key]["value"]


def pearson(a, b):
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def block_bootstrap_ci(a, b, block, reps, rng):
    """95% percentile CI of Pearson r by moving-block bootstrap of the (a, b) pairs (keeps autocorrelation)."""
    n = len(a)
    if n < block * 2:
        return float("nan"), float("nan")
    starts = n - block + 1
    rs = []
    for _ in range(reps):
        ia = []
        while len(ia) < n:
            s0 = rng.randrange(starts)
            ia.extend(range(s0, s0 + block))
        ia = ia[:n]
        r = pearson([a[i] for i in ia], [b[i] for i in ia])
        if not math.isnan(r):
            rs.append(r)
    rs.sort()
    return rs[int(0.025 * len(rs))], rs[min(len(rs) - 1, int(0.975 * len(rs)))]


def lagged(x, y, lag):
    """Pairs (x_t, y_t+lag). Positive lag = x moves first."""
    pairs = [(x[t], y[t + lag]) for t in range(len(x)) if 0 <= t + lag < len(y)
             and x[t] is not None and y[t + lag] is not None]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def critical_r(n):
    """|r| needed for p < 0.05 (two-sided), and the smallest |r| detectable with 80% power (Fisher z)."""
    if n <= 3:
        return float("nan"), float("nan")
    se = 1 / math.sqrt(n - 3)
    return math.tanh(1.96 * se), math.tanh((1.96 + 0.84) * se)


# ----------------------------------------------------------------------------- extra measured metrics
def extra(m):
    q = _csv(m, "bq", "q30_buyback_balance_daily.csv")
    last = date.fromisoformat(q[-1]["block_date"])
    recent = [r for r in q if date.fromisoformat(r["block_date"]) > last - timedelta(days=90)]
    worst = max((-float(r["largest_single_outflow_near"] or 0) / float(r["end_of_day_near"]) for r in recent), default=0.0)
    m.put("wallet_largest_outflow_share_90d", max(0.0, worst), "share of balance", "FACT",
          ["data/bq/q30_buyback_balance_daily.csv"],
          "largest single balance decrease in the last 90 days of data / that day's closing balance "
          "(first version of the outflow signal; replaced on 12 Nov 2026, kept for disclosure)")
    # Scorecard signal since 12 Nov 2026: no window to choose - everything that left / everything that came in.
    inflow = sum(float(r["inflow_near"] or 0) for r in q)
    outflow = sum(float(r["outflow_near"] or 0) for r in q)
    sep09 = sum(float(r["delta_near"]) for r in _csv(m, "bq", "q33_buyback_sep09_moves.csv"))
    m.put("wallet_outflow_share_of_inflows", outflow / inflow, "share of inflows", "FACT",
          ["data/bq/q30_buyback_balance_daily.csv"],
          "all NEAR that left the wallet / all NEAR that came in, over every day of daily data (%s to %s)"
          % (q[0]["block_date"], q[-1]["block_date"]))
    m.put("wallet_outflow_share_of_inflows_ex_sep09", outflow / (inflow - sep09), "share of inflows", "FACT",
          ["data/bq/q30_buyback_balance_daily.csv", "data/bq/q33_buyback_sep09_moves.csv"],
          "same, with the 9 Sep treasury transfer removed from inflows (fee flow only)")

    ll = [r for r in _csv(m, "market", "defillama_intents_daily.csv") if r["intents_volume_usd"]]
    vol = [float(r["intents_volume_usd"]) for r in ll][:-2]   # drop the 2 newest (often incomplete) days
    m.put("intents_volume_4w_vs_prior_12w", st.mean(vol[-28:]) / st.mean(vol[-112:-28]), "ratio", "FACT",
          ["data/market/defillama_intents_daily.csv"], "mean daily all-Intents volume, last 28 complete days / the 84 days before")
    m.put("intents_volume_8w_vs_prior_8w", st.mean(vol[-56:]) / st.mean(vol[-112:-56]), "ratio", "FACT",
          ["data/market/defillama_intents_daily.csv"], "same idea, last 56 days / the 56 days before (robustness)")
    m.put("intents_volume_4w_vs_prior_4w", st.mean(vol[-28:]) / st.mean(vol[-56:-28]), "ratio", "FACT",
          ["data/market/defillama_intents_daily.csv"], "same idea, last 28 days / the 28 days before (robustness)")


# ----------------------------------------------------------------------------- value-capture bridge and windows
BUYBACK_START = "2026-02-23"  # DefiLlama's adapter: captured revenue is used to buy back NEAR from this date
BUYBACK_PREV_SUNDAY = "2026-02-22"  # weeks labelled up to this day are left out of the post-buyback lead-lag sample


def windows(m):
    """Two robustness checks on the value-capture numbers, from pinned tables only.

    1. Bridge: over the same days as DefiLlama's 30-day window, compare (a) 1Click buyback fees from our swaps,
       (b) NEAR flowing into buybacks.multisignature.near valued at each day's price, (c) DefiLlama captured revenue.
       DefiLlama's revenue counts three NEAR wallets (fefundsadmin.sputnik-dao.near, 1csfundsadmin.sputnik-dao.near and
       the buyback wallet), so (c) - (b) is revenue that went to the other two wallets plus any measurement difference.
    2. Windows: the revenue-based ratios over 30, 90 and 180 days and since the buyback program began.
    """
    ll = [r for r in _csv(m, "market", "defillama_intents_daily.csv") if r["intents_volume_usd"]]
    rows = {r["day"]: r for r in ll}
    a, b = _v(m, "defillama_window").split(" to ")
    last = date.fromisoformat(b)
    price = {r["day"]: float(r["near_usd"]) for r in _csv(m, "market", "near_price_daily.csv")}
    q = {r["block_date"]: r for r in _csv(m, "bq", "q30_buyback_balance_daily.csv")}
    sep09 = sum(float(r["delta_near"]) for r in _csv(m, "bq", "q33_buyback_sep09_moves.csv"))
    oc = {r["day"]: float(r["buyback_usd_if_bps"]) for r in _csv(m, "audit", "buyback_usd_est_by_day_if_bps.csv")}
    mcap, p_now = _v(m, "near_market_cap_usd"), _v(m, "near_price_usd")
    iss_usd = _v(m, "total_supply_near") * _v(m, "max_inflation_rate") * p_now
    src = ["data/market/defillama_intents_daily.csv", "data/market/near_price_daily.csv",
           "data/bq/q30_buyback_balance_daily.csv", "data/bq/q33_buyback_sep09_moves.csv",
           "data/audit/buyback_usd_est_by_day_if_bps.csv"]

    def wallet_usd(d):
        near_in = float(q[d]["inflow_near"]) - (sep09 if d == "2026-09-09" else 0.0)
        return near_in * price[d]

    ds = [d for d in sorted(rows) if a <= d <= b]
    n = len(ds)
    dl = sum(float(rows[d]["near_captured_revenue_usd"] or 0) for d in ds)
    vol = sum(float(rows[d]["intents_volume_usd"]) for d in ds)
    w = sum(wallet_usd(d) for d in ds)
    one = sum(oc.get(d, 0.0) for d in ds)
    m.put("bridge_window", "%s to %s (%d days)" % (ds[0], ds[-1], n), "", "FACT", src, "the same days for every row of the bridge")
    m.put("bridge_oneclick_usd_per_year", one / n * 365, "USD/yr", "INFERENCE", src,
          "(a) 1Click swaps: fee to the buyback wallet (bps) x amountInUsd, summed over the window, x 365 / days")
    m.put("bridge_wallet_usd_per_year", w / n * 365, "USD/yr", "INFERENCE", src,
          "(b) NEAR into buybacks.multisignature.near each day x that day's NEAR price, x 365 / days")
    m.put("bridge_defillama_usd_per_year", dl / n * 365, "USD/yr", "INFERENCE", src,
          "(c) DefiLlama captured revenue (three NEAR wallets), x 365 / days")
    m.put("bridge_wallet_share_of_defillama", w / dl, "share", "INFERENCE", src, "(b) / (c)")
    m.put("bridge_oneclick_share_of_wallet", one / w, "share", "INFERENCE", src, "(a) / (b)")
    m.put("bridge_other_wallets_usd_per_year", (dl - w) / n * 365, "USD/yr", "INFERENCE", src,
          "(c) - (b): captured revenue DefiLlama assigns to its other two wallets, plus any measurement difference")
    m.put("wallet_take_bps_dayprice", w / vol * 1e4, "bps", "INFERENCE", src, "(b) / all-Intents volume, same days")
    m.put("market_cap_to_wallet_inflow", mcap / (w / n * 365), "x", "INFERENCE", src + ["data/market/peers.csv"],
          "market cap / (b) annualised: the multiple if only the buyback wallet's inflow is counted")
    monthly = []
    for mo in ("2026-07", "2026-08", "2026-09", "2026-10"):
        md = [d for d in sorted(q) if d.startswith(mo) and d in rows and d in price]
        wm = sum(wallet_usd(d) for d in md)
        dm = sum(float(rows[d]["near_captured_revenue_usd"] or 0) for d in md)
        monthly.append([mo, round(wm), round(dm), round(wm / dm, 3) if dm else None])
    m.put("bridge_monthly", monthly, "USD", "INFERENCE", src, "per month: (b) buyback-wallet inflow at day prices, (c) DefiLlama revenue, (b)/(c)")

    out = []
    starts = [("30 days", (last - timedelta(days=29)).isoformat()), ("90 days", (last - timedelta(days=89)).isoformat()),
              ("180 days", (last - timedelta(days=179)).isoformat()), ("since buybacks began", BUYBACK_START)]
    for label, start in starts:
        dd = [d for d in sorted(rows) if start <= d <= b]
        v = sum(float(rows[d]["intents_volume_usd"]) for d in dd)
        r = sum(float(rows[d]["near_captured_revenue_usd"] or 0) for d in dd)
        r_yr = r / len(dd) * 365
        out.append({"window": label, "from": dd[0], "to": dd[-1], "days": len(dd), "volume_usd_per_day": v / len(dd),
                    "take_bps": r / v * 1e4, "revenue_usd_per_year": r_yr, "revenue_to_issuance_usd": r_yr / iss_usd,
                    "market_cap_to_revenue": mcap / r_yr})
    m.put("window_table", out, "", "INFERENCE", ["data/market/defillama_intents_daily.csv", "data/market/peers.csv",
                                                 "data/market/near_chain_snapshot.json"],
          "revenue-based ratios over different windows ending %s; 'since buybacks began' starts %s" % (b, BUYBACK_START))


# ----------------------------------------------------------------------------- five-year scenarios and reverse valuation
def scenario_start(m):
    """Today's values the scenario model starts from (all from metrics.json)."""
    return {"volume_usd_per_day": _v(m, "intents_volume_usd_per_day"), "take_bps": _v(m, "captured_revenue_take_bps"),
            "gross_fee_bps": _v(m, "intents_gross_fee_bps"), "supply_near": _v(m, "total_supply_near"),
            "custody_near": _v(m, "revenue_wallets_total_near"), "price_usd": _v(m, "near_price_usd"),
            "market_cap_usd": _v(m, "near_market_cap_usd"), "inflation_rate": _v(m, "max_inflation_rate"),
            "realised_factor": _v(m, "realised_vs_ceiling_issuance")}


def scenarios(m, path):
    import json
    import scenario_model as sm
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    start = scenario_start(m)
    src = ["scenarios.json", "data/derived/metrics.json", "pipeline/scenario_model.py"]
    m.put("scenario_start", start, "", "INFERENCE", src, "today's values the scenarios start from (see scenario_model.py)")
    m.put("scenario_config", {k: v for k, v in cfg.items() if k != "note"}, "", "INFERENCE", ["scenarios.json"],
          "scenario assumptions (chosen by us; not forecasts)")
    results, summary = {}, []
    for sc in cfg["scenarios"]:
        rows = sm.run(start, cfg, sc)
        results[sc["id"]] = rows
        last = rows[-1]
        cum_float = 1.0
        for r in rows:
            cum_float *= 1.0 + r["float_growth"]
        summary.append({"id": sc["id"], "label": sc["label"], "volume_usd_per_day": last["volume_usd_per_day"],
                        "take_bps": last["take_bps"], "captured_usd": last["captured_usd"],
                        "buyback_share_of_issuance": last["buyback_share_of_issuance"],
                        "float_growth_final_year": last["float_growth"], "float_change_total": cum_float - 1.0,
                        "market_cap_to_revenue": last["market_cap_to_revenue"]})
    m.put("scenario_results", results, "", "INFERENCE", src, "year-by-year outputs of each scenario")
    m.put("scenario_summary", summary, "", "INFERENCE", src, "final-year outputs of each scenario, plus 5-year float change")
    by = {s["id"]: s for s in summary}
    for sid in ("bear", "base", "bull", "stress"):
        if sid in by:
            m.put("scenario_%s_final_buyback_share" % sid, by[sid]["buyback_share_of_issuance"], "share", "INFERENCE", src,
                  "%s scenario: NEAR bought back / NEAR issued, final year" % sid)
            m.put("scenario_%s_float_change_total" % sid, by[sid]["float_change_total"], "share", "INFERENCE", src,
                  "%s scenario: change in tradable float over the whole period" % sid)
    m.put("scenarios_offsetting_issuance", [s["id"] for s in summary if s["buyback_share_of_issuance"] >= 1.0], "", "INFERENCE", src,
          "scenarios in which NEAR bought back reaches NEAR issued by the final year")
    # custody-release sensitivity: each scenario re-run with only custody_release_per_year changed
    sens = []
    for sc in cfg["scenarios"]:
        cells = []
        for rel in RELEASE_GRID:
            cum = 1.0
            for r in sm.run(start, cfg, dict(sc, custody_release_per_year=rel)):
                cum *= 1.0 + r["float_growth"]
            cells.append(cum - 1.0)
        sens.append([sc["id"], sc["custody_release_per_year"], cells, by[sc["id"]]["buyback_share_of_issuance"]])
    m.put("scenario_release_grid", list(RELEASE_GRID), "share per year", "INFERENCE", src, "custody release rates tried")
    m.put("scenario_release_sensitivity", sens, "", "INFERENCE", src,
          "per scenario: id, its own release rate, five-year change in custody-adjusted float at each release rate in "
          "scenario_release_grid (everything else as defined), final-year NEAR bought / issued (does not depend on release)")
    bull = [r for r in sens if r[0] == "bull"]
    if bull:
        m.put("scenario_bull_float_falls_up_to_release", max([g for g, c in zip(RELEASE_GRID, bull[0][2]) if c < 0], default=None),
              "share per year", "INFERENCE", src, "highest release rate in the grid at which the bull case's float still shrinks")
    rv = sm.reverse(start, cfg)
    for k, v in rv.items():
        m.put("reverse_" + k, v, "", "INFERENCE", src,
              "reverse valuation (scenario_model.reverse): " + k.replace("_", " ") + "; at today's NEAR price")


# ----------------------------------------------------------------------------- HSP-029 sensitivity
def sensitivity(m):
    supply, stake = _v(m, "total_supply_near"), _v(m, "validator_stake_near")
    reward_cut, price = _v(m, "protocol_reward_rate"), _v(m, "near_price_usd")
    inflow_day = _v(m, "wallet_inflow_near_per_day")
    vol_day = _v(m, "intents_volume_usd_per_day")
    wallet_bps = _v(m, "wallet_inflow_usd_per_year") / (vol_day * 365) * 1e4
    captured_bps = _v(m, "captured_revenue_take_bps")
    src = ["data/derived/metrics.json"]

    net = []
    for rate in INFLATION_RATES:
        issued = supply * rate
        row = {"inflation": rate, "issued_near_per_year": issued,
               "staking_yield_ceiling": issued * (1 - reward_cut) / stake}
        for k in BUYBACK_MULTIPLES:
            row["net_supply_growth_at_%gx" % k] = (issued - k * inflow_day * 365) / supply
        row["buyback_multiple_to_offset"] = issued / (inflow_day * 365)
        net.append(row)
    m.put("sensitivity_net_supply", net, "share of supply per year", "INFERENCE", src,
          "net new supply = (supply x inflation - k x today's buyback inflow x 365) / supply, if bought-back NEAR stays held; "
          "supply, stake and price held at today's values")

    takes = [("buyback wallet today", wallet_bps), ("all captured revenue today", captured_bps)] + \
            [("hypothetical %g bps" % b, b) for b in EXTRA_TAKE_BPS]
    be = []
    for rate in INFLATION_RATES:
        row = {"inflation": rate}
        for label, bps in takes:
            need = supply * rate * price / 365 / (bps / 1e4)
            row[label] = {"take_bps": bps, "volume_usd_per_day": need, "x_today": need / vol_day}
        be.append(row)
    m.put("sensitivity_break_even_volume", be, "USD/day", "INFERENCE", src,
          "Intents volume per day at which buybacks would equal issuance: supply x inflation x price / 365 / take-rate; "
          "today's all-Intents volume = %.0f USD/day" % vol_day)
    m.put("wallet_take_bps", wallet_bps, "bps", "INFERENCE", src,
          "buyback-wallet inflow in USD / all-Intents volume (same 30-day volume window)")
    m.put("break_even_volume_x_today_at_current_take", be[0]["buyback wallet today"]["x_today"], "x", "INFERENCE", src,
          "times today's Intents volume needed for buyback-wallet inflow to equal 2.5% issuance at today's take-rate")
    m.put("break_even_volume_x_today_hsp029_at_current_take", be[-1]["buyback wallet today"]["x_today"], "x", "INFERENCE", src,
          "same at 1.6% issuance")


# ----------------------------------------------------------------------------- lead-lag
def _weekly_series(m):
    days = {}

    def add(key, rows, dcol, vcol):
        for r in rows:
            if r.get(vcol) not in (None, ""):
                days.setdefault(r[dcol], {})[key] = float(r[vcol])
    add("intents_volume", _csv(m, "market", "defillama_intents_daily.csv"), "day", "intents_volume_usd")
    add("near_price", _csv(m, "market", "near_price_daily.csv"), "day", "near_usd")
    add("organic_signers", _csv(m, "bq", "q10_daily_signers_by_segment.csv"), "block_date", "organic_signers")
    plc = _csv(m, "market", "placebo_daily.csv")
    add("btc_price", plc, "day", "btc_usd")
    add("solana_dex_volume", plc, "day", "solana_dex_volume_usd")
    keys = ["intents_volume", "near_price", "organic_signers", "btc_price", "solana_dex_volume"]
    full = sorted(d for d, v in days.items() if all(k in v for k in keys))
    weeks = {}
    for d in full:
        dd = date.fromisoformat(d)
        weeks.setdefault((dd - timedelta(days=dd.weekday())).isoformat(), []).append(days[d])
    out = []
    for w in sorted(weeks):
        rows = weeks[w]
        if len(rows) < 7:
            continue  # partial weeks are dropped
        out.append({"week": w, **{k: st.mean(r[k] for r in rows) for k in keys}})
    return out, full, days


def _logdiff(vals):
    return [None] + [math.log(b / a) if a > 0 and b > 0 else None for a, b in zip(vals, vals[1:])]


PAIRS = [  # (id, x, y, role)
    ("intents_to_price", "intents_volume", "near_price", "main"),
    ("intents_to_organic", "intents_volume", "organic_signers", "main"),
    ("organic_to_price", "organic_signers", "near_price", "main"),
    ("intents_to_price_ex_btc", "intents_volume", "near_price_ex_btc", "main"),
    ("solana_dex_to_price", "solana_dex_volume", "near_price", "placebo"),
    ("btc_to_price", "btc_price", "near_price", "market factor"),
]


def leadlag(m):
    rng = random.Random(SEED)
    weekly, full_days, days = _weekly_series(m)
    src = ["data/market/defillama_intents_daily.csv", "data/market/near_price_daily.csv",
           "data/bq/q10_daily_signers_by_segment.csv", "data/market/placebo_daily.csv"]

    def prepare(rows, mask_from=None, mask_to=None):
        ser = {k: _logdiff([r[k] for r in rows]) for k in ("intents_volume", "near_price", "organic_signers", "btc_price", "solana_dex_volume")}
        # NEAR price change with the same-period BTC move removed (OLS beta on the whole sample)
        pb = [(p, b) for p, b in zip(ser["near_price"], ser["btc_price"]) if p is not None and b is not None]
        mb = st.mean(b for _, b in pb)
        beta = sum((p - st.mean(x for x, _ in pb)) * (b - mb) for p, b in pb) / sum((b - mb) ** 2 for _, b in pb)
        ser["near_price_ex_btc"] = [None if p is None or b is None else p - beta * b
                                    for p, b in zip(ser["near_price"], ser["btc_price"])]
        if mask_from:
            labels = [r.get("week") or r.get("day") for r in rows]
            for k in ser:
                ser[k] = [None if mask_from <= lab <= mask_to else v for v, lab in zip(ser[k], labels)]
        return ser, beta

    out, summary = [], {}
    variants = [("weekly", weekly, 4, 4, 2000, None, None),
                ("weekly_ex_incentive", weekly, 4, 4, 2000) + INCENTIVE_WEEKS,
                ("daily", [{"day": d, **days[d]} for d in full_days], 7, 14, 400, None, None),
                # last, so the random draws of the three variants above are unchanged
                ("weekly_post_buyback", weekly, 4, 4, 2000, "0000-00-00", BUYBACK_PREV_SUNDAY)]
    for name, rows, maxlag, block, reps, mf, mt in variants:
        ser, beta = prepare(rows, mf, mt)
        if name == "weekly":
            m.put("leadlag_btc_beta", beta, "", "INFERENCE", src, "OLS beta of weekly NEAR log-price change on BTC's")
        for pid, x, y, role in PAIRS:
            best = None
            for lag in range(-maxlag, maxlag + 1):
                a, b = lagged(ser[x], ser[y], lag)
                r = pearson(a, b)
                lo, hi = block_bootstrap_ci(a, b, block, reps, rng)
                crit, mde = critical_r(len(a))
                sig = not (math.isnan(lo) or lo <= 0 <= hi)
                out.append([name, pid, role, lag, round(r, 4), round(lo, 4), round(hi, 4), len(a), round(crit, 3), sig])
                if lag != 0 and (best is None or abs(r) > abs(best[1])):
                    best = (lag, r, sig, len(a), crit, mde)
            summary["%s:%s" % (name, pid)] = best
    m.put("leadlag_table", out, "r", "INFERENCE", src,
          "Pearson r of log changes, x at time t vs y at t+lag (positive lag = x moves first); 95%% CI by moving-block "
          "bootstrap (weekly: blocks of 4, 2,000 draws; daily: blocks of 14, 400 draws); fixed seed %d" % SEED)
    nw = [r for r in out if r[0] == "weekly"]
    tests = [r for r in nw if r[3] != 0]
    m.put("leadlag_weeks", len(weekly), "weeks", "FACT", src, "complete weeks with all five series (Mon-Sun)")
    m.put("leadlag_weekly_first_last", [weekly[0]["week"], weekly[-1]["week"]], "", "FACT", src, "first and last week used")
    crit, mde = critical_r(len(weekly) - 1)
    m.put("leadlag_weekly_critical_r", crit, "r", "INFERENCE", src, "|r| needed for p < 0.05 with this many weekly changes")
    m.put("leadlag_weekly_min_detectable_r", mde, "r", "INFERENCE", src, "smallest |r| detectable with 80% power")
    m.put("leadlag_weekly_nonzero_lag_tests", len(tests), "tests", "INFERENCE", src, "lag != 0 tests across all weekly pairs")
    m.put("leadlag_weekly_nonzero_lag_significant", sum(1 for r in tests if r[9]), "tests", "INFERENCE", src,
          "of those, how many have a bootstrap CI excluding 0")
    m.put("leadlag_weekly_expected_false_positives", 0.05 * len(tests), "tests", "INFERENCE", src, "5% of the tests, by chance alone")
    # The question the thesis asks is about Intents, so count that family on its own (placebo and BTC pairs excluded).
    it = [r for r in tests if r[1].startswith("intents_")]
    m.put("leadlag_intents_tests", len(it), "tests", "INFERENCE", src, "weekly lag != 0 tests where x = Intents volume")
    m.put("leadlag_intents_significant", sum(1 for r in it if r[9]), "tests", "INFERENCE", src,
          "of those, how many have a bootstrap CI excluding 0")
    m.put("leadlag_organic_to_price_lag1", [r for r in nw if r[1] == "organic_to_price" and r[3] == 1][0][4], "r", "INFERENCE", src,
          "weekly r: organic signers this week vs NEAR price next week (weekly means; may reflect averaging plus the same-week link)")
    # post-buyback sample: weeks before the 23 Feb buyback start are masked out
    pb = [r for r in out if r[0] == "weekly_post_buyback"]
    n_pb = [r for r in pb if r[1] == "intents_to_price" and r[3] == 0][0][7]
    crit_pb, mde_pb = critical_r(n_pb)
    pb_it = [r for r in pb if r[1].startswith("intents_") and r[3] != 0]
    m.put("leadlag_post_buyback_changes", n_pb, "weekly changes", "FACT", src,
          "weekly changes used when weeks up to %s are left out (same-week Intents -> price pair)" % BUYBACK_PREV_SUNDAY)
    m.put("leadlag_post_buyback_critical_r", crit_pb, "r", "INFERENCE", src, "|r| needed for p < 0.05 in the post-buyback sample")
    m.put("leadlag_post_buyback_min_detectable_r", mde_pb, "r", "INFERENCE", src, "smallest |r| detectable with 80% power in that sample")
    m.put("leadlag_post_buyback_intents_tests", len(pb_it), "tests", "INFERENCE", src, "post-buyback weekly lag != 0 tests where x = Intents volume")
    m.put("leadlag_post_buyback_intents_significant", sum(1 for r in pb_it if r[9]), "tests", "INFERENCE", src,
          "of those, how many have a bootstrap CI excluding 0")
    pb_all = [r for r in pb if r[3] != 0]
    m.put("leadlag_post_buyback_all_tests", len(pb_all), "tests", "INFERENCE", src, "post-buyback weekly lag != 0 tests, all pairs")
    m.put("leadlag_post_buyback_all_significant", sum(1 for r in pb_all if r[9]), "tests", "INFERENCE", src,
          "of those, how many have a bootstrap CI excluding 0")
    m.put("leadlag_post_buyback_expected_false_positives", 0.05 * len(pb_all), "tests", "INFERENCE", src, "5% of them, by chance alone")
    m.put("leadlag_post_buyback_intents_to_price_lead_significant",
          sum(1 for r in pb_all if r[1] in ("intents_to_price", "intents_to_price_ex_btc") and r[3] > 0 and r[9]), "tests",
          "INFERENCE", src, "post-buyback tests where Intents volume moves FIRST (positive lag) and NEAR's price follows, CI excluding 0")
    m.put("leadlag_post_buyback_btc_lag_significant", sum(1 for r in pb_all if r[1] == "btc_to_price" and r[9]), "tests",
          "INFERENCE", src, "post-buyback BTC -> NEAR price tests at non-zero lags with a CI excluding 0 (a liquid market should show none)")
    for pid, *_ in PAIRS:
        lag, r, sig, n, crit, mde = summary["weekly:" + pid]
        m.put("leadlag_best_" + pid, [lag, round(r, 3), "CI excludes 0" if sig else "CI includes 0"], "", "INFERENCE", src,
              "weekly: the non-zero lag with the largest |r|, its r, and whether the bootstrap CI excludes 0")
        zero = [row for row in nw if row[1] == pid and row[3] == 0][0]
        m.put("leadlag_same_week_" + pid, [round(zero[4], 3), "CI excludes 0" if zero[9] else "CI includes 0"], "", "INFERENCE", src,
              "weekly: same-week r and whether its CI excludes 0")


# ----------------------------------------------------------------------------- scorecard (thesis.yaml)
def parse_thesis_yaml(text):
    """Parser for the small YAML subset thesis.yaml uses: top-level scalars and a 'signals:' list of flat maps."""
    doc, items, cur, in_list = {}, [], None, False
    for raw in text.splitlines():
        line = re.sub(r"\s+#.*$", "", raw) if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            in_list = line.strip()[:-1] == "signals"
            continue
        mo = re.match(r"^(\s*)(- )?([A-Za-z_]+):\s*(.*)$", line)
        if not mo:
            raise ValueError("thesis.yaml: cannot read line: %r" % raw)
        indent, dash, key, val = mo.groups()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if in_list and indent:
            if dash:
                cur = {}
                items.append(cur)
            cur[key] = val
        else:
            doc[key] = val
    doc["signals"] = items
    return doc


def _check(cond, value, met):
    mo = re.match(r"^(>=|<=|>|<)\s*(metric:)?([A-Za-z0-9_.\-]+)$", cond.strip())
    if not mo:
        raise ValueError("bad condition %r (use e.g. '>= 0.25' or '< metric:strict_weekly_active_aug')" % cond)
    op, is_metric, ref = mo.groups()
    thr = met[ref]["value"] if is_metric else float(ref)
    return {">=": value >= thr, "<=": value <= thr, ">": value > thr, "<": value < thr}[op], thr


def _score(doc, met, override=None):
    """Score every thesis.yaml signal. `override` maps metric key -> value (used for the window robustness rows)."""
    rows = []
    for s in doc["signals"]:
        key = s["metric"]
        if key not in met:
            rows.append({**s, "value": None, "status": "not computed"})
            continue
        val = (override or {}).get(key, met[key]["value"])
        bull, bull_thr = _check(s["bullish_if"], val, met)
        bear, bear_thr = _check(s["bearish_if"], val, met)
        status = "red" if bear else "green" if bull else "yellow"
        rows.append({**s, "value": val, "bullish_threshold": bull_thr, "bearish_threshold": bear_thr, "status": status,
                     "kind": met[key]["kind"]})
    counts = {c: sum(1 for r in rows if r["status"] == c) for c in ("green", "yellow", "red", "not computed")}
    if counts["red"] > counts["green"]:
        verdict = doc.get("verdict_if_more_red", "bearish")
    elif counts["green"] > counts["red"] and counts["green"] >= len(rows) / 2:
        verdict = doc.get("verdict_if_mostly_green", "bullish")
    else:
        verdict = doc.get("verdict_otherwise", "mixed")
    return rows, counts, verdict


def scorecard(m, yaml_path):
    with open(yaml_path, encoding="utf-8") as f:
        doc = parse_thesis_yaml(f.read())
    rows, counts, verdict = _score(doc, m.out)
    # Same rules, but with the three revenue-based signals measured over other windows (window_table).
    alt = []
    for w in (m.out.get("window_table") or {}).get("value", []):
        override = {"captured_revenue_take_bps": w["take_bps"], "captured_revenue_to_issuance_usd": w["revenue_to_issuance_usd"],
                    "market_cap_to_captured_revenue": w["market_cap_to_revenue"]}
        _, c, v = _score(doc, m.out, override)
        alt.append([w["window"], c["green"], c["yellow"], c["red"], v])
    if alt:
        m.put("scorecard_by_window", alt, "", "INFERENCE", ["thesis.yaml", "data/derived/metrics.json (window_table)"],
              "the scorecard re-scored with take_rate, revenue_vs_dilution and valuation measured over each window")
    m.put("scorecard", rows, "", "INFERENCE", ["thesis.yaml", "data/derived/metrics.json"],
          "each signal: green if its bullish condition holds, red if its bearish condition holds, else yellow")
    m.put("scorecard_counts", [counts["green"], counts["yellow"], counts["red"]], "signals", "INFERENCE", ["thesis.yaml"],
          "green, yellow, red")
    m.put("scorecard_verdict", verdict, "", "INFERENCE", ["thesis.yaml"],
          "red > green -> bearish verdict; green > red and at least half green -> bullish; otherwise mixed")
    m.put("thesis_claim", doc.get("claim", ""), "", "INFERENCE", ["thesis.yaml"], "the claim being scored")

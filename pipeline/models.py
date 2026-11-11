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
          "largest single balance decrease in the last 90 days of data / that day's closing balance")

    ll = [r for r in _csv(m, "market", "defillama_intents_daily.csv") if r["intents_volume_usd"]]
    vol = [float(r["intents_volume_usd"]) for r in ll][:-2]   # drop the 2 newest (often incomplete) days
    m.put("intents_volume_4w_vs_prior_12w", st.mean(vol[-28:]) / st.mean(vol[-112:-28]), "ratio", "FACT",
          ["data/market/defillama_intents_daily.csv"], "mean daily all-Intents volume, last 28 complete days / the 84 days before")


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
                ("daily", [{"day": d, **days[d]} for d in full_days], 7, 14, 400, None, None)]
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


def scorecard(m, yaml_path):
    with open(yaml_path, encoding="utf-8") as f:
        doc = parse_thesis_yaml(f.read())
    rows = []
    for s in doc["signals"]:
        key = s["metric"]
        if key not in m.out:
            rows.append({**s, "value": None, "status": "not computed"})
            continue
        val = m.out[key]["value"]
        bull, bull_thr = _check(s["bullish_if"], val, m.out)
        bear, bear_thr = _check(s["bearish_if"], val, m.out)
        status = "red" if bear else "green" if bull else "yellow"
        rows.append({**s, "value": val, "bullish_threshold": bull_thr, "bearish_threshold": bear_thr, "status": status,
                     "kind": m.out[key]["kind"]})
    counts = {c: sum(1 for r in rows if r["status"] == c) for c in ("green", "yellow", "red", "not computed")}
    if counts["red"] > counts["green"]:
        verdict = doc.get("verdict_if_more_red", "bearish")
    elif counts["green"] > counts["red"] and counts["green"] >= len(rows) / 2:
        verdict = doc.get("verdict_if_mostly_green", "bullish")
    else:
        verdict = doc.get("verdict_otherwise", "mixed")
    m.put("scorecard", rows, "", "INFERENCE", ["thesis.yaml", "data/derived/metrics.json"],
          "each signal: green if its bullish condition holds, red if its bearish condition holds, else yellow")
    m.put("scorecard_counts", [counts["green"], counts["yellow"], counts["red"]], "signals", "INFERENCE", ["thesis.yaml"],
          "green, yellow, red")
    m.put("scorecard_verdict", verdict, "", "INFERENCE", ["thesis.yaml"],
          "red > green -> bearish verdict; green > red and at least half green -> bullish; otherwise mixed")
    m.put("thesis_claim", doc.get("claim", ""), "", "INFERENCE", ["thesis.yaml"], "the claim being scored")

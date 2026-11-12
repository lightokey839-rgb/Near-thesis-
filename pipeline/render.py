"""
render.py - turn model outputs in metrics.json into Markdown tables for THESIS.md.
build.py replaces the markers <!-- SCORECARD -->, <!-- SENSITIVITY -->, <!-- LEADLAG --> and <!-- CHANNELS -->
in docs/THESIS.template.md with these tables.
"""

PAIR_LABELS = {
    "intents_to_price": "Intents volume -> NEAR price",
    "intents_to_organic": "Intents volume -> organic NEAR signers",
    "organic_to_price": "Organic NEAR signers -> NEAR price",
    "intents_to_price_ex_btc": "Intents volume -> NEAR price with BTC's move removed",
    "solana_dex_to_price": "PLACEBO: Solana DEX volume -> NEAR price",
    "btc_to_price": "MARKET: BTC price -> NEAR price",
}
VARIANT_LABELS = {"weekly": "weekly, all weeks", "weekly_ex_incentive": "weekly, without Sep 14-Oct 19", "daily": "daily"}


def fmt_value(v, unit):
    if v is None:
        return "not computed"
    if isinstance(v, float) and ("share" in unit):
        return "%.1f%%" % (100 * v)
    if unit == "x":
        return "%.0fx" % v
    if unit == "bps":
        return "%.1f bps" % v
    if unit == "ratio":
        return "%.2f" % v
    if isinstance(v, (int, float)) and abs(v) >= 100:
        return "{:,.0f}".format(v)
    return str(round(v, 3)) if isinstance(v, float) else str(v)


def scorecard_md(met):
    rows = met["scorecard"]["value"]
    out = ["| Signal | Question | Today | Bullish if | Bearish if | Status |", "|---|---|---|---|---|---|"]
    for r in rows:
        unit = met.get(r["metric"], {}).get("unit", "")
        thr = lambda cond, t: cond if "metric:" not in cond else "%s (%s)" % (cond, fmt_value(t, unit))
        out.append("| `%s` | %s | %s | %s | %s | **%s** |" % (
            r["id"], r["question"], fmt_value(r.get("value"), unit),
            thr(r["bullish_if"], r.get("bullish_threshold")), thr(r["bearish_if"], r.get("bearish_threshold")),
            r["status"].upper()))
    g, y, rd = met["scorecard_counts"]["value"]
    out.append("")
    out.append("**%d green, %d yellow, %d red -> verdict: %s.** Thresholds and rules live in `thesis.yaml`; "
               "each signal's metric, source and method are in `data/derived/metrics.json`." % (g, y, rd, met["scorecard_verdict"]["value"]))
    return "\n".join(out)


def sensitivity_md(met):
    net = met["sensitivity_net_supply"]["value"]
    mults = [k.split("_at_")[1] for k in net[0] if k.startswith("net_supply_growth_at_")]
    out = ["*Net new NEAR supply per year if bought-back NEAR stays held, by inflation rate (rows) and buyback pace "
           "(columns, multiples of today's buyback-wallet inflow).*", "",
           "| Inflation | New NEAR / yr | Staking yield ceiling | " + " | ".join("buyback %s" % k for k in mults) +
           " | Buyback multiple to offset |",
           "|---|---|---|" + "---|" * len(mults) + "---|"]
    for r in net:
        out.append("| %.1f%% | %.1fM | %.1f%% | %s | %.1fx |" % (
            100 * r["inflation"], r["issued_near_per_year"] / 1e6, 100 * r["staking_yield_ceiling"],
            " | ".join("%.2f%%" % (100 * r["net_supply_growth_at_" + k]) for k in mults), r["buyback_multiple_to_offset"]))
    be = met["sensitivity_break_even_volume"]["value"]
    takes = [k for k in be[0] if k != "inflation"]
    out += ["", "*NEAR Intents volume per day at which buybacks would equal issuance (at today's NEAR price), and how many "
            "times today's all-Intents volume that is.*", "",
            "| Inflation | " + " | ".join("%s (%.1f bps)" % (t, be[0][t]["take_bps"]) for t in takes) + " |",
            "|---|" + "---|" * len(takes)]
    for r in be:
        out.append("| %.1f%% | %s |" % (100 * r["inflation"], " | ".join(
            "$%.0fM/day (%.1fx)" % (r[t]["volume_usd_per_day"] / 1e6, r[t]["x_today"]) for t in takes)))
    return "\n".join(out)


def leadlag_md(met):
    table = met["leadlag_table"]["value"]
    out = ["| Pair (x -> y) | Data | Same period r [95% CI] | Strongest lead/lag: lag, r [95% CI] |", "|---|---|---|---|"]
    for variant in ("weekly", "weekly_ex_incentive", "daily"):
        unit = "wk" if variant.startswith("weekly") else "d"
        for pid, label in PAIR_LABELS.items():
            rows = [r for r in table if r[0] == variant and r[1] == pid]
            if not rows:
                continue
            zero = [r for r in rows if r[3] == 0][0]
            best = max((r for r in rows if r[3] != 0), key=lambda r: abs(r[4]))
            mark = lambda r: "" if not r[9] else " *"
            out.append("| %s | %s | %.2f [%.2f, %.2f]%s | %+d %s, %.2f [%.2f, %.2f]%s |" % (
                label, VARIANT_LABELS[variant], zero[4], zero[5], zero[6], mark(zero),
                best[3], unit, best[4], best[5], best[6], mark(best)))
    out += ["", "`*` = the bootstrap 95% CI excludes 0. Positive lag = x moves first. Full table (every lag): "
            "`leadlag_table` in `data/derived/metrics.json`."]
    return "\n".join(out)


def channels_md(met):
    out = ["| Referral code (app that sent the swap) | Share of 1Click volume | Share of buyback fees | Buyback fee (bps) |",
           "|---|---|---|---|"]
    for name, vol_share, bb_share, bps in met["channel_table"]["value"]:
        out.append("| `%s` | %.1f%% | %.1f%% | %.2f |" % (name, 100 * vol_share, 100 * bb_share, bps))
    out += ["", "*The 6 biggest referral codes by volume plus the 6 biggest by buyback fees. `(none)` = swaps with no "
            "referral code. Every code: `data/audit/buyback_by_referral.csv`.*"]
    return "\n".join(out)


def families_md(met):
    out = ["| Organic signers by account family (per day) | January | August | Latest month |", "|---|---|---|---|"]
    for label, jan, aug, latest in met["organic_family_table"]["value"]:
        out.append("| %s | {:,} | {:,} | {:,} |".format(jan, aug, latest) % label)
    return "\n".join(out)


def bridge_monthly_md(met):
    out = ["| Month | (b) buyback-wallet inflow, USD at day prices | (c) DefiLlama captured revenue, USD | (b) / (c) |",
           "|---|---|---|---|"]
    for mo, b, c, ratio in met["bridge_monthly"]["value"]:
        out.append("| %s | {:,} | {:,} | %s |".format(b, c) % (mo, "n/a" if ratio is None else "%.0f%%" % (100 * ratio)))
    return "\n".join(out)


def windows_md(met):
    by = {r[0]: r for r in met.get("scorecard_by_window", {}).get("value", [])}
    out = ["| Revenue window | Days | Take-rate | Captured revenue / yr | Revenue / issuance (USD) | Market cap / revenue | "
           "Scorecard (green / yellow / red) | Verdict |", "|---|---|---|---|---|---|---|---|"]
    for w in met["window_table"]["value"]:
        s = by.get(w["window"], [w["window"], "?", "?", "?", "?"])
        out.append("| %s (%s to %s) | %d | %.1f bps | $%.1fM | %.2f | %.0fx | %s / %s / %s | %s |" % (
            w["window"], w["from"], w["to"], w["days"], w["take_bps"], w["revenue_usd_per_year"] / 1e6,
            w["revenue_to_issuance_usd"], w["market_cap_to_revenue"], s[1], s[2], s[3], s[4]))
    return "\n".join(out)


def render_thesis(text, met):
    for marker, fn in (("<!-- SCORECARD -->", scorecard_md), ("<!-- SENSITIVITY -->", sensitivity_md),
                       ("<!-- LEADLAG -->", leadlag_md), ("<!-- CHANNELS -->", channels_md),
                       ("<!-- FAMILIES -->", families_md), ("<!-- BRIDGE_MONTHLY -->", bridge_monthly_md),
                       ("<!-- WINDOWS -->", windows_md)):
        if marker in text:
            text = text.replace(marker, fn(met))
    return text

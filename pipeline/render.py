"""
render.py - turn model outputs in metrics.json into Markdown tables for THESIS.md.
build.py replaces markers such as <!-- SCORECARD --> and <!-- CHANNELS --> in docs/THESIS.template.md with these
tables. The full list is in render_thesis at the bottom.
"""

PAIR_LABELS = {
    "intents_to_price": "Intents volume -> NEAR price",
    "intents_to_organic": "Intents volume -> organic NEAR signers",
    "organic_to_price": "Organic NEAR signers -> NEAR price",
    "intents_to_price_ex_btc": "Intents volume -> NEAR price with BTC's move removed",
    "solana_dex_to_price": "PLACEBO: Solana DEX volume -> NEAR price",
    "btc_to_price": "MARKET: BTC price -> NEAR price",
}
VARIANT_LABELS = {"weekly": "weekly, all weeks", "weekly_ex_incentive": "weekly, without Sep 14-Oct 19",
                  "weekly_post_buyback": "weekly, from the 23 Feb buyback start", "daily": "daily"}


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
    for variant in ("weekly", "weekly_ex_incentive", "weekly_post_buyback", "daily"):
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


def agents_md(met):
    out = ["| Agents listed in month | Listed | Of these, delivered at least one job |", "|---|---|---|"]
    for mo, listed, working in met["agent_market_listed_by_month"]["value"]:
        out.append("| %s | %d | %d |" % (mo, listed, working))
    return "\n".join(out)


def revenue_wallets_md(met):
    out = ["| Revenue wallet | NEAR at first sample | NEAR at last sample |", "|---|---|---|"]
    for w, a, b in met["revenue_wallet_balances"]["value"]:
        out.append("| `%s` | {:,} | {:,} |".format(a, b) % w)
    return "\n".join(out)


def scenarios_md(met):
    cfg = met["scenario_config"]["value"]
    out = ["| Scenario | Volume growth / yr | Take-rate by year %d | HSP-029 | Custody released / yr | Year-%d volume / day | "
           "Year-%d captured revenue | NEAR bought / issued (year %d) | Float change over %d years | Market cap / revenue (year %d) |"
           % ((cfg["years"],) * 6), "|---|---|---|---|---|---|---|---|---|---|"]
    by = {s["id"]: s for s in cfg["scenarios"]}
    for s in met["scenario_summary"]["value"]:
        c = by[s["id"]]
        out.append("| **%s** | %+.0f%% | %.1f bps | %s | %.0f%% | $%.0fM | $%.0fM | %.0f%% | %+.1f%% | %.0fx |" % (
            s["label"].split(":")[0], 100 * c["volume_cagr"], s["take_bps"], "yes" if c["hsp029"] else "no",
            100 * c["custody_release_per_year"], s["volume_usd_per_day"] / 1e6, s["captured_usd"] / 1e6,
            100 * s["buyback_share_of_issuance"], 100 * s["float_change_total"], s["market_cap_to_revenue"]))
    return "\n".join(out)


def _n(v, pattern="{:,.0f}"):
    return "n/a" if v is None else pattern.format(v)


def weekly_trend_md(met):
    out = ["| Week from (Monday) | Days | Volume / day | Gross fees (bps) | Captured take-rate (bps) | Captured revenue / day | "
           "Buyback inflow (NEAR / day) | NEAR price (mean) | Buyback inflow (USD / day) |", "|---|---|---|---|---|---|---|---|---|"]
    for w, days, vol, gross, cap, cap_usd, in_near, px, in_usd in met["trend_weekly"]["value"]:
        out.append("| %s%s | %d | $%.1fM | %.1f | %.2f | $%s | %s | %s | %s |" % (
            w, " (partial)" if days < 7 else "", days, vol / 1e6, gross, cap, _n(cap_usd), _n(in_near), _n(px, "${:.2f}"), _n(in_usd, "${:,.0f}")))
    out += ["", "*All Intents, from DefiLlama's daily series; NEAR price and the buyback wallet's daily inflow from the pinned tables "
            "(`trend_weekly` in `data/derived/metrics.json`). The last row is a partial week, and DefiLlama often revises its newest "
            "1-2 days. Buyback inflow is shown from the week of 14 Sep, because the one-off transfer of {:,.0f} NEAR on 9 Sep "
            "falls before it.*".format(met["wallet_sep09_treasury_transfer_near"]["value"])]
    return "\n".join(out)


def recon_md(met):
    v = lambda k: met[k]["value"]
    musd = lambda x: "$%.1fM" % (x / 1e6)
    pct = lambda x: "%.0f%%" % (100 * x)
    partner = v("recon_appfees_usd_per_year") - v("recon_buyback_usd_per_year")
    rows = [
        ("(1) All-Intents volume", "DefiLlama, FACT", musd(v("recon_allintents_usd_per_day")) + " / day", ""),
        ("(2) 1Click volume", "our download, SUCCESS swaps, FACT", musd(v("recon_oneclick_usd_per_day")) + " / day",
         pct(v("recon_oneclick_share_of_volume")) + " of (1)"),
        ("(3) Gross fees", "DefiLlama \"fees\", FACT", musd(v("recon_gross_usd_per_year")) + " / yr", "%.1f bps of (1)" % v("recon_gross_bps")),
        ("(4) 1Click app fees", "our download: fee (bps) x swap value, every recipient, INFERENCE", musd(v("recon_appfees_usd_per_year")) + " / yr",
         "%.1f bps of (2); %s of (3)" % (v("recon_appfees_bps_on_oneclick"), pct(v("recon_appfees_share_of_gross")))),
        ("(5) of which kept by integrators and partners", "(4) - (6), INFERENCE", musd(partner) + " / yr",
         pct(1 - v("recon_buyback_share_of_appfees")) + " of (4)"),
        ("(6) of which paid to the buyback wallet", "our download, INFERENCE", musd(v("recon_buyback_usd_per_year")) + " / yr",
         "%.1f%% of (4)" % (100 * v("recon_buyback_share_of_appfees"))),
        ("(7) Captured revenue, three wallets", "DefiLlama \"revenue\", INFERENCE (annualised)", musd(v("recon_captured_usd_per_year")) + " / yr",
         pct(v("recon_captured_share_of_gross")) + " of (3)"),
        ("(8) Captured revenue we cannot attribute to a swap", "(7) - (6), INFERENCE", musd(v("recon_other_captured_usd_per_year")) + " / yr",
         pct(v("recon_other_captured_share")) + " of (7)"),
    ]
    out = ["| Layer | Basis | Amount | Relative to |", "|---|---|---|---|"]
    out += ["| %s | %s | %s | %s |" % r for r in rows]
    out += ["", "*Window: %s. Monday-Sunday weeks, because the 1Click app-fee table is weekly; annualised by x 365 / 28. Every row is a `recon_*` "
            "metric in `data/derived/metrics.json`.*" % v("recon_window")]
    return "\n".join(out)


def extra_gaps_md(met):
    out = ["| Run of thin hours (UTC) | Hours | Swaps seen | Swaps expected | Status |", "|---|---|---|---|---|"]
    for a, b, hours, seen, expected, status in met["hourly_anomaly_table"]["value"]:
        out.append("| %s to %s | %d | %s | %s | %s |" % (a, b[-5:], hours, "{:,}".format(seen), "{:,}".format(expected), status))
    out += ["", "| Gap between two consecutive swaps, start (UTC) | Minutes | Swaps expected at the usual rate | Status |", "|---|---|---|---|"]
    for start, minutes, status, expected in met["extra_gap_table"]["value"]:
        out.append("| %s | %.1f | %s | %s |" % (start, minutes, "{:,}".format(expected), status))
    out += ["", "*Rule for the first table: %s. The second table is every gap of 10 minutes or more in `data/audit/integrity_largest_gaps.csv`, "
            "which keeps only the 15 largest gaps, so shorter ones are not visible (floor: %.1f minutes). \"Expected\" is the median count "
            "for that hour of day: an estimate, not a count.*" % (met["hourly_anomaly_rule"]["value"], met["extra_gap_listed_floor_minutes"]["value"])]
    return "\n".join(out)


def release_sens_md(met):
    grid = met["scenario_release_grid"]["value"]
    out = ["| Scenario | " + " | ".join("Release %.0f%% / yr" % (100 * g) for g in grid) + " | NEAR bought / issued, final year |",
           "|---|" + "---|" * (len(grid) + 1)]
    for sid, own, cells, share in met["scenario_release_sensitivity"]["value"]:
        out.append("| %s (defines %.0f%%) | %s | %.0f%% |" % (sid.capitalize(), 100 * own, " | ".join(
            ("**%+.1f%%**" if abs(g - own) < 1e-9 else "%+.1f%%") % (100 * c) for g, c in zip(grid, cells)), 100 * share))
    out += ["", "*Five-year change in custody-adjusted float (supply minus NEAR held in the revenue wallets) when only the release "
            "rate changes. Bold = the scenario as defined in `scenarios.json`. The last column does not depend on release, because it "
            "counts purchases. Metric: `scenario_release_sensitivity`.*"]
    return "\n".join(out)


def crosschain_md(met):
    v = lambda k: met[k]["value"]
    out = ["| Venue | Volume / day, %s | Share of the three | All-time volume (DefiLlama) |" % v("crosschain_window"), "|---|---|---|---|"]
    for key, label in (("near_intents", "NEAR Intents"), ("thorchain", "THORChain"), ("chainflip", "Chainflip")):
        out.append("| %s | $%.1fM | %.0f%% | $%.1fB |" % (label, v("crosschain_%s_usd_per_day" % key) / 1e6,
                                                         100 * v("crosschain_%s_share_of_three" % key), v("crosschain_alltime_%s_usd" % key) / 1e9))
    out += ["", "*DefiLlama DEX-volume adapters, read %s by `pipeline/fetch_crosschain.py` and pinned in "
            "`data/market/crosschain_peers_daily.csv`. Each venue's adapter counts volume its own way. Weekly values: `crosschain_weekly` "
            "in `data/derived/metrics.json`.*" % v("crosschain_fetched_utc")[:10]]
    return "\n".join(out)


def render_thesis(text, met):
    for marker, fn in (("<!-- SCORECARD -->", scorecard_md), ("<!-- SENSITIVITY -->", sensitivity_md),
                       ("<!-- LEADLAG -->", leadlag_md), ("<!-- CHANNELS -->", channels_md),
                       ("<!-- FAMILIES -->", families_md), ("<!-- BRIDGE_MONTHLY -->", bridge_monthly_md),
                       ("<!-- WINDOWS -->", windows_md), ("<!-- AGENTS -->", agents_md), ("<!-- REVENUE_WALLETS -->", revenue_wallets_md), ("<!-- SCENARIOS -->", scenarios_md),
                       ("<!-- WEEKLY_TREND -->", weekly_trend_md), ("<!-- RECON -->", recon_md),
                       ("<!-- EXTRA_GAPS -->", extra_gaps_md), ("<!-- CROSSCHAIN -->", crosschain_md),
                       ("<!-- RELEASE_SENS -->", release_sens_md)):
        if marker in text:
            text = text.replace(marker, fn(met))
    return text

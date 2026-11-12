"""
scenario_model.py - a five-year scenario model for NEAR value capture, plus a reverse valuation.

The same arithmetic is implemented in dashboard/scenario_model.js for the live sliders;
tests/test_scenarios.py checks that both give identical results.

What it models (all per year, t = 1..years):
  volume      = today's all-Intents volume x (1 + volume_cagr)^t
  take-rate   = moves in a straight line from today's captured take-rate to take_bps_end by the last year
  captured    = volume x take-rate                      (USD; revenue NEAR sweeps into its revenue wallets)
  bought      = captured / today's NEAR price          (NEAR; the price is HELD CONSTANT - this is not a price model)
  issuance    = supply x inflation rate x realised factor
                (inflation 2.5%; with HSP-029 it falls in a straight line to 1.6% over hsp029_ramp_years,
                 starting hsp029_activation_years from today; the realised factor is measured supply growth / the maximum)
  custody     = last year's custody x (1 - custody_release_per_year) + bought
                (NEAR held in the revenue wallets; released NEAR returns to the float. Nothing here is a burn.)
  float       = supply - custody
Outputs: buyback / issuance, revenue / issuance (USD), float growth, market cap / revenue (today's market cap: descriptive).
"""


def inflation_rate(t_mid, hsp029, start_rate, end_rate, activation, ramp):
    """Inflation ceiling at time t_mid (years from today)."""
    if not hsp029 or t_mid <= activation:
        return start_rate
    return start_rate - (start_rate - end_rate) * min(1.0, (t_mid - activation) / ramp)


def run(start, cfg, sc):
    """start: today's values; cfg: scenarios.json top level; sc: one scenario. Returns one dict per year."""
    years = int(cfg["years"])
    take_end = start["take_bps"] if sc.get("take_bps_end") is None else float(sc["take_bps_end"])
    supply, custody = start["supply_near"], start["custody_near"]
    flt = supply - custody
    rows = []
    for t in range(1, years + 1):
        vol_year = start["volume_usd_per_day"] * 365.0 * (1.0 + sc["volume_cagr"]) ** t
        take = start["take_bps"] + (take_end - start["take_bps"]) * t / years
        captured = vol_year * take / 1e4
        bought = captured / start["price_usd"]
        rate = inflation_rate(t - 0.5, sc["hsp029"], start["inflation_rate"], cfg["hsp029_end_rate"],
                              cfg["hsp029_activation_years"], cfg["hsp029_ramp_years"])
        issued = supply * rate * start["realised_factor"]
        supply = supply + issued
        custody = custody * (1.0 - sc["custody_release_per_year"]) + bought
        new_float = supply - custody
        rows.append({
            "year": t,
            "volume_usd_per_day": vol_year / 365.0,
            "take_bps": take,
            "captured_usd": captured,
            "bought_near": bought,
            "inflation_rate": rate,
            "issued_near": issued,
            "buyback_share_of_issuance": bought / issued,
            "revenue_to_issuance_usd": captured / (issued * start["price_usd"]),
            "float_growth": new_float / flt - 1.0,
            "custody_near": custody,
            "market_cap_to_revenue": start["market_cap_usd"] / captured,
        })
        flt = new_float
    return rows


def reverse(start, cfg):
    """What would have to be true. Returns a dict of required values (all at today's NEAR price)."""
    years = int(cfg["years"])
    # issuance in the final year with HSP-029 active and supply grown by issuance only
    supply = start["supply_near"]
    issued = 0.0
    for t in range(1, years + 1):
        rate = inflation_rate(t - 0.5, True, start["inflation_rate"], cfg["hsp029_end_rate"],
                              cfg["hsp029_activation_years"], cfg["hsp029_ramp_years"])
        issued = supply * rate * start["realised_factor"]
        supply += issued
    need_usd = issued * start["price_usd"]            # captured revenue (USD/yr) for buybacks to equal issuance in year N
    vol_today = start["volume_usd_per_day"] * 365.0

    def cagr_needed(take_bps):
        need_vol = need_usd / (take_bps / 1e4)
        return (need_vol / vol_today) ** (1.0 / years) - 1.0

    mult = float(cfg["valuation_multiple_for_reverse"])
    rev_for_mult = start["market_cap_usd"] / mult
    return {
        "final_year_issuance_near": issued,
        "revenue_needed_to_offset_final_year_usd": need_usd,
        "volume_cagr_needed_at_today_take": cagr_needed(start["take_bps"]),
        "volume_cagr_needed_at_8_bps": cagr_needed(8.0),
        "volume_cagr_needed_at_gross_fee_bps": cagr_needed(start["gross_fee_bps"]),
        "multiple": mult,
        "revenue_for_multiple_usd": rev_for_mult,
        "revenue_for_multiple_x_today": rev_for_mult / (vol_today * start["take_bps"] / 1e4),
        "volume_per_day_for_multiple_at_today_take": rev_for_mult / (start["take_bps"] / 1e4) / 365.0,
    }

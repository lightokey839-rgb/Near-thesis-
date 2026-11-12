// scenario_model.js - the same arithmetic as pipeline/scenario_model.py, for the dashboard sliders.
// tests/test_scenarios.py runs this file with Node (when available) and checks it matches Python exactly.
// Price is held constant: this is a scenario model of value capture, not a price model.
(function (root) {
  function inflationRate(tMid, hsp029, startRate, endRate, activation, ramp) {
    if (!hsp029 || tMid <= activation) return startRate;
    return startRate - (startRate - endRate) * Math.min(1.0, (tMid - activation) / ramp);
  }

  function run(start, cfg, sc) {
    var years = cfg.years | 0;
    var takeEnd = (sc.take_bps_end === null || sc.take_bps_end === undefined) ? start.take_bps : Number(sc.take_bps_end);
    var supply = start.supply_near, custody = start.custody_near;
    var flt = supply - custody;
    var rows = [];
    for (var t = 1; t <= years; t++) {
      var volYear = start.volume_usd_per_day * 365.0 * Math.pow(1.0 + sc.volume_cagr, t);
      var take = start.take_bps + (takeEnd - start.take_bps) * t / years;
      var captured = volYear * take / 1e4;
      var bought = captured / start.price_usd;
      var rate = inflationRate(t - 0.5, sc.hsp029, start.inflation_rate, cfg.hsp029_end_rate,
                               cfg.hsp029_activation_years, cfg.hsp029_ramp_years);
      var issued = supply * rate * start.realised_factor;
      supply = supply + issued;
      custody = custody * (1.0 - sc.custody_release_per_year) + bought;
      var newFloat = supply - custody;
      rows.push({
        year: t,
        volume_usd_per_day: volYear / 365.0,
        take_bps: take,
        captured_usd: captured,
        bought_near: bought,
        inflation_rate: rate,
        issued_near: issued,
        buyback_share_of_issuance: bought / issued,
        revenue_to_issuance_usd: captured / (issued * start.price_usd),
        float_growth: newFloat / flt - 1.0,
        custody_near: custody,
        market_cap_to_revenue: start.market_cap_usd / captured
      });
      flt = newFloat;
    }
    return rows;
  }

  var api = { run: run, inflationRate: inflationRate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ScenarioModel = api;
})(this);

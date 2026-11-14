"""
explain.py - the dashboard's "Explain this dashboard" panel and data/derived/claims.json.

Three layers, from most to least verifiable:
  1. A plain-English summary built from metrics.json by the build. No AI, no network, no key: every sentence is a template
     whose numbers are {metric|format} placeholders, so each one traces to a metric id with a value, a source and a label.
  2. The same sentences as a machine-readable file (data/derived/claims.json) and a downloadable brief, so a screener or
     any AI tool can check claims without reading prose.
  3. Optional: "Ask an AI about this dashboard". The viewer brings their own API key for Claude (Anthropic) or NEAR AI
     Cloud. The key stays in page memory, is never stored or logged, and is sent only to the provider's own API; the
     page's Content-Security-Policy allows no other destination. The repository holds no key and the site has no server.
"""

import json
import re

PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)(?:\|([a-z0-9]+))?\}")

# (id, section, sentence). Numbers only as placeholders; typed words only for things that are not numbers.
CLAIMS = [
    ("demand_size", "Demand",
     "All NEAR Intents swaps averaged {intents_volume_usd_per_day|musd} a day over {defillama_window}, "
     "{recent_vs_jan|pctsigned} on January."),
    ("demand_peers", "Demand",
     "Over the same 30 days that is {crosschain_near_intents_share_of_three|pct0} of the volume of three native cross-chain "
     "swap venues (NEAR Intents, THORChain, Chainflip); in the newest 7 days ({crosschain_latest7_window}) the leader was "
     "{crosschain_latest7_leader}."),
    ("demand_momentum", "Demand",
     "Momentum is fading: the last 4 weeks are {intents_volume_4w_vs_prior_4w|r2}x the 4 weeks before, and all of the "
     "rise since January is one step in late August ({stepup_before_usd_per_day|musd} to {stepup_after_usd_per_day|musd} "
     "a day) whose cause is unidentified."),
    ("capture_rate", "Capture",
     "NEAR keeps {captured_share_of_gross_fees|pct0} of the gross fees users pay, which is "
     "{captured_revenue_take_bps|d1} of {intents_gross_fee_bps|d1} basis points of volume (30 days)."),
    ("capture_trend", "Capture",
     "That take-rate peaked at {trend_take_bps_peak_week|d1} bps in the week of {trend_take_bps_peak_week_label} and was "
     "{trend_take_bps_latest_full_week|d1} bps in the latest full week ({trend_latest_full_week})."),
    ("volume_not_value", "Capture",
     "Volume is not value: {top_volume_channel} sends {top_volume_channel_usd_share|pct0} of 1Click volume but funds "
     "{top_volume_channel_buyback_share|pct1} of the buyback; swaps with no referral code are {no_referral_usd_share|pct0} "
     "of volume and fund {no_referral_buyback_share|pct0}."),
    ("accrual_share", "Accrual",
     "The buyback wallet takes in about {wallet_inflow_share_of_issuance|pct0} of the NEAR issued each year, and holds it: "
     "{wallet_outflow_share_of_inflows|pct1} of everything it received has ever left. Holding is custody, not a burn: "
     "supply still grew {realised_supply_growth|pct1} last year."),
    ("accrual_ceiling", "Accrual",
     "Even 100% of today's gross fees would cover only {gross_fees_to_issuance_usd|pct0} of issuance at today's price; "
     "break-even needs about {break_even_take_bps|d1} bps of all Intents volume."),
    ("valuation", "Valuation",
     "NEAR's market cap is {market_cap_to_captured_revenue|x0} its captured Intents revenue, annualised from 30 days."),
    ("usage", "Usage",
     "Organic NEAR-chain signers changed {organic_change_jan_to_latest|pctsigned} from January to the latest month."),
    ("agents", "AI agents",
     "NEAR AI Agent Market lists {agent_market_live_agents|int} live agents with {agent_market_delivered_jobs|int} "
     "delivered jobs all-time; {agent_market_agents_payable_in_near} of the catalogue agents accept NEAR."),
    ("verdict", "Verdict",
     "Scorecard verdict: \"{scorecard_verdict}\" (green, yellow, red: {scorecard_counts}). Measured over the whole "
     "buyback era instead of the latest 30 days, the same rules read \"bearish\" (THESIS.md section 5b; a test fails if "
     "that stops being true)."),
]

OPEN = [
    ("open_fee_layers", "1Click's app fees are {recon_appfees_share_of_gross|pct0} of DefiLlama's gross fees on "
                        "{recon_oneclick_share_of_volume|pct0} of the volume; the fee layers do not reconcile."),
    ("open_confidential", "Confidential settlement may hide volume while its fees still reach NEAR's wallets; no adjustment "
                          "factor exists."),
    ("open_step_up", "The cause of the August volume step-up is unidentified."),
    ("open_treasury_cut", "The treasury cut reads 0% on-chain against a 90/10 staker/treasury split in HSP-029 coverage."),
]

VERIFY = [
    "git clone https://github.com/lightokey839-rgb/Near-thesis-.git near-thesis && cd near-thesis",
    "python build.py --check      # every pinned input table matches its SHA-256 in data/MANIFEST.json",
    "python verify.py             # recomputes the headline numbers from the pinned tables, prints PASS/FAIL",
    "python build.py --test       # full rebuild of every number, THESIS.md and this page, then the tests",
]


def _metric_ids(text):
    return [m.group(1) for m in PLACEHOLDER.finditer(text)]


def build_claims(met, fill):
    """Fill every claim from metrics.json; return the list written to data/derived/claims.json."""
    out = []
    for cid, section, text in CLAIMS:
        ids = list(dict.fromkeys(_metric_ids(text)))
        kinds = {met[k]["kind"] for k in ids}
        out.append({"id": cid, "section": section, "claim": fill(text, met),
                    "label": "FACT" if kinds == {"FACT"} else "INFERENCE",
                    "metrics": [{"id": k, "value": met[k]["value"], "unit": met[k]["unit"], "kind": met[k]["kind"],
                                 "sources": met[k]["sources"], "method": met[k]["method"]} for k in ids]})
    for cid, text in OPEN:
        ids = list(dict.fromkeys(_metric_ids(text)))
        out.append({"id": cid, "section": "Open", "claim": fill(text, met), "label": "OPEN",
                    "metrics": [{"id": k, "value": met[k]["value"], "unit": met[k]["unit"], "kind": met[k]["kind"],
                                 "sources": met[k]["sources"], "method": met[k]["method"]} for k in ids]})
    return out


def brief_markdown(claims, claim_text, met):
    """A compact, self-contained brief: what an AI (or a person) needs to explain the dashboard, and nothing else."""
    lines = ["# NEAR Intents Thesis Engine: brief for reviewers", "",
             "Claim tested: " + claim_text, "",
             "Data as of: swaps to %s; NEAR price %s at %s. Every number below is a metric in data/derived/metrics.json, "
             "computed from pinned tables whose SHA-256 is in data/MANIFEST.json." % (
                 met["swaps_last_utc"]["value"], met["near_price_usd"]["value"], met["snapshot_block_time_utc"]["value"]), "",
             "Labels: FACT = measured from a named source; INFERENCE = arithmetic or a model on measured inputs; "
             "OPEN = unresolved. Not investment advice; no price targets.", ""]
    section = None
    for c in claims:
        if c["section"] != section:
            section = c["section"]
            lines += ["", "## " + section]
        ids = ", ".join("%s=%s" % (m["id"], json.dumps(m["value"]) if not isinstance(m["value"], float) else repr(round(m["value"], 4)))
                        for m in c["metrics"])
        lines.append("- [%s] %s%s" % (c["label"], c["claim"], (" (metrics: %s)" % ids) if ids else ""))
    lines += ["", "## Verify it yourself", ""] + ["    " + v for v in VERIFY]
    return "\n".join(lines) + "\n"


def panel_html(claims, brief, html_escape):
    rows = []
    section = None
    for c in claims:
        if c["section"] == "Open":
            continue
        if c["section"] != section:
            section = c["section"]
            rows.append('<h4>%s</h4>' % html_escape(section))
        chips = " ".join('<code title="%s">%s</code>' % (html_escape(m["kind"] + ": " + m["method"]), html_escape(m["id"]))
                         for m in c["metrics"])
        rows.append('<p class="claim"><span class="kind %s">%s</span>%s<br><span class="ids">%s</span></p>' % (
            c["label"].lower(), c["label"], html_escape(c["claim"]), chips))
    opens = "".join('<li>%s</li>' % html_escape(c["claim"]) for c in claims if c["section"] == "Open")
    verify = html_escape("\n".join(VERIFY))
    return EXPLAIN_HTML.replace("{{ROWS}}", "".join(rows)).replace("{{OPEN}}", opens).replace("{{VERIFY}}", verify).replace(
        "{{BRIEF_JSON}}", json.dumps(brief).replace("</", "<\\/"))


EXPLAIN_HTML = r"""<h2 id="explain">Explain this dashboard</h2>
<section class="card explain">
<h3>The verdict in plain English (generated from the data; no AI, no key)</h3>
<p class="sentence">Every sentence below is filled in by <code>python build.py</code> from <code>data/derived/metrics.json</code>. Hover a metric id to see how it is computed. The same sentences, with values, sources and labels, are in <code>data/derived/claims.json</code>.</p>
{{ROWS}}
<h4>Still open</h4><ul class="open">{{OPEN}}</ul>
<details><summary>Check one number yourself in about 2 minutes</summary><pre><code>{{VERIFY}}</code></pre></details>
<div class="presets" style="margin-top:10px"><button id="ex-copy">Copy brief for any AI chat</button><button id="ex-dl">Download brief (.md)</button><span id="ex-copied" class="q"></span></div>
</section>
<section class="card explain" id="ask">
<h3>Ask an AI about this dashboard (optional, your own key)</h3>
<p class="sentence">The AI sees only the brief above, and is told to answer from it, cite metric ids and say when the brief has no answer. You need your own API key. It stays in this page's memory: it is not saved, not logged and not sent anywhere except the provider you pick, and this page's security policy blocks every other destination. Use a key with a low spend limit, and delete it from the provider's console afterwards if you like. Answers are generated text: check any number against its metric id.</p>
<div class="ctl">
  <label>Provider
    <select id="ai-prov">
      <option value="anthropic">Claude (Anthropic API), model claude-opus-5-5</option>
      <option value="nearai">NEAR AI Cloud (private inference), OpenAI-compatible</option>
    </select></label>
  <label id="ai-model-wrap" hidden>NEAR AI model id <input id="ai-model" type="text" value="zai-org/GLM-5.1-FP8" spellcheck="false" autocomplete="off"></label>
  <label>API key <input id="ai-key" type="password" autocomplete="off" spellcheck="false" placeholder="paste your own key; it is kept in memory only"></label>
  <div class="presets">
    <button data-q="Summarize this dashboard for a hackathon judge in 5 bullets. Give the verdict first.">Summarize for a judge</button>
    <button data-q="What is the strongest evidence against the thesis's conclusion, and what is still open?">Strongest evidence against</button>
    <button data-q="Which three numbers should a reviewer verify first, and with which metric ids and commands?">What to verify first</button>
    <button data-q="Explain 'volume is not value' to someone new to NEAR, in under 120 words.">Explain 'volume is not value'</button>
  </div>
  <label>Your question <textarea id="ai-q" rows="3">Summarize this dashboard for a hackathon judge in 5 bullets. Give the verdict first.</textarea></label>
  <div class="presets"><button id="ai-go">Ask</button><button id="ai-forget">Forget key</button><span id="ai-status" class="q"></span></div>
</div>
<div id="ai-out" class="aiout" aria-live="polite"></div>
</section>
<script>
(function () {
  var BRIEF = {{BRIEF_JSON}};
  var $ = function (id) { return document.getElementById(id); };
  var SYSTEM = "You explain a published, reproducible investment-research dashboard to a hackathon judge. " +
    "Use only the brief below. Every number you state must appear in the brief, and you cite its metric id in backticks. " +
    "Keep the brief's FACT / INFERENCE / OPEN labels. If the brief does not answer the question, say so plainly. " +
    "Do not give investment advice or price targets. Be concise: under 250 words unless asked for more. Plain text, no tables.\n\n" + BRIEF;
  function status(t) { $("ai-status").textContent = t; }
  function show(t) { $("ai-out").textContent = t; }
  $("ex-copy").onclick = function () {
    var done = function () { $("ex-copied").textContent = "Copied. Paste it into any AI chat, then ask your question."; };
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(BRIEF).then(done, function () { $("ex-copied").textContent = "Copy blocked by the browser; use Download."; }); }
    else { $("ex-copied").textContent = "Copy is not available here; use Download."; }
  };
  $("ex-dl").onclick = function () {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([BRIEF], {type: "text/markdown"}));
    a.download = "near-intents-thesis-brief.md"; a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  };
  $("ai-prov").onchange = function () { $("ai-model-wrap").hidden = $("ai-prov").value !== "nearai"; };
  document.querySelectorAll("#ask .presets button[data-q]").forEach(function (b) { b.onclick = function () { $("ai-q").value = b.dataset.q; }; });
  $("ai-forget").onclick = function () { $("ai-key").value = ""; status("Key cleared from this page."); };
  async function askAnthropic(key, q) {
    var r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {"content-type": "application/json", "x-api-key": key, "anthropic-version": "2026-10-21",
                "anthropic-beta": "server-side-fallback-2026-07-01", "anthropic-dangerous-direct-browser-access": "true"},
      body: JSON.stringify({model: "claude-opus-5-5", max_tokens: 16000, system: SYSTEM, output_config: {effort: "low"},
                            fallbacks: "default", messages: [{role: "user", content: q}]})});
    var body = await r.json().catch(function () { return null; });
    if (!r.ok) { throw new Error("Anthropic API error " + r.status + ": " + ((body && body.error && body.error.message) || r.statusText)); }
    if (body.stop_reason === "refusal") {
      var cat = body.stop_details && body.stop_details.category;
      return "The model declined this question" + (cat ? " (" + cat + ")" : "") + ". Try rephrasing it.";
    }
    var text = (body.content || []).filter(function (b) { return b.type === "text"; }).map(function (b) { return b.text; }).join("\n").trim();
    return (text || "(empty answer)") + "\n\n[answered by " + body.model + "; stop_reason " + body.stop_reason + "]";
  }
  async function askNearAI(key, q, model) {
    var r = await fetch("https://cloud-api.near.ai/v1/chat/completions", {
      method: "POST",
      headers: {"content-type": "application/json", "authorization": "Bearer " + key},
      body: JSON.stringify({model: model, max_tokens: 2000,
                            messages: [{role: "system", content: SYSTEM}, {role: "user", content: q}]})});
    var raw = await r.text();
    var body = null; try { body = JSON.parse(raw); } catch (e) { body = null; }
    if (!r.ok) {
      var msg = body && (body.error && (body.error.message || body.error) || body.message || body.detail);
      throw new Error("NEAR AI Cloud error " + r.status + ": " + (typeof msg === "string" ? msg : raw.slice(0, 300)));
    }
    var c = body && body.choices && body.choices[0] && body.choices[0].message && body.choices[0].message.content;
    return (c || "(empty answer)").trim() + "\n\n[answered by " + ((body && body.model) || model) + " on NEAR AI Cloud]";
  }
  $("ai-go").onclick = async function () {
    var key = $("ai-key").value.trim(), q = $("ai-q").value.trim();
    if (!key) { status("Paste your own API key first. The rest of the page works without one."); return; }
    if (!q) { status("Type a question."); return; }
    $("ai-go").disabled = true; status("Asking..."); show("");
    try {
      var ans = $("ai-prov").value === "anthropic" ? await askAnthropic(key, q) : await askNearAI(key, q, $("ai-model").value.trim());
      show(ans); status("Done. Check numbers against their metric ids.");
    } catch (e) {
      show(""); status(String(e.message || e).slice(0, 400));
    } finally { $("ai-go").disabled = false; }
  };
})();
</script>"""

"""
explain.py - the dashboard's "Explain this dashboard" panel and data/derived/claims.json.

Three layers, from most to least verifiable:
  1. A plain-English summary built from metrics.json by the build. No AI, no network, no key: every sentence is a template
     whose numbers are {metric|format} placeholders, so each one traces to a metric id with a value, a source and a label.
  2. The same sentences as a machine-readable file (data/derived/claims.json) and a downloadable brief, so a screener or
     any AI tool can check claims without reading prose.
  3. For AI agents: llms.txt, brief.md, claims.json and metrics.json are published next to the page, so any agent can
     read the thesis with no key (GitHub Pages serves them as a read-only API).
  4. Optional: "Ask an AI". The viewer picks Claude, NEAR AI Cloud, any OpenAI-compatible API, or a local model, and
     brings their own key. The key stays in page memory, is never stored or logged, and is sent only to the address
     shown. The repository holds no key, and no server of ours ever sees one.
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


PAGES_URL = "https://lightokey839-rgb.github.io/Near-thesis-/"

# Files published next to the page (by .github/workflows/pages.yml) so that any AI agent or tool can read the thesis
# without a key: a read-only "API" served by GitHub Pages. No secrets are involved anywhere.
AGENT_FILES = [
    ("llms.txt", "Start here: what this is, where everything is, how to answer questions about it"),
    ("brief.md", "The verdict and every headline claim with its metric ids (Markdown)"),
    ("claims.json", "The same claims as JSON: text, label, metric values, sources, methods"),
    ("metrics.json", "Every metric the build computes (value, unit, FACT/INFERENCE, sources, method)"),
    ("THESIS.md", "The full thesis"),
]


def llms_txt(met, brief):
    lines = ["# NEAR Intents Thesis Engine", "",
             "> An evidence-first, reproducible investment thesis on NEAR: is NEAR Intents demand real, and how much of it does "
             "the NEAR token capture? Every number is computed from pinned, SHA-256-checked tables by one command. Not investment "
             "advice; no price targets.", "",
             "Verdict (scorecard, latest 30 days): %s. Data as of %s." % (met["scorecard_verdict"]["value"], met["swaps_last_utc"]["value"]), "",
             "## How to answer questions about this project", "",
             "- Use only the files below. Quote numbers exactly as they appear, with their metric id.",
             "- Keep the labels: FACT (measured), INFERENCE (arithmetic or a model), OPEN (unresolved).",
             "- If the files do not answer a question, say so. Do not add outside figures as if they were in the thesis.", "",
             "## Files (all public, no key needed)", ""]
    lines += ["- [%s](%s%s): %s" % (n, PAGES_URL, n, d) for n, d in AGENT_FILES]
    lines += ["- [Repository](https://github.com/lightokey839-rgb/Near-thesis-): code, pinned data, tests, CI", "",
              "## Verify a number", ""] + ["    " + v for v in VERIFY]
    return "\n".join(lines) + "\n"


def write_agent_files(dashboard_dir, brief, met):
    """dashboard/brief.md and dashboard/llms.txt; pages.yml publishes them with claims.json and metrics.json."""
    for name, text in (("brief.md", brief), ("llms.txt", llms_txt(met, brief))):
        with open("%s/%s" % (dashboard_dir, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


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


def ask_html(brief):
    eps = "".join('<li><a href="%s">%s</a><span class="q">%s</span></li>' % (n, n, d) for n, d in AGENT_FILES)
    presets = json.dumps(PROVIDERS).replace("</", "<\\/")
    return ASK_HTML.replace("{{ENDPOINTS}}", eps).replace("{{PAGES_URL}}", PAGES_URL).replace("{{PROVIDERS}}", presets)


# Providers whose APIs accept calls straight from a browser page (CORS preflight from this site's origin checked
# 14 Nov 2026). Model ids are left for the viewer to fill in where we would otherwise be guessing them.
PROVIDERS = [
    {"id": "anthropic", "label": "Claude (Anthropic API)", "kind": "anthropic", "base": "https://api.anthropic.com/v1", "model": "claude-opus-5-5"},
    {"id": "nearai", "label": "NEAR AI Cloud (private inference)", "kind": "openai", "base": "https://cloud-api.near.ai/v1", "model": "zai-org/GLM-5.1-FP8"},
    {"id": "openai", "label": "OpenAI", "kind": "openai", "base": "https://api.openai.com/v1", "model": ""},
    {"id": "openrouter", "label": "OpenRouter (hundreds of models)", "kind": "openai", "base": "https://openrouter.ai/api/v1", "model": ""},
    {"id": "gemini", "label": "Google Gemini (OpenAI-compatible endpoint)", "kind": "openai", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "model": ""},
    {"id": "groq", "label": "Groq", "kind": "openai", "base": "https://api.groq.com/openai/v1", "model": ""},
    {"id": "mistral", "label": "Mistral", "kind": "openai", "base": "https://api.mistral.ai/v1", "model": ""},
    {"id": "together", "label": "Together AI", "kind": "openai", "base": "https://api.together.xyz/v1", "model": ""},
    {"id": "local", "label": "A model on your own computer (Ollama, LM Studio)", "kind": "openai", "base": "http://localhost:11434/v1", "model": ""},
    {"id": "custom", "label": "Any other OpenAI-compatible API", "kind": "openai", "base": "https://", "model": ""},
]


EXPLAIN_HTML = r"""<h2 id="explain">Explain this dashboard</h2>
<section class="card explain">
<h3>The verdict in plain English (generated from the data; no AI, no key)</h3>
<p class="sentence">Every sentence below is filled in by <code>python build.py</code> from <code>data/derived/metrics.json</code>. Hover a metric id to see how it is computed. The same sentences, with values, sources and labels, are in <code>data/derived/claims.json</code>.</p>
{{ROWS}}
<h4>Still open</h4><ul class="open">{{OPEN}}</ul>
<details><summary>Check one number yourself in about 2 minutes</summary><pre><code>{{VERIFY}}</code></pre></details>
<div class="presets" style="margin-top:12px"><button id="ex-copy">Copy brief for any AI chat</button><button id="ex-dl">Download brief (.md)</button><span id="ex-copied" class="q"></span></div>
</section>
<script>
(function () {
  var BRIEF = {{BRIEF_JSON}};
  window.__THESIS_BRIEF = BRIEF;
  var $ = function (id) { return document.getElementById(id); };
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
})();
</script>"""


ASK_HTML = r"""<h2 id="ask">Ask an AI about this dashboard</h2>
<div class="two">
<section class="card">
<h3>For AI agents and tools (no key)</h3>
<p class="sentence">Any AI agent that can read a web page (Claude, ChatGPT, Perplexity, Cursor, your own scripts) can use these public files. GitHub Pages serves them as a read-only API; nothing here needs a key or a login.</p>
<ul class="endpoints">{{ENDPOINTS}}</ul>
<p class="sentence">Tell your agent: <code>Read {{PAGES_URL}}llms.txt and summarize the thesis for a judge, citing metric ids.</code></p>
<div class="presets"><button class="btn" id="ag-copy">Copy that instruction</button><span id="ag-copied" class="q"></span></div>
</section>
<section class="card" id="ask-box">
<h3>Or ask here with your own key (optional)</h3>
<p class="sentence">Pick Claude, NEAR AI Cloud, any OpenAI-compatible provider, or a model running on your own computer. The AI sees only the brief and is told to answer from it and cite metric ids. Your key stays in this page's memory: it is not saved or logged, and it is sent only to the address shown below. Use a key with a low spend limit. Answers are generated text: check numbers against their metric ids.</p>
<div class="ctl">
  <label>Provider <select id="ai-prov"></select></label>
  <label>API address (OpenAI-compatible base URL) <input id="ai-base" type="url" spellcheck="false" autocomplete="off"></label>
  <label>Model id <input id="ai-model" type="text" spellcheck="false" autocomplete="off" placeholder="the model id from your provider's docs"></label>
  <label>API key <input id="ai-key" type="password" autocomplete="off" spellcheck="false" placeholder="your own key (not needed for a local model)"></label>
  <p class="q" id="ai-hint"></p>
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
</div>
<script>
(function () {
  var PROVIDERS = {{PROVIDERS}};
  var BRIEF = window.__THESIS_BRIEF || "";
  var $ = function (id) { return document.getElementById(id); };
  var SYSTEM = "You explain a published, reproducible investment-research dashboard to a hackathon judge. " +
    "Use only the brief below. Every number you state must appear in the brief, and you cite its metric id in backticks. " +
    "Keep the brief's FACT / INFERENCE / OPEN labels. If the brief does not answer the question, say so plainly. " +
    "Do not give investment advice or price targets. Be concise: under 250 words unless asked for more. Plain text, no tables.\n\n" + BRIEF;
  var HINTS = {
    local: "Start your local server first. Ollama: set OLLAMA_ORIGINS to this page's address so the browser may call it; LM Studio: use http://localhost:1234/v1 and enable CORS.",
    custom: "Any API that speaks the OpenAI chat-completions format and allows browser calls (CORS).",
    anthropic: "Uses the Messages API directly from your browser."
  };
  PROVIDERS.forEach(function (p) { var o = document.createElement("option"); o.value = p.id; o.textContent = p.label; $("ai-prov").appendChild(o); });
  function pick() {
    var p = PROVIDERS.filter(function (x) { return x.id === $("ai-prov").value; })[0];
    $("ai-base").value = p.base; $("ai-model").value = p.model; $("ai-base").readOnly = p.kind === "anthropic";
    $("ai-hint").textContent = HINTS[p.id] || "";
  }
  $("ai-prov").onchange = pick; pick();
  function status(t) { $("ai-status").textContent = t; }
  function show(t) { $("ai-out").textContent = t; }
  $("ag-copy").onclick = function () {
    var t = "Read {{PAGES_URL}}llms.txt and summarize the thesis for a judge, citing metric ids.";
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(t).then(function () { $("ag-copied").textContent = "Copied."; }); }
  };
  document.querySelectorAll("#ask-box .presets button[data-q]").forEach(function (b) { b.onclick = function () { $("ai-q").value = b.dataset.q; }; });
  $("ai-forget").onclick = function () { $("ai-key").value = ""; status("Key cleared from this page."); };
  function okBase(u) {
    try { var x = new URL(u); } catch (e) { return false; }
    return x.protocol === "https:" || (x.protocol === "http:" && (x.hostname === "localhost" || x.hostname === "127.0.0.1"));
  }
  async function askAnthropic(key, model, q) {
    var body = {model: model, max_tokens: 16000, system: SYSTEM, output_config: {effort: "low"}, messages: [{role: "user", content: q}]};
    var headers = {"content-type": "application/json", "x-api-key": key, "anthropic-version": "2026-10-21",
                   "anthropic-dangerous-direct-browser-access": "true"};
    if (model === "claude-opus-5-5") { body.fallbacks = "default"; headers["anthropic-beta"] = "server-side-fallback-2026-07-01"; }
    var r = await fetch("https://api.anthropic.com/v1/messages", {method: "POST", headers: headers, body: JSON.stringify(body)});
    var b = await r.json().catch(function () { return null; });
    if (!r.ok) { throw new Error("Anthropic API error " + r.status + ": " + ((b && b.error && b.error.message) || r.statusText)); }
    if (b.stop_reason === "refusal") {
      var cat = b.stop_details && b.stop_details.category;
      return "The model declined this question" + (cat ? " (" + cat + ")" : "") + ". Try rephrasing it.";
    }
    var text = (b.content || []).filter(function (x) { return x.type === "text"; }).map(function (x) { return x.text; }).join("\n").trim();
    return (text || "(empty answer)") + "\n\n[answered by " + b.model + "; stop_reason " + b.stop_reason + "]";
  }
  async function askOpenAICompatible(base, key, model, q) {
    var headers = {"content-type": "application/json"};
    if (key) { headers.authorization = "Bearer " + key; }
    var r = await fetch(base.replace(/\/+$/, "") + "/chat/completions", {method: "POST", headers: headers,
      body: JSON.stringify({model: model, max_tokens: 2000, messages: [{role: "system", content: SYSTEM}, {role: "user", content: q}]})});
    var raw = await r.text();
    var b = null; try { b = JSON.parse(raw); } catch (e) { b = null; }
    if (!r.ok) {
      var e = b && (b.error && (b.error.message || b.error) || b.message || b.detail);
      throw new Error("API error " + r.status + ": " + (typeof e === "string" ? e : raw.slice(0, 300)));
    }
    var c = b && b.choices && b.choices[0] && b.choices[0].message && b.choices[0].message.content;
    if (Array.isArray(c)) { c = c.map(function (x) { return x.text || ""; }).join(""); }
    return (c || "(empty answer)").trim() + "\n\n[answered by " + ((b && b.model) || model) + " via " + new URL(base).host + "]";
  }
  $("ai-go").onclick = async function () {
    var p = PROVIDERS.filter(function (x) { return x.id === $("ai-prov").value; })[0];
    var base = $("ai-base").value.trim(), model = $("ai-model").value.trim(), key = $("ai-key").value.trim(), q = $("ai-q").value.trim();
    show("");
    if (!okBase(base)) { status("The API address must start with https:// (or http://localhost for a local model)."); return; }
    if (!model) { status("Enter the model id from your provider's docs."); return; }
    if (!key && p.id !== "local") { status("Paste your own API key first. The rest of the page works without one."); return; }
    if (!q) { status("Type a question."); return; }
    $("ai-go").disabled = true; status("Asking " + new URL(base).host + "..."); show("");
    try {
      var ans = p.kind === "anthropic" ? await askAnthropic(key, model, q) : await askOpenAICompatible(base, key, model, q);
      show(ans); status("Done. Check numbers against their metric ids.");
    } catch (e) {
      show(""); status(String(e.message || e).slice(0, 400) + (String(e).indexOf("Failed to fetch") >= 0 ? " (the provider may not allow browser calls, or the address is wrong)" : ""));
    } finally { $("ai-go").disabled = false; }
  };
})();
</script>"""

"""
layout.py - the dashboard's page shell: sidebar navigation, overview stat cards, the verdict card, the signal rail,
and the page template with its styles. Content (numbers, sentences, charts, queries) comes from build_dashboard.py and
explain.py; this file only arranges it. Icons are inline SVG, so the page loads nothing extra.
"""

import html

REPO_URL = "https://github.com/lightokey839-rgb/Near-thesis-"

_I = {  # 24x24 stroke icons (drawn for this page)
    "overview": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    "explain": '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>',
    "scorecard": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>',
    "scenarios": '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    "demand": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "value-capture": '<circle cx="12" cy="12" r="8"/><path d="M14.5 9.5c-.5-1-1.5-1.5-2.5-1.5-1.5 0-2.5.8-2.5 2s1 1.6 2.5 2 2.5.8 2.5 2-1 2-2.5 2c-1 0-2-.5-2.5-1.5M12 6.5V8M12 16v1.5"/>',
    "valuation": '<path d="M12 4v16M5 8h14"/><path d="M5 8l-3 6a3 3 0 006 0zM19 8l-3 6a3 3 0 006 0z"/>',
    "usage": '<circle cx="9" cy="8" r="3"/><path d="M3 19c0-3 3-5 6-5s6 2 6 5"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14c3 0 5 1.6 5 4"/>',
    "ai-agents": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/><rect x="10" y="10" width="4" height="4"/>',
    "model": '<path d="M4 19h16"/><path d="M6 16V9M10 16V5M14 16v-6M18 16V7"/>',
    "ask": '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
    "volume": '<path d="M4 18V10M10 18V6M16 18v-9M22 18H2"/>',
    "take": '<circle cx="12" cy="12" r="8"/><path d="M12 12V4a8 8 0 018 8z"/>',
    "buyback": '<path d="M4 12a8 8 0 0114-5.3L20 9"/><path d="M20 4v5h-5"/><path d="M20 12a8 8 0 01-14 5.3L4 15"/><path d="M4 20v-5h5"/>',
    "multiple": '<path d="M6 6l12 12M18 6L6 18"/>',
    "github": '<path d="M9 19c-4 1.3-4-2-6-2.5m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 00-1.3-3.2 4.2 4.2 0 00-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 00-6.2 0C6.6 2.3 5.6 2.6 5.6 2.6a4.2 4.2 0 00-.1 3.2A4.6 4.6 0 004.2 9c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
    "doc": '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>',
    "check": '<path d="M5 12l4 4 10-10"/>',
}


def icon(name, size=20):
    return ('<svg class="ic" width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>' % (size, size, _I.get(name, _I["overview"])))


def wrap_id(key):
    """A metric id that may wrap only after its underscores."""
    return html.escape(key).replace("_", "_<wbr>")


def stat_card(met, key, fmt, label, ic):
    m = met.get(key)
    v = html.escape(fmt(m["value"])) if m else "not computed"
    k = '<div class="k">%s &middot; <code>%s</code></div>' % (m["kind"], wrap_id(key)) if m else ""
    return ('<div class="stat"><div class="stat-ic">%s</div><div class="l">%s</div><div class="v">%s</div>%s</div>'
            % (icon(ic, 22), html.escape(label), v, k))


def mini_tile(met, key, fmt, label):
    m = met.get(key)
    if not m:
        return '<div class="tile"><div class="v">not computed</div><div class="l">%s</div></div>' % html.escape(label)
    return '<div class="tile"><div class="v">%s</div><div class="l">%s</div><div class="k">%s &middot; <code>%s</code></div></div>' % (
        html.escape(fmt(m["value"])), html.escape(label), m["kind"], wrap_id(key))


def verdict_card(met):
    g, y, r = met["scorecard_counts"]["value"]
    by = {w[0]: w for w in met.get("scorecard_by_window", {}).get("value", [])}
    era = by.get("since buybacks began")
    latest, ref = met["trend_take_bps_latest_full_week"]["value"], met["captured_revenue_take_bps"]["value"]
    return """<div class="verdict card">
  <div class="vc-head"><span>Scorecard verdict</span><span class="pill">Latest 30 days</span></div>
  <div class="vc-dots"><span class="dot green">%d</span><span class="dot yellow">%d</span><span class="dot red">%d</span></div>
  <div class="vc-big">%s</div>
  <div class="vc-sub">green &middot; yellow &middot; red signals in <code>thesis.yaml</code></div>
  <div class="vc-row"><span>Whole buyback era</span><b>%s</b></div>
  <div class="vc-row"><span>Take-rate, latest full week</span><b class="down">%.1f bps <small>vs %.1f (30 days)</small></b></div>
  <div class="k">INFERENCE &middot; <code>scorecard_verdict</code>, <code>scorecard_by_window</code>, <code>trend_take_bps_latest_full_week</code></div>
</div>""" % (g, y, r, html.escape(met["scorecard_verdict"]["value"]), html.escape(era[4] if era else "?"), latest, ref)


def signal_rail(met, fmt_value, claims):
    cards = []
    for r in met["scorecard"]["value"]:
        unit = met.get(r["metric"], {}).get("unit", "")
        cards.append("""<div class="sig">
  <span class="badge %s">%s</span>
  <div class="sig-t">%s</div>
  <div class="sig-q">%s</div>
  <div class="sig-f"><span class="sig-v">%s</span><code>%s</code></div>
</div>""" % (r["status"].replace(" ", "-"), r["status"].upper(), html.escape(r["question"]), html.escape(r["id"]),
             html.escape(fmt_value(r.get("value"), unit)), wrap_id(r["metric"])))
    opens = "".join('<div class="sig open"><span class="badge open">OPEN</span><div class="sig-q">%s</div></div>' % html.escape(c["claim"])
                    for c in claims if c["label"] == "OPEN")
    return ('<aside class="rail" aria-label="Signals"><h2 class="rail-h">Signals</h2>%s<h2 class="rail-h">Still open</h2>%s</aside>'
            % ("".join(cards), opens))


def side_nav(sections, slug):
    items = [("overview", "Overview", "overview"), ("explain", "Explain", "explain"), ("scorecard", "Scorecard", "scorecard"),
             ("scenarios", "Scenarios", "scenarios")] + [(slug(s), s, slug(s)) for s in sections] + [("ask", "Ask an AI", "ask")]
    links = "".join('<a href="#%s" data-sec="%s">%s<span>%s</span></a>' % (a, a, icon(ic), html.escape(t)) for a, t, ic in items)
    return """<aside class="side">
  <a class="brand" href="#overview"><span class="logo">N</span><span><b>NEAR Intents</b><small>Thesis Engine</small></span></a>
  <nav class="nav">%s</nav>
  <div class="side-foot">
    <a href="%s">%s<span>Repository</span></a>
    <a href="THESIS.md">%s<span>THESIS.md</span></a>
    <a href="llms.txt">%s<span>For AI agents</span></a>
  </div>
</aside>""" % (links, REPO_URL, icon("github"), icon("doc"), icon("ai-agents"))


CSS = r"""
:root{--bg1:#eef0fb;--bg2:#fbeef2;--card:#fff;--ink:#1e2240;--muted:#6b7090;--line:#ececf3;--accent:#5146d8;--accent2:#e5348a;
--fact:#16936b;--inf:#b26a00;--code:#f4f4f9;--side:#fff;--shadow:0 10px 30px rgba(40,40,90,.08)}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg1:#11121a;--bg2:#17111a;--card:#1c1d28;--ink:#e9e9f2;--muted:#a3a6bd;--line:#2c2e3d;--accent:#8c84ff;--accent2:#ff5fa8;--fact:#5fd1a2;--inf:#f0a64a;--code:#24263a;--side:#191a24;--shadow:none}}
:root[data-theme="dark"]{--bg1:#11121a;--bg2:#17111a;--card:#1c1d28;--ink:#e9e9f2;--muted:#a3a6bd;--line:#2c2e3d;--accent:#8c84ff;--accent2:#ff5fa8;--fact:#5fd1a2;--inf:#f0a64a;--code:#24263a;--side:#191a24;--shadow:none}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;color:var(--ink);font:15px/1.5 "Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:linear-gradient(135deg,var(--bg1),var(--bg2)) fixed;min-height:100vh}
.app{display:grid;grid-template-columns:240px minmax(0,1fr) 300px;max-width:1560px;margin:24px auto;background:var(--card);border-radius:22px;box-shadow:var(--shadow);overflow:clip}
.side{background:var(--side);border-right:1px solid var(--line);padding:26px 18px;position:sticky;top:0;align-self:start;height:100vh;overflow:auto;display:flex;flex-direction:column}
.brand{display:flex;gap:10px;align-items:center;text-decoration:none;color:var(--ink);padding:0 8px 22px;border-bottom:1px solid var(--line);margin-bottom:18px}
.brand .logo{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;display:grid;place-items:center;font-weight:800;font-size:18px}
.brand b{display:block;font-size:15px;line-height:1.1}.brand small{color:var(--muted);font-size:12px}
.nav,.side-foot{display:flex;flex-direction:column;gap:4px}.side-foot{margin-top:auto;padding-top:16px;border-top:1px solid var(--line)}
.nav a,.side-foot a{display:flex;gap:12px;align-items:center;padding:10px 12px;border-radius:12px;color:var(--muted);text-decoration:none;font-size:14px}
.nav a:hover,.side-foot a:hover{background:var(--code);color:var(--ink)}
.nav a.active{background:var(--accent);color:#fff;box-shadow:0 6px 16px rgba(81,70,216,.35)}
.main{padding:28px 30px 60px;min-width:0;background:linear-gradient(180deg,rgba(81,70,216,.03),transparent 300px)}
.rail{border-left:1px solid var(--line);padding:26px 18px;background:var(--side);min-width:0;position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto}
.rail-h{font-size:18px;margin:0 0 14px;padding-bottom:12px;border-bottom:1px solid var(--line)}.rail-h~.rail-h{margin-top:26px}
.sig{border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:12px;background:var(--card)}
.sig-t{font-weight:600;margin:8px 0 2px;line-height:1.3}.sig-q{color:var(--muted);font-size:12px}.sig.open .sig-q{color:var(--ink);font-size:13px;margin-top:8px}
.sig-f{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:10px}.sig-v{font-weight:700;color:var(--accent2)}
.sig-f code{font-size:10px;color:var(--muted);text-align:right}
.badge{display:inline-block;font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;border:1px solid}
.badge.green{color:#16936b;background:#e7f7f0;border-color:#a8e3cc}.badge.yellow{color:#9a6a00;background:#fff6dd;border-color:#f3d98a}
.badge.red{color:#c23b3b;background:#fdecec;border-color:#f3b4b4}.badge.open{color:#5146d8;background:#eeedff;border-color:#c9c5fb}.badge.not-computed{color:#6b7079;border-color:#ccc}
h1{font-size:26px;margin:0}h2{font-size:20px;margin:40px 0 14px;scroll-margin-top:16px}h3{font-size:16px;margin:0 0 6px}h4{margin:14px 0 4px;font-size:14px}
.top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-bottom:18px}.lead{color:var(--muted);margin:6px 0 0;font-size:13px;max-width:760px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:var(--shadow)}
.stat-ic{width:46px;height:46px;border-radius:50%;background:#45486b;color:#fff;display:grid;place-items:center;margin-bottom:14px;box-shadow:0 6px 14px rgba(40,40,90,.25)}
.stat .l{color:var(--muted);font-size:13px}.stat .v{font-size:28px;font-weight:600;color:var(--accent2);letter-spacing:-.5px;margin:2px 0 4px}
.k{color:var(--muted);font-size:11px;overflow-wrap:normal;margin-top:4px}
.hero{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;margin-top:16px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;align-content:start}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}.tile .v{font-size:20px;font-weight:650}.tile .l{font-size:13px}
.verdict .vc-head{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:14px}
.pill{border:1px solid var(--line);border-radius:10px;padding:4px 10px;font-size:12px;color:var(--ink)}
.vc-dots{display:flex;gap:8px;margin:16px 0 6px}.dot{min-width:40px;text-align:center;border-radius:10px;padding:4px 8px;font-weight:700;color:#fff}
.dot.green{background:#16936b}.dot.yellow{background:#c99400}.dot.red{background:#c23b3b}
.vc-big{font-size:24px;font-weight:800;line-height:1.15;color:var(--ink)}.vc-sub{color:var(--muted);font-size:12px;margin:4px 0 12px}
.vc-row{display:flex;justify-content:space-between;gap:10px;border-top:1px solid var(--line);padding:8px 0;font-size:13px}.vc-row span{color:var(--muted)}
.down{color:#c23b3b}.down small{color:var(--muted);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;min-width:0;box-shadow:var(--shadow)}
.sentence{margin:0 0 10px}.chart{position:relative;height:280px}.meta{color:var(--muted);font-size:12px;margin:10px 0 6px;word-break:break-word}
.kind{font-weight:700;font-size:11px;padding:1px 7px;border-radius:999px;border:1px solid currentColor;margin-right:6px}.kind.fact{color:var(--fact)}.kind.inference{color:var(--inf)}.kind.open{color:var(--accent)}
details summary{cursor:pointer;font-size:13px;color:var(--muted)}pre{background:var(--code);padding:10px;border-radius:10px;overflow:auto;max-height:340px;font-size:12px}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px}a{color:inherit}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}
th{color:var(--muted);font-weight:500;text-align:left;padding:12px 10px;border-bottom:1px solid var(--line)}td{padding:12px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.q{color:var(--muted);font-size:12px}.st{font-weight:600;font-size:11px;padding:3px 10px;border-radius:999px;border:1px solid}
.st.green{color:#16936b;background:#e7f7f0;border-color:#a8e3cc}.st.yellow{color:#9a6a00;background:#fff6dd;border-color:#f3d98a}.st.red{color:#c23b3b;background:#fdecec;border-color:#f3b4b4}.st.not-computed{color:#6b7079}
.ctl{display:grid;gap:10px;margin:8px 0 12px}.ctl label{display:grid;gap:4px;font-size:13px}.ctl label.chk{display:flex;gap:8px;align-items:center}
.ctl input[type=range]{width:100%;accent-color:var(--accent)}.presets{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.presets button,.btn{font:inherit;font-size:13px;padding:7px 14px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.presets button:hover{border-color:var(--accent);color:var(--accent)}#sc-reset{margin-left:auto}
#ai-go,#ex-copy{background:var(--accent);color:#fff;border-color:var(--accent)}#ai-go:hover,#ex-copy:hover{color:#fff;filter:brightness(1.1)}
.explain h4{margin:14px 0 4px;font-size:14px}.claim{margin:4px 0 10px}.claim .ids{font-size:11px;color:var(--muted)}.claim .ids code{font-size:11px;margin-right:4px;cursor:help}
ul.open{margin:4px 0 8px;padding-left:20px}
.ctl select,.ctl textarea,.ctl input[type=text],.ctl input[type=password],.ctl input[type=url]{font:inherit;font-size:14px;padding:8px 10px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);width:100%}
.aiout{white-space:pre-wrap;background:var(--code);border-radius:10px;padding:12px;min-height:2em;font-size:14px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}
.endpoints{list-style:none;padding:0;margin:8px 0}.endpoints li{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding:8px 0;font-size:13px}
.endpoints a{color:var(--accent);word-break:break-all}
button:disabled{opacity:.5;cursor:wait}
footer{color:var(--muted);font-size:12px;margin-top:40px}
@media (max-width:1280px){.app{grid-template-columns:220px minmax(0,1fr)}.rail{position:static;max-height:none;overflow:visible;grid-column:2;border-left:0;border-top:1px solid var(--line);display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}.rail-h{grid-column:1/-1;margin:10px 0 0}.sig{margin:0}}
@media (max-width:1050px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.hero{grid-template-columns:1fr}}
@media (max-width:820px){.app{grid-template-columns:1fr;margin:0;border-radius:0}.side{position:sticky;top:0;z-index:5;height:auto;flex-direction:row;align-items:center;gap:10px;padding:10px 12px;border-right:0;border-bottom:1px solid var(--line)}
.brand{border:0;padding:0;margin:0}.brand span:last-child{display:none}.nav{flex-direction:row;overflow-x:auto;gap:2px;scrollbar-width:none}.nav a{padding:8px 10px;white-space:nowrap}.nav a span{font-size:13px}
.side-foot{display:none}.main{padding:18px 16px 40px}.rail{grid-column:1;padding:18px 16px}.stats{grid-template-columns:1fr 1fr;gap:10px}.stat{padding:14px}.stat .v{font-size:22px}}
@media (max-width:420px){.stats{grid-template-columns:1fr}}
"""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'unsafe-inline'; img-src data:; connect-src https: http://localhost:* http://127.0.0.1:*; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<meta name="description" content="Is NEAR Intents demand real, and does the NEAR token capture it? A reproducible investment thesis. AI agents: read llms.txt.">
<link rel="alternate" type="text/markdown" href="brief.md" title="Brief for AI agents">
<title>NEAR Intents Thesis</title>
<style>{{CSS}}</style></head><body>
<div class="app">
{{SIDE}}
<main class="main">
<div class="top" id="overview"><div><h1>Overview</h1>
<p class="lead">Is NEAR Intents demand real, and does the NEAR token capture it? Every number comes from pinned tables in this repo (<code>data/</code>) and is rebuilt by <code>python build.py</code>; each chart shows its query. FACT = measured; INFERENCE = derived by arithmetic or modelling. Data as of {{STAMP}}.</p></div></div>
<div class="stats">{{STATS}}</div>
<div class="hero"><div class="tiles">{{TILES}}</div>{{VERDICT}}</div>
{{BODY}}
<footer>Built by dashboard/build_dashboard.py. Sources: NEAR Intents Explorer API (1Click swaps), Google BigQuery public dataset crypto_near_mainnet_us, NEAR JSON-RPC, DefiLlama, CoinGecko. Not investment advice.</footer>
</main>
{{RAIL}}
</div>
{{CHARTJS}}
<script>
const CHARTS = {{DATA}};
const css = getComputedStyle(document.documentElement);
if (window.Chart) {
  Chart.defaults.color = css.getPropertyValue('--muted').trim();
  Chart.defaults.borderColor = css.getPropertyValue('--line').trim();
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.font.family = 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  Chart.defaults.elements.bar.borderRadius = 6;
  Chart.defaults.elements.bar.maxBarThickness = 16;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  for (const [id, cfg] of Object.entries(CHARTS)) {
    cfg.options = Object.assign({interaction: {mode: 'index', intersect: false}, plugins: {legend: {position: 'top', align: 'start'}}}, cfg.options || {});
    if (id === 'peers') cfg.options.scales.y.type = 'logarithmic';
    const lg = cfg.options.plugins && cfg.options.plugins.legend;
    if (lg && lg.labels && lg.labels.filter === 'nonempty') lg.labels.filter = (item) => item.text !== '';
    const el = document.getElementById('cv-' + id);
    if (el) new Chart(el, cfg);
  }
} else {
  document.querySelectorAll('.chart').forEach(c => c.innerHTML = '<p class="meta">Chart library could not load (offline?). The data and query are still below.</p>');
}
(function () {  // highlight the section in view
  const links = [...document.querySelectorAll('.nav a[data-sec]')];
  const targets = links.map(a => [a.dataset.sec, document.getElementById(a.dataset.sec)]).filter(t => t[1]);
  let ticking = false;
  function update() {
    ticking = false;
    const line = window.innerHeight * 0.35;
    let cur = targets.length ? targets[0][0] : null;
    for (const [id, el] of targets) { if (el.getBoundingClientRect().top <= line) cur = id; }
    links.forEach(a => a.classList.toggle('active', a.dataset.sec === cur));
  }
  let last = 0;
  window.addEventListener('scroll', () => { const now = Date.now(); if (now - last > 60) { last = now; update(); } else if (!ticking) { ticking = true; setTimeout(update, 80); } }, {passive: true});
  update();
})();
</script></body></html>
"""

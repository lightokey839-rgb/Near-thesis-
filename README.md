# NEAR Intents Thesis Engine

[![build](https://github.com/lightokey839-rgb/Near-thesis-/actions/workflows/build.yml/badge.svg)](https://github.com/lightokey839-rgb/Near-thesis-/actions/workflows/build.yml)

An evidence-first investment thesis on NEAR: **is NEAR Intents demand real, and how much of it does the NEAR token capture?** It is built from 818,000 NEAR Intents (1Click) swaps, the NEAR BigQuery public dataset, the NEAR RPC, DefiLlama and CoinGecko. One command rebuilds every number, the thesis text and the dashboard from pinned data tables.

- **Thesis:** [THESIS.md](THESIS.md) opens with a one-page decision memo, then tests the chain **demand → capture → accrual**: is Intents activity real, how much of it does NEAR keep, and does that outweigh issuance? Could AI agents add demand that reaches the token? Agents are measured from NEAR AI Agent Market's own public data, with evidence tiers so bots are never counted as agents. It covers evidence for and against, a risk matrix, a catalyst calendar and what would change my mind.
- **Headline finding, only visible in swap-level data:** [volume is not value](THESIS.md#3b-volume-is-not-value-who-actually-pays-for-nears-buyback). The app that sends the most 1Click volume pays almost none of NEAR's buyback, and small channels fund most of it.
- **Dashboard:** `dashboard/index.html` has a scorecard, an interactive five-year scenario panel (sliders, presets, reset) and 24 charts. Each chart shows its query and one plain sentence. Hosted copy: https://lightokey839-rgb.github.io/Near-thesis-/ (published by [`pages.yml`](.github/workflows/pages.yml) once the repository is public).
- **Scenarios:** [`scenarios.json`](scenarios.json) holds the bear, base, bull and stress assumptions. [`pipeline/scenario_model.py`](pipeline/scenario_model.py) runs them and the reverse valuation (THESIS.md section 6b); the dashboard runs the same model in the browser, and a test checks that the two match.
- **Scorecard rules:** [thesis.yaml](thesis.yaml) holds the claim and its numeric tripwires. Each build marks every signal green, yellow or red.
- **Red-team log:** [docs/RED_TEAM_2026-11-11.md](docs/RED_TEAM_2026-11-11.md) records what we checked, what survived and what we corrected.

NEAR Hackathon, track **Investment Thesis** (`thesis`). Not investment advice; no price targets.

## Reproduce in about 2 minutes (no keys, no internet needed for the build)

Needs Python 3.8+. No packages to install. Tested on Python 3.15 (Windows). On every push, [GitHub Actions](.github/workflows/build.yml) rebuilds on Ubuntu and Windows (Python 3.12), runs the tests, and fails if the rebuild changes any committed file.

```bash
git clone https://github.com/lightokey839-rgb/Near-thesis-.git near-thesis
cd near-thesis
python build.py --test
```

**You should see:**
1. `all 57 pinned tables match data/MANIFEST.json`. The input tables are exactly the ones we analysed (SHA-256).
2. `metrics: 246 computed, 0 sections not computed`, which writes `data/derived/metrics.json`. This includes the HSP-029 sensitivity tables, the five-year scenarios and reverse valuation, the lead-lag statistics and the `thesis.yaml` scorecard.
3. `THESIS.md written (every number filled from metrics.json)`
4. `dashboard: 24 charts -> dashboard/index.html`
5. The tests (32), ending in `OK`. They include checks that sentences stating a conclusion in words still match the data, and that the browser's scenario model gives exactly the same numbers as the Python one. That check needs Node.js and is skipped without it.

**Offline viewing (optional):** the page loads Chart.js 4.4.1 from cdnjs with an integrity hash. To make it fully offline, put the same file in `dashboard/vendor/chart.umd.min.js`. The build checks its SHA-512 against the published hash and inlines it.

Then open `dashboard/index.html` in a browser (it loads Chart.js 4.4.1 from cdnjs). You should see 10 headline tiles, the scorecard (verdict, signals and their status) and 24 charts. Under each chart, **"Query behind this chart"** shows the exact SQL file or Python function that produced it.

**Why the numbers can't be invented:**
- **Generated, not typed:** THESIS.md is generated from `docs/THESIS.template.md`. Every number in it is a placeholder like `{wallet_inflow_share_of_issuance|pct0}`, filled from `metrics.json`. A placeholder naming a metric that doesn't exist stops the build.
- **Traceable:** each metric in `metrics.json` records its source files, its method, and whether it is a FACT (measured) or an INFERENCE (arithmetic or model).
- **Gaps stay visible:** if an input is missing, the metric is listed under `not_computed`; it is never estimated.

## What is where

```
build.py                    one command: verify -> (refresh) -> metrics -> THESIS.md -> dashboard
THESIS.md                   generated thesis (edit docs/THESIS.template.md instead)
thesis.yaml                 the claim and its numeric tripwires (bullish/bearish thresholds per signal)
dashboard/                  build_dashboard.py -> index.html
pipeline/
  download_swaps.py         1Click swap history from the NEAR Intents Explorer API (needs a JWT)
  summarize_swaps.py        raw swaps -> data/summary/*.csv
  audit_swaps.py            red-team checks: integrity, pricing, fee unit, refunds, buyback fees -> data/audit/
  check_gaps.py             asks the API whether gaps in our file are real (needs the JWT)
  bq_run.py                 runs sql/*.sql on BigQuery with a dry run, a per-query cap and a monthly budget -> data/bq/
  buyback_wallet.py         weekly balance of buybacks.multisignature.near from the NEAR archival RPC -> data/onchain/
  fetch_market.py           price, supply, stake, inflation, peers, DefiLlama Intents data -> data/market/
  metrics.py                pinned tables -> data/derived/metrics.json
  models.py                 HSP-029 sensitivity, lead-lag (block bootstrap, placebos, power), thesis.yaml scorecard
  render.py                 Markdown tables for THESIS.md
sql/                        every BigQuery query (each starts with a title and the sentence shown on the dashboard)
data/                       pinned snapshot tables (small CSV/JSON) + MANIFEST.json; the 1.1 GB raw swap file is NOT committed
docs/                       thesis template, red-team log
tests/                      unit tests; network code is tested against local mock servers
```

## Re-running from the original sources (optional, needs your own access)

| Source | Command | Needs | Cost |
|---|---|---|---|
| Market, supply, peers | `python build.py --refresh market` | internet | free public APIs (DefiLlama, CoinGecko, NEAR RPC) |
| Buyback wallet history | `python build.py --refresh wallet` | internet | free archival RPC; slow on purpose (rate limits) |
| BigQuery | `python build.py --refresh bq` | `pip install google-cloud-bigquery pydata-google-auth`, a Google Cloud project in `.env` as `BQ_PROJECT` (Sandbox is fine) | ~200 GB scanned in total, inside the free 1 TB/month; every query is dry-run and capped |
| AI Agent Market snapshot | `python pipeline/agent_market.py`, then `python build.py --repin` | internet | free public API (market.near.ai/v1), about 20 requests |
| Supply history and revenue wallets | `python pipeline/chain_history.py`, then `python build.py --repin` | internet | free archival RPC, about 5-10 minutes |
| Swaps | `python pipeline/download_swaps.py`, then `python build.py --refresh swaps` | a NEAR Intents Explorer JWT in `NEAR_INTENTS_JWT` (see `.env.example`) | 1 request per 5 s; ~818 pages for 28 Sep–10 Nov |

After a refresh, `build.py` re-pins the tables (rewrites `data/MANIFEST.json`), so the change shows up in the git diff. Secrets live only in `.env`, which git ignores; scripts never print them.

## Data sources and as-of dates

- **NEAR Intents Explorer API** (`explorer.near-intents.org/api/v0/transactions`): 1Click swaps from 2026-09-28 06:45 to 2026-11-10 12:48 UTC. It covers 1Click only, not all Intents.
- **Google BigQuery** `bigquery-public-data.crypto_near_mainnet_us` (region us-east1): transactions, receipt_actions and account_changes, queried 2026-11-11 for 1 Jan–9 Nov 2026.
- **NEAR JSON-RPC** (fastnear, near.org archival): supply, validators, protocol config and wallet balances, read 2026-11-11.
- **DefiLlama** (`api.llama.fi`, `coins.llama.fi`): Intents volume, fees, revenue and NEAR price. Its Intents volume comes from a NEAR-maintained Dune table, so it is only partly independent of our source.
- **CoinGecko** (`api.coingecko.com`): peer market caps.
- **Controls for lead-lag:** BTC price (DefiLlama coins) and Solana DEX volume (DefiLlama), in `data/market/placebo_daily.csv`.

## Known limitations

- **Gaps in the source:** the Explorer API itself has no swaps for about 12 hours (1 Oct, 20 Oct, 2 Nov). We disclose this and exclude those days from averages.
- **Users are approximated:** "user" = the swap's refund address. On-chain signer counts cannot see NEAR Intents users, because `intents.near` signs settlements.
- **No agent detection:** there is no published label set for agents on NEAR.
- **Lead-lag has low power:** it uses 44 weeks of DefiLlama all-Intents data, not our 6-week 1Click download. Only correlations above about 0.30 are detectable, so "no lead-lag found" is not proof that none exists.

## Hackathon disclosure

- **When it was built:** all code and analysis in this repo were written during the NEAR Hackathon window (November 2026). There is no pre-hackathon baseline.
- **AI tools:** Claude (Claude Code) helped write the code, run checks and draft text. The author ran the data downloads with their own credentials and reviewed the results.
- **Other project by the same author (rule Q-015):** the author also entered **CommonCircle** (https://github.com/lightokey839-rgb/commoncircle), private lending circles on NEAR. It is a separate, independent project: the two share no code, data or contracts.

## License

[MIT](LICENSE)

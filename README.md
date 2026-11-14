# NEAR Intents Thesis Engine

[![build](https://github.com/lightokey839-rgb/Near-thesis-/actions/workflows/build.yml/badge.svg)](https://github.com/lightokey839-rgb/Near-thesis-/actions/workflows/build.yml)

> **Claim tested:** NEAR is a call option on NEAR Intents. The demand is real and some of it is bought back and held, but not yet enough to outweigh issuance or justify the valuation.
> **Verdict (scorecard, rebuilt on every push):** *working but not yet sufficient*: 0 green, 7 yellow, 0 red on the latest 30 days; the same rules read *bearish* over the whole buyback era.
> **Why:** NEAR keeps about 5 bps of Intents volume (32% of gross fees); its buyback wallet absorbs about 11% of new NEAR; even 100% of today's gross fees would cover 58% of issuance.

**Live dashboard:** https://lightokey839-rgb.github.io/Near-thesis-/ · **Thesis:** [THESIS.md](THESIS.md) · **Every claim as data:** [`data/derived/claims.json`](data/derived/claims.json)

### Verify one number in 2 minutes

Needs Python 3.8+ and nothing else (no packages, keys or internet).

```bash
git clone https://github.com/lightokey839-rgb/Near-thesis-.git near-thesis
cd near-thesis
python verify.py
```

You should see `pinned tables match data/MANIFEST.json (59) PASS`, six lines such as `NEAR's captured take-rate, bps PASS recomputed 5.00232, metrics.json 5.00232`, and `ALL PASS`. `verify.py` recomputes the headline numbers straight from the pinned CSVs with code written separately from the pipeline. The full rebuild is below.

## What this is

An evidence-first investment thesis on NEAR: **is NEAR Intents demand real, and how much of it does the NEAR token capture?** It is built from 818,000 NEAR Intents (1Click) swaps, the NEAR BigQuery public dataset, the NEAR RPC, DefiLlama and CoinGecko. One command rebuilds every number, the thesis text and the dashboard from pinned data tables.

- **Thesis:** [THESIS.md](THESIS.md) opens with a one-page decision memo, then tests the chain **demand → capture → accrual**: is Intents activity real, how much of it does NEAR keep, and does that outweigh issuance? Could AI agents add demand that reaches the token? Agents are measured from NEAR AI Agent Market's own public data, with evidence tiers so bots are never counted as agents. It covers evidence for and against, outside cross-checks, a risk matrix, the strongest case from both sides, a catalyst calendar and what would change my mind.
- **Headline finding, only visible in swap-level data:** [volume is not value](THESIS.md#3b-volume-is-not-value-what-1clicks-swap-level-data-reveals-and-what-it-cannot-establish-about-all-intents-revenue). The app that sends the most 1Click volume pays almost none of NEAR's buyback, and small channels fund most of it.
- **Dashboard:** `dashboard/index.html`, hosted at https://lightokey839-rgb.github.io/Near-thesis-/ (rebuilt and published by [`pages.yml`](.github/workflows/pages.yml) on every push to `main`). It has:
  - **Explain this dashboard:** the verdict in plain English, generated from the data by the build (no AI, no key). Every sentence shows the metric ids behind it, and the same sentences are in `data/derived/claims.json`. A button copies or downloads a short brief for any AI chat.
  - **Ask an AI (optional):** a viewer can paste their *own* Claude (Anthropic) or NEAR AI Cloud API key to ask questions answered only from that brief. The key stays in page memory and goes only to that provider; the page's Content-Security-Policy blocks every other destination. **This repository contains no API key, and the site has no server.**
  - a scorecard, an interactive five-year scenario panel (sliders, presets, reset) and 27 charts, each with its query and one plain sentence.
- **Scenarios:** [`scenarios.json`](scenarios.json) holds the bear, base, bull and stress assumptions. [`pipeline/scenario_model.py`](pipeline/scenario_model.py) runs them and the reverse valuation (THESIS.md section 6b); the dashboard runs the same model in the browser, and a test checks that the two match.
- **Scorecard rules:** [thesis.yaml](thesis.yaml) holds the claim and its numeric tripwires. Each build marks every signal green, yellow or red.
- **Red-team log:** [docs/RED_TEAM_2026-11-11.md](docs/RED_TEAM_2026-11-11.md) records what we checked, what survived and what we corrected.
- **Outside cross-check:** [docs/AUDIT_2026-11-12.md](docs/AUDIT_2026-11-12.md) compares the thesis with the fee docs, NEAR's dashboard figures as reported, HSP-029 coverage and a Blockworks report (THESIS.md section 3e), and lists what stays unresolved.

NEAR Hackathon, track **Investment Thesis** (`thesis`). Not investment advice; no price targets.

## Reproduce everything (no keys, no internet needed for the build)

**Two different things, kept apart:**
- **Reproducible by anyone, from this repository:** every number, THESIS.md and the dashboard, rebuilt from the pinned snapshot tables in `data/` (below). About a minute on GitHub's runners; a few minutes on a laptop (the lead-lag bootstrap is the slow part).
- **Source-data acquisition, not reproducible from the repository alone:** re-downloading the 1.1 GB raw 1Click swap file needs a NEAR Intents Explorer token, and BigQuery needs your own Google Cloud project. The raw file is not published. Its pinned summaries are, and their SHA-256 hashes are checked on every build. See "Re-running from the original sources".

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
- **Generated, not typed:** THESIS.md is generated from `docs/THESIS.template.md`. Every number computed from data is a placeholder like `{wallet_inflow_share_of_issuance|pct0}`, filled from `metrics.json`. A placeholder naming a metric that doesn't exist stops the build. The exceptions are facts quoted from outside sources (governance dates, the exploit, docs and dashboard figures): they are typed, and each has a source and read date in THESIS.md section 12.
- **Checked twice:** `verify.py` recomputes the headline numbers with separate code, and the tests check that every sentence stating a conclusion in words (for example "the take-rate is falling") still matches the data.
- **Traceable:** each metric in `metrics.json` records its source files, its method, and whether it is a FACT (measured) or an INFERENCE (arithmetic or model).
- **Gaps stay visible:** if an input is missing, the metric is listed under `not_computed`; it is never estimated.

## What is where

```
build.py                    one command: verify -> (refresh) -> metrics -> THESIS.md -> dashboard
THESIS.md                   generated thesis (edit docs/THESIS.template.md instead)
thesis.yaml                 the claim and its numeric tripwires (bullish/bearish thresholds per signal)
verify.py                   recomputes the headline numbers from the pinned CSVs with separate code; PASS/FAIL
dashboard/                  build_dashboard.py -> index.html; explain.py -> the plain-English panel and data/derived/claims.json
pipeline/
  download_swaps.py         1Click swap history from the NEAR Intents Explorer API (needs a JWT)
  summarize_swaps.py        raw swaps -> data/summary/*.csv
  audit_swaps.py            red-team checks: integrity, pricing, fee unit, refunds, buyback fees -> data/audit/
  check_gaps.py             asks the API whether gaps in our file are real (needs the JWT)
  bq_run.py                 runs sql/*.sql on BigQuery with a dry run, a per-query cap and a monthly budget -> data/bq/
  buyback_wallet.py         weekly balance of buybacks.multisignature.near from the NEAR archival RPC -> data/onchain/
  fetch_market.py           price, supply, stake, inflation, peers, DefiLlama Intents data -> data/market/
  fetch_crosschain.py       NEAR Intents, THORChain and Chainflip daily volume (DefiLlama) -> data/market/crosschain_peers_daily.csv
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
| Cross-chain venues | `python pipeline/fetch_crosschain.py`, then `python build.py --repin` | internet | free public API (DefiLlama), 3 requests |
| AI Agent Market snapshot | `python pipeline/agent_market.py`, then `python build.py --repin` | internet | free public API (market.near.ai/v1), about 20 requests |
| Supply history and revenue wallets | `python pipeline/chain_history.py`, then `python build.py --repin` | internet | free archival RPC, about 5-10 minutes |
| Swaps | `python pipeline/download_swaps.py`, then `python build.py --refresh swaps` | a NEAR Intents Explorer JWT in `NEAR_INTENTS_JWT` (see `.env.example`) | 1 request per 5 s; ~818 pages for 28 Sep–10 Nov |

After a refresh, `build.py` re-pins the tables (rewrites `data/MANIFEST.json`), so the change shows up in the git diff. Secrets live only in `.env`, which git ignores; scripts never print them.

## Data sources and as-of dates

- **NEAR Intents Explorer API** (`explorer.near-intents.org/api/v0/transactions`): 1Click swaps from 2026-09-28 06:45 to 2026-11-10 12:48 UTC. It covers 1Click only, not all Intents.
- **Google BigQuery** `bigquery-public-data.crypto_near_mainnet_us` (region us-east1): transactions, receipt_actions and account_changes, queried 2026-11-11 for 1 Jan–9 Nov 2026.
- **NEAR JSON-RPC** (fastnear, near.org archival): supply, validators, protocol config and wallet balances, read 2026-11-11.
- **DefiLlama** (`api.llama.fi`, `coins.llama.fi`): Intents volume, fees, revenue and NEAR price, read 2026-11-11; THORChain and Chainflip volume for the comparison in THESIS.md section 2b, read 2026-11-14. Its Intents volume comes from a NEAR-maintained Dune table, so it is only partly independent of our source.
- **CoinGecko** (`api.coingecko.com`): peer market caps.
- **Controls for lead-lag:** BTC price (DefiLlama coins) and Solana DEX volume (DefiLlama), in `data/market/placebo_daily.csv`.

## Known limitations

- **Gaps in the source:** the Explorer API itself has no swaps for about 12 hours (1 Oct, 20 Oct, 2 Nov). We disclose this and exclude those days from averages.
- **Users are approximated:** "user" = the swap's refund address. On-chain signer counts cannot see NEAR Intents users, because `intents.near` signs settlements. The `real_usage` signal counts NEAR L1 signers, not Intents users.
- **Privacy:** `data/summary/top_users.csv` holds pseudonyms (`u_` + 16 hex characters of a salted SHA-256), not refund addresses. This is pseudonymization, not anonymization: the swaps are public on the NEAR Intents Explorer. Earlier commits of this repository contain the raw addresses. Fee-recipient wallets (integrators and the buyback wallet) are kept on purpose, because the fee analysis is about them.
- **No agent detection:** there is no published label set for agents on NEAR.
- **Lead-lag has low power:** it uses 44 weeks of DefiLlama all-Intents data, not our 6-week 1Click download. Only correlations above about 0.30 are detectable, so "no lead-lag found" is not proof that none exists.
- **Scorecard thresholds were set after seeing the data** (11 Nov 2026) and have not been changed since. They are monitoring rules, not pre-registered tests.

## The strongest criticisms of this thesis, answered

1. **"Revenue attribution is incomplete."** Agreed, and shown. About 78% of NEAR's captured revenue has no swap-level record here, and the fee layers do not reconcile: 1Click's app fees are 82% of DefiLlama's gross fees on 28% of the volume. We read DefiLlama's adapter (gross = protocol fee plus every integrator's affiliate fee, from a NEAR-uploaded Dune table), but which swaps that table covers is not public, so the gap is labelled OPEN (THESIS.md section 3c).
2. **"The headline and the scenarios rest on judgement."** Partly. The 5.0 bps headline averages a weekly series that fell from 5.7 to 3.8 bps, and the weekly table is now in section 5b. The 25% base growth, the constant $3.73 price and the custody-release rate are assumptions, labelled as such, and the release rate alone decides whether the bull case's float shrinks: at 100% a year it stops falling (section 6b). The verdict is reported for four windows, including the one that reads bearish.
3. **"There are blind spots."** Yes, listed rather than hidden: Confidential Intents (1Click swaps settle confidentially since 27 Oct; the Explorer still reports them, but private volume elsewhere is unmeasured), an August volume step-up with no identified cause, `real_usage` measuring L1 signers, low lead-lag power, and the 0% on-chain vs 90/10 treasury-cut discrepancy (sections 4, 7, 8).

## Hackathon disclosure

- **When it was built:** all code and analysis in this repo were written during the NEAR Hackathon window (November 2026). There is no pre-hackathon baseline.
- **AI tools:** Claude (Claude Code) helped write the code, run checks and draft text. The author ran the data downloads with their own credentials and reviewed the results. The dashboard's optional "Ask an AI" box calls Claude or NEAR AI Cloud with the viewer's own key; no AI output is part of the thesis or its numbers.
- **Other project by the same author (rule Q-015):** the author also entered **CommonCircle** (https://github.com/lightokey839-rgb/commoncircle), private lending circles on NEAR. It is a separate, independent project: the two share no code, data or contracts.

## License

[MIT](LICENSE)

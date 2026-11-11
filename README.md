# NEAR Intents Thesis Engine

An evidence-first investment thesis on NEAR: **is NEAR Intents demand real, and how much of it does the NEAR token capture?** It is built from 818,000 NEAR Intents (1Click) swaps, the NEAR BigQuery public dataset, the NEAR RPC, DefiLlama and CoinGecko. One command rebuilds every number, the thesis text and the dashboard from pinned data tables.

- **Thesis:** [THESIS.md](THESIS.md) covers the claim, evidence for, evidence against, and what would change my mind.
- **Dashboard:** `dashboard/index.html` has 15 charts. Each shows its query and one plain sentence.
- **Red-team log:** [docs/RED_TEAM_2026-11-11.md](docs/RED_TEAM_2026-11-11.md) records what we checked, what survived and what we corrected.

NEAR Hackathon, track **Investment Thesis** (`thesis`). Not investment advice; no price targets.

## Reproduce in 1 minute (no keys, no internet needed for the build)

Needs Python 3.8+ (tested on 3.15, Windows and Linux). No packages to install.

```bash
git clone <this repo> near-thesis
cd near-thesis
python build.py --test
```

**You should see:**
1. `all 50 pinned tables match data/MANIFEST.json`. The input tables are exactly the ones we analysed (SHA-256).
2. `metrics: 98 computed, 0 sections not computed`, which writes `data/derived/metrics.json`.
3. `THESIS.md written (every number filled from metrics.json)`
4. `dashboard: 15 charts -> dashboard/index.html`
5. The unit tests, ending in `OK`.

Then open `dashboard/index.html` in a browser (it loads Chart.js 4.4.1 from cdnjs). You should see 8 headline tiles and 15 charts. Under each chart, **"Query behind this chart"** shows the exact SQL file or Python function that produced it.

**Why the numbers can't be invented:**
- **Generated, not typed:** THESIS.md is generated from `docs/THESIS.template.md`. Every number in it is a placeholder like `{wallet_inflow_share_of_issuance|pct0}`, filled from `metrics.json`. A placeholder naming a metric that doesn't exist stops the build.
- **Traceable:** each metric in `metrics.json` records its source files, its method, and whether it is a FACT (measured) or an INFERENCE (arithmetic or model).
- **Gaps stay visible:** if an input is missing, the metric is listed under `not_computed`; it is never estimated.

## What is where

```
build.py                    one command: verify -> (refresh) -> metrics -> THESIS.md -> dashboard
THESIS.md                   generated thesis (edit docs/THESIS.template.md instead)
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
| Swaps | `python pipeline/download_swaps.py`, then `python build.py --refresh swaps` | a NEAR Intents Explorer JWT in `NEAR_INTENTS_JWT` (see `.env.example`) | 1 request per 5 s; ~818 pages for 28 Sep–10 Nov |

After a refresh, `build.py` re-pins the tables (rewrites `data/MANIFEST.json`), so the change shows up in the git diff. Secrets live only in `.env`, which git ignores; scripts never print them.

## Data sources and as-of dates

- **NEAR Intents Explorer API** (`explorer.near-intents.org/api/v0/transactions`): 1Click swaps from 2026-09-28 06:45 to 2026-11-10 12:48 UTC. It covers 1Click only, not all Intents.
- **Google BigQuery** `bigquery-public-data.crypto_near_mainnet_us` (region us-east1): transactions, receipt_actions and account_changes, queried 2026-11-11 for 1 Jan–9 Nov 2026.
- **NEAR JSON-RPC** (fastnear, near.org archival): supply, validators, protocol config and wallet balances, read 2026-11-11.
- **DefiLlama** (`api.llama.fi`, `coins.llama.fi`): Intents volume, fees, revenue and NEAR price. Its Intents volume comes from a NEAR-maintained Dune table, so it is only partly independent of our source.
- **CoinGecko** (`api.coingecko.com`): peer market caps.

## Known limitations

- **Gaps in the source:** the Explorer API itself has no swaps for about 12 hours (1 Oct, 20 Oct, 2 Nov). We disclose this and exclude those days from averages.
- **Users are approximated:** "user" = the swap's refund address. On-chain signer counts cannot see NEAR Intents users, because `intents.near` signs settlements.
- **No agent detection:** there is no published label set for agents on NEAR.
- **Lead-lag isn't run yet:** analysis between volume, usage and price needs a longer history than six weeks of swaps.

## Hackathon disclosure

- **When it was built:** all code and analysis in this repo were written during the NEAR Hackathon window (November 2026). There is no pre-hackathon baseline.
- **AI tools:** Claude (Claude Code) helped write the code, run checks and draft text. The author ran the data downloads with their own credentials and reviewed the results.

## License

[MIT](LICENSE)

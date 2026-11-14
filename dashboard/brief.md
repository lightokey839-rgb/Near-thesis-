# NEAR Intents Thesis Engine: brief for reviewers

Claim tested: NEAR is a call option on NEAR Intents: the demand is real and some of it is bought back and held, but not yet enough to outweigh issuance or justify the valuation.

Data as of: swaps to 2026-11-10T12:48:46+00:00; NEAR price 3.73 at 2026-11-11T14:46:34+00:00. Every number below is a metric in data/derived/metrics.json, computed from pinned tables whose SHA-256 is in data/MANIFEST.json.

Labels: FACT = measured from a named source; INFERENCE = arithmetic or a model on measured inputs; OPEN = unresolved. Not investment advice; no price targets.


## Demand
- [FACT] All NEAR Intents swaps averaged $123.8M a day over 2026-10-10 to 2026-11-08, +41% on January. (metrics: intents_volume_usd_per_day=123823455.7, defillama_window="2026-10-10 to 2026-11-08", recent_vs_jan=0.4089)
- [INFERENCE] Over the same 30 days that is 52% of the volume of three native cross-chain swap venues (NEAR Intents, THORChain, Chainflip); in the newest 7 days (2026-11-05 to 2026-11-11) the leader was THORChain. (metrics: crosschain_near_intents_share_of_three=0.5219, crosschain_latest7_window="2026-11-05 to 2026-11-11", crosschain_latest7_leader="THORChain")
- [FACT] Momentum is fading: the last 4 weeks are 0.76x the 4 weeks before, and all of the rise since January is one step in late August ($66.1M to $140.0M a day) whose cause is unidentified. (metrics: intents_volume_4w_vs_prior_4w=0.7577, stepup_before_usd_per_day=66119957.0714, stepup_after_usd_per_day=140045835.1429)

## Capture
- [INFERENCE] NEAR keeps 32% of the gross fees users pay, which is 5.0 of 15.6 basis points of volume (30 days). (metrics: captured_share_of_gross_fees=0.3214, captured_revenue_take_bps=5.0023, intents_gross_fee_bps=15.5627)
- [FACT] That take-rate peaked at 5.7 bps in the week of 2026-09-28 and was 3.8 bps in the latest full week (2026-11-02). (metrics: trend_take_bps_peak_week=5.729, trend_take_bps_peak_week_label="2026-09-28", trend_take_bps_latest_full_week=3.815, trend_latest_full_week="2026-11-02")
- [INFERENCE] Volume is not value: swapkit sends 40% of 1Click volume but funds 1.0% of the buyback; swaps with no referral code are 19% of volume and fund 46%. (metrics: top_volume_channel="swapkit", top_volume_channel_usd_share=0.3968, top_volume_channel_buyback_share=0.0096, no_referral_usd_share=0.1916, no_referral_buyback_share=0.4613)

## Accrual
- [INFERENCE] The buyback wallet takes in about 11% of the NEAR issued each year, and holds it: 0.7% of everything it received has ever left. Holding is custody, not a burn: supply still grew 2.5% last year. (metrics: wallet_inflow_share_of_issuance=0.1097, wallet_outflow_share_of_inflows=0.0068, realised_supply_growth=0.0248)
- [INFERENCE] Even 100% of today's gross fees would cover only 58% of issuance at today's price; break-even needs about 27.1 bps of all Intents volume. (metrics: gross_fees_to_issuance_usd=0.5752, break_even_take_bps=27.058)

## Valuation
- [INFERENCE] NEAR's market cap is 217x its captured Intents revenue, annualised from 30 days. (metrics: market_cap_to_captured_revenue=216.603)

## Usage
- [FACT] Organic NEAR-chain signers changed -58% from January to the latest month. (metrics: organic_change_jan_to_latest=-0.5769)

## AI agents
- [FACT] NEAR AI Agent Market lists 806 live agents with 745 delivered jobs all-time; 0 of the catalogue agents accept NEAR. (metrics: agent_market_live_agents=806, agent_market_delivered_jobs=745, agent_market_agents_payable_in_near=0)

## Verdict
- [INFERENCE] Scorecard verdict: "working but not yet sufficient" (green, yellow, red: 0, 7, 0). Measured over the whole buyback era instead of the latest 30 days, the same rules read "bearish" (THESIS.md section 5b; a test fails if that stops being true). (metrics: scorecard_verdict="working but not yet sufficient", scorecard_counts=[0, 7, 0])

## Open
- [OPEN] 1Click's app fees are 82% of DefiLlama's gross fees on 28% of the volume; the fee layers do not reconcile. (metrics: recon_appfees_share_of_gross=0.8201, recon_oneclick_share_of_volume=0.2818)
- [OPEN] Confidential settlement may hide volume while its fees still reach NEAR's wallets; no adjustment factor exists.
- [OPEN] The cause of the August volume step-up is unidentified.
- [OPEN] The treasury cut reads 0% on-chain against a 90/10 staker/treasury split in HSP-029 coverage.

## Verify it yourself

    git clone https://github.com/lightokey839-rgb/Near-thesis-.git near-thesis && cd near-thesis
    python build.py --check      # every pinned input table matches its SHA-256 in data/MANIFEST.json
    python verify.py             # recomputes the headline numbers from the pinned tables, prints PASS/FAIL
    python build.py --test       # full rebuild of every number, THESIS.md and this page, then the tests

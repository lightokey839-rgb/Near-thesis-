# THESIS: NEAR is a call option on NEAR Intents, and the option is not yet paying for itself

*Every number below is filled in by `python build.py` from `data/derived/metrics.json`, which is computed only from the pinned tables in `data/`. Labels: **FACT** = measured from a named source; **INFERENCE** = derived by arithmetic or modelling; **GUESS** = judgement, marked as such. Nothing here is investment advice, and there is no price target.*

## 1. Claim

NEAR Intents is a **real, steady cross-chain demand source**, and since spring 2026 it has created a **measurable on-chain buy-and-hold flow into NEAR**. But that flow absorbs only about **{wallet_inflow_share_of_issuance|pct0} of the new NEAR issued each year**. Organic activity on the NEAR chain itself **fell {organic_change_jan_to_aug|pctabs} from January to August 2026**. And the token trades at about **{market_cap_to_captured_revenue|x0} its annualised captured Intents revenue**.

So today NEAR is best described as an **option on Intents' volume × take-rate growing faster than issuance** (which HSP-029 is about to cut). It is not yet a token backed by the cash flows it captures. The thesis is **"working but not yet sufficient"**. Section 5 lists the measurements that would change that verdict either way.

## 2. Evidence for (the demand is real, and some of it reaches NEAR)

- **FACT - steady volume.** 1Click swaps averaged **{oneclick_usd_per_day|musd}/day** over {clean_full_days} clean full days ({swaps_first_utc} to {swaps_last_utc}; {swaps_total|int} swaps, {swaps_duplicates} duplicates).
  - All NEAR Intents averaged **{intents_volume_usd_per_day|musd}/day** on DefiLlama ({defillama_window}).
  - 1Click is a stable **{oneclick_share_of_intents_volume_median|pct0}** of that, with daily correlation **{oneclick_vs_intents_daily_corr|r2}**. So our download is a consistent sample of the whole.
- **FACT - the volume is not inflated by bad prices.** {usd_share_priced_within_2pct|pct1} of the dollars are in swaps where USD out is within 2% of USD in. Same-asset transfers are only {same_asset_usd_share|pct1} of the USD.
- **FACT - users.** A median of {oneclick_users_per_day_median|int} distinct refund addresses use 1Click each day, out of {user_proxies_total|int} in the window. An address is a proxy for a person, not a person.
- **FACT - the fee unit is settled.** appFees.fee is in **basis points**. The docs say so, and on stablecoin-to-stablecoin swaps what users actually lost tracks the fee field with slope **{fee_unit_slope|r2}** across {fee_unit_groups} fee groups. The buyback wallet is paid on {buyback_fee_swap_share|pct0} of successful 1Click swaps.
- **FACT - bought-back NEAR is held, not burned or sold.** `buybacks.multisignature.near` grew in **{wallet_weeks_rising} of {wallet_weeks_total} weeks** since inflows began and holds **{wallet_balance_near|int} NEAR** ({wallet_balance_day}).
  - Since 1 Jul, the only days with more than 10 NEAR leaving: **{wallet_outflow_days_over_10_near}**, {wallet_outflow_near_since_jul|int} NEAR in total. It has never staked (max staked {wallet_max_staked_near}).
  - {wallet_inflows_from_intents_share|pct1} of its inbound receipts come from `intents.near`.
  - One inflow was not fee flow: a **{wallet_sep09_treasury_transfer_near|int} NEAR** treasury transfer on 9 Sep (a Trezu DAO proposal).
- **INFERENCE - size of the flow.** In October the wallet took in **{wallet_inflow_near_per_day|int} NEAR/day**, about **{wallet_inflow_share_of_issuance|pct0} of annual issuance today** and **{wallet_inflow_share_of_issuance_hsp029|pct0}** at HSP-029's 1.6% end state.
  - In dollars at {near_price_usd|usd2}: **{wallet_inflow_usd_per_year|musd}/yr**.
  - DefiLlama's broader "captured revenue" (more wallets) is **{near_captured_revenue_usd_per_year|musd}/yr**, ≈ {captured_revenue_take_bps|d1} bps of Intents volume.
  - Our 1Click-only buyback-fee estimate is {oneclick_buyback_fee_usd_per_year|musd}/yr.
- **FACT - the 4-5 Nov refund spike was not lost demand.** {refund_spike_refunded|int} refunds, {refund_spike_intent_submit_failed_share|pct0} of them `INTENT_SUBMIT_FAILED` and {refund_spike_aurora_share|pct0} from Aurora referral codes. Aurora's successful swaps stayed normal ({aurora_success_on_spike_days} on 4 and 5 Nov). The normal refund rate is {refund_rate_normal_median|pct1}.

## 3. Evidence against

- **FACT - organic NEAR-chain usage fell hard this year.** Accounts doing something other than the HOT game or self-transactions went from **{organic_signers_per_day_jan|int}/day in January** to **{organic_signers_per_day_aug|int}/day in August** (-{organic_change_jan_to_aug|pctabs}), and are **{organic_signers_per_day_latest|int}/day** in the latest month.
  - The strictest weekly count (engaged *and* returning) went {strict_weekly_active_jan|int} → {strict_weekly_active_aug|int} → **{strict_weekly_active_latest|int}** per week, peaking in the week of {strict_weekly_active_peak} during the September-October incentive period.
- **FACT - low retention.** A median of {retention_next_week_median|pct1} of a weekly cohort of organic accounts comes back the next week, and {retention_weeks_1_4_median|pct1} within four weeks.
- **FACT - headline activity is inflated by account factories and one game.**
  - **Account factories:** {burst_feb_implicit_self_only|int} accounts in February and {burst_oct_kaiching_self_only|int} kaiching accounts in October each made about one transaction to themselves. The "3 Nov surge" was {burst_nov03_implicit_self_only|int} such accounts; organic unnamed signers were flat ({nov03_organic_hex}).
  - **One game:** HOT game signers were {game_signers_per_day_jan|int}/day in January and {game_signers_per_day_latest|int}/day in the latest month. Mining-claim callers fell steadily over the sample days ({game_claim_callers}).
  - **27 Oct:** {oct27_senders|int} accounts sending {oct27_near_total|int} NEAR (median {oct27_near_median} NEAR) to one address were {oct27_senders_never_active_2026_share|pct0} dormant all year. That address moved {oct27_target_outflow_oct29|int} NEAR out two days later. **INFERENCE:** a custodial dust sweep, not users.
- **FACT - most Intents users are not NEAR-chain users.** Settlement is signed by `intents.near` itself, so on-chain signer counts cannot see Intents users. Intents volume is concentrated:
  - **by app:** the top 5 referral codes carry {top5_referrals_usd_share|pct0} of 1Click USD, and {top_referral} alone {top_referral_usd_share|pct0};
  - **by size:** swaps of $10k+ are {swaps_10k_plus_share_of_swaps|pct1} of swaps but {swaps_10k_plus_share_of_usd|pct0} of USD;
  - **by user:** the top 1,000 addresses carry {top1000_users_usd_share|pct0}.
- **FACT - automation is rising.** The share of 1Click swaps from addresses making 10+ swaps that day went from {heavy_user_share_first_week|pct1} (first week) to {heavy_user_share_last_week|pct1} (last week). We cannot tell agents from bots.
- **INFERENCE - value capture is small next to dilution and valuation.**
  - **Dilution:** issuance is ≈ {issuance_near_per_year|mnear} NEAR/yr ≈ {issuance_usd_per_year|musd}/yr at today's price. Captured revenue covers ≈ {captured_revenue_to_issuance_usd|pct0} of that.
  - **Valuation:** market cap {near_market_cap_usd|busd} ≈ {market_cap_to_captured_revenue|x0} annualised captured revenue.
  - **Holding is not burning:** held NEAR can be sold later.
- **FACT - price has not tracked usage.** NEAR is {near_price_change_ytd|pctsigned} since 1 Jan 2026 (from {near_price_2026_01_01|usd2}) while organic usage fell. Whatever drives the price, this data does not show it is on-chain usage.

## 4. Staking and issuance (context for the option)

**FACT** (RPC, {snapshot_block_time_utc}):

| Measure | Value |
|---|---|
| Total supply | {total_supply_near|int} NEAR |
| Current validator stake | {validator_stake_near|int} NEAR ({staked_share|pct1} of supply) |
| Max inflation | {max_inflation_rate|pct1} |
| Protocol treasury cut | {protocol_reward_rate|pct0} |

**INFERENCE:** the gross staking-yield ceiling is **{staking_yield_ceiling|pct1}** now and **{staking_yield_ceiling_hsp029|pct1}** at 1.6%. HSP-029 passed on 2 Nov 2026 and is not in force yet: a Security Council veto window, then a 90-day grace period and a validator upgrade.

## 5. What would change my mind (scorecard, checked on every build)

Each signal below has a numeric bullish and bearish condition in [`thesis.yaml`](thesis.yaml), set on 11 Nov 2026 from the ranges in this data. `python build.py` looks up today's value and marks it green (bullish condition holds), red (bearish condition holds) or yellow (neither).

<!-- SCORECARD -->

Disclosure for `buyback_outflows`: it uses a rolling 90-day window. The wallet's last outflow was 12,000 NEAR on 10 Jul 2026, about 2.3% of its balance then. That is outside the window, but it is not explained publicly (multisig request, 9-10 Jul).

## 6. HSP-029 sensitivity: what it takes for buybacks to outweigh issuance

**INFERENCE.** These are a sensitivity table, not a forecast.
- **Held constant:** supply, stake and NEAR price stay at today's values, and bought-back NEAR stays held.
- **Activation:** HSP-029 is assumed to lower the inflation ceiling from 2.5% to 1.6% over 24 months once it activates. That is no earlier than mid-February 2027: after the 16 Nov veto window, a 90-day grace period and a validator upgrade. It is shown here as three levels, not a timeline.

<!-- SENSITIVITY -->

**What this says:**
- At today's pace, buybacks soak up about **{wallet_inflow_share_of_issuance|pct0}** of new NEAR.
- To fully offset issuance, the buyback-wallet inflow would have to be **{break_even_volume_x_today_at_current_take|d1}x** today's at 2.5% issuance, or **{break_even_volume_x_today_hsp029_at_current_take|d1}x** at 1.6%.
- The same multiple applies to Intents volume if the wallet's take-rate stays at {wallet_take_bps|d1} bps.
- HSP-029 roughly halves the distance; a higher take-rate closes the rest.

This is why the thesis is an option: it pays off only if **volume x take-rate** grows several-fold while issuance falls.

## 7. Lead-lag: does Intents activity move NEAR's price or usage?

**Method (INFERENCE):**
- **Series:** weekly log changes of all-Intents volume (DefiLlama), NEAR price, organic NEAR signers (BigQuery q10), and two controls: BTC price (the market factor) and Solana DEX volume (a placebo). The sample is {leadlag_weeks} complete weeks (first and last week starting: {leadlag_weekly_first_last}).
- **Tests:** for each lag from -4 to +4 weeks we compute Pearson r with a 95% confidence interval from a moving-block bootstrap. Blocks of 4 weeks keep the autocorrelation, and a fixed seed makes reruns identical.
- **Robustness:** the test is repeated without the September-October incentive weeks, and on daily data (lags of ±7 days).

<!-- LEADLAG -->

**Reading, stated plainly:**
- **Low power.** With {leadlag_weeks} weeks, only |r| above about **{leadlag_weekly_critical_r|r2}** is distinguishable from noise, and real effects smaller than about **{leadlag_weekly_min_detectable_r|r2}** would usually be missed.
- **No lead-lag found.** Of {leadlag_weekly_nonzero_lag_tests} weekly lead/lag tests, **{leadlag_weekly_nonzero_lag_significant}** had a confidence interval excluding 0. Chance alone produces about {leadlag_weekly_expected_false_positives|d1}. So there is **no evidence that Intents volume leads NEAR's price or on-chain usage**, and none for the reverse.
- **Same-week moves.**
  - NEAR price moves with BTC in the same week (r, CI: {leadlag_same_week_btc_to_price}; beta {leadlag_btc_beta|r2}).
  - It also moves with organic NEAR signers (r, CI: {leadlag_same_week_organic_to_price}). This data cannot say which drives which, or whether both follow the wider market.
- **Intents volume and price.**
  - Same-week r, CI: {leadlag_same_week_intents_to_price}; with BTC removed: {leadlag_same_week_intents_to_price_ex_btc}.
  - The placebo, Solana DEX volume, gives {leadlag_same_week_solana_dex_to_price}.

## 8. What we could not measure

- **AI agents on NEAR:** not measurable. There is no published label set, and rising repeat-swapper share cannot be attributed to agents.
- **Intents users on the NEAR chain:** not measurable with BigQuery, because `intents.near` signs settlements.
- **Who runs the 27 Oct wallet, and who sent the 9 Sep treasury transfer:** not found.
- **Cause of the HOT game's summer decline and its 3-4 Nov jump:** not found.
- **A causal link between Intents activity and NEAR's price:** not testable here. Section 7 finds no lead-lag, but with low power. It uses DefiLlama's all-Intents series (from January 2026), because our own 1Click download covers only six weeks.
- **The documented 20 bps minimum for 1Click's fee share vs observed 1-5 bps buyback fees:** unresolved.
- **Why the buyback wallet's 12,000 NEAR left on 10 Jul:** not found.

## 9. Data caveats

- The swap file has gaps in the source API itself: {source_gap_hours|d1} hours, {source_gap_share_of_window|pct1} of the window, on 1 Oct, 20 Oct and 2 Nov. These days are excluded from averages.
- "User" = refund address.
- DefiLlama's Intents volume comes from a Dune table maintained by NEAR, so it is only partly independent of our source.
- Peer multiples use base-layer gas fees, whose methodology differs by chain.
- All dollar figures use prices at fetch time.

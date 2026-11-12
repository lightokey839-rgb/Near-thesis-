# THESIS: NEAR is a call option on NEAR Intents, and the option is not yet paying for itself

*Every number computed from data is filled in by `python build.py` from `data/derived/metrics.json`, which is computed only from the pinned tables in `data/`. Dates and facts quoted from outside sources (governance, incidents) are typed, and each has a source and read date in section 12. Labels: **FACT** = measured from a named source; **INFERENCE** = derived by arithmetic or modelling; **GUESS** = judgement, marked as such. Nothing here is investment advice, and there is no price target.*

## 0. The decision on one page

**The question.** Does NEAR Intents' cross-chain activity become durable value for one NEAR token, once issuance, custody and resale risk are counted? We test the chain **demand → capture → accrual**, and we do not assume that volume equals token value.

| Stage | Question | What the data says | Key numbers |
|---|---|---|---|
| **1. Demand** | Is Intents activity real and lasting? | **Yes, but concentrated.** Higher since September. | All Intents {intents_volume_usd_per_day|musd}/day ({defillama_window}). The top 5 apps send {top5_referrals_usd_share|pct0} of 1Click volume; $10k+ swaps are {swaps_10k_plus_share_of_usd|pct0} of the dollars. |
| **2. Capture** | How much does NEAR keep? | **A thin slice, and it depends on which app sends the swap.** | NEAR keeps {captured_share_of_gross_fees|pct0} of gross fees ({captured_revenue_take_bps|d1} of {intents_gross_fee_bps|d1} bps). The app with the most volume pays {top_volume_channel_buyback_share|pct1} of the buyback. |
| **3. Accrual** | Does it outweigh dilution? | **No, not yet.** It is held in custody, not burned. | The buyback wallet absorbs {wallet_inflow_share_of_issuance|pct0} of new NEAR. Even 100% of today's gross fees would cover only {gross_fees_to_issuance_usd|pct0} of issuance at today's price. Supply actually grew {realised_supply_growth|pct1} last year. The three revenue wallets hold {revenue_wallets_total_near|mnear} NEAR, in custody. |
| **4. Future demand: AI agents** | Could agents add demand that reaches the token? | **Real but small. Today it settles outside NEAR.** | NEAR AI Agent Market: {agent_market_live_agents|int} live agents, {agent_market_delivered_jobs|int} delivered jobs all-time. {agent_market_agents_payable_in_near} catalogue agents accept NEAR (section 3d). |

**Current conclusion: "{scorecard_verdict}".** The scorecard is in section 5.
- **This depends on the window.** Measured over the whole buyback era, the same rules read "bearish" (section 5).
- **Strongest evidence for:** only {wallet_outflow_share_of_inflows|pct1} of everything the buyback wallet received has ever left it, and the take-rate rose from about 1-3 bps early in 2026 to {captured_revenue_take_bps|d1} bps in the latest 30 days.
- **Strongest evidence against:** the arithmetic of section 3c. Break-even needs about {break_even_take_bps|d1} bps of all Intents volume, more than the {intents_gross_fee_bps|d1} bps users pay in total today.
- **What would change our mind:** buyback inflow above 25% of issuance, a take-rate above 8 bps for a quarter, or a full reversal of organic usage back to January levels (bullish). Any sale from the buyback wallet, a take-rate at or below 3 bps, or market cap above 400x captured revenue (bearish). All of these are in `thesis.yaml`.
- **What we do not know:**
  - how much volume now settles through Confidential Intents and so may be missing from public series;
  - who controls the release of held NEAR;
  - whether HSP-029 activates.

**Confidence (GUESS): medium.** The measurements are solid and reproducible. The conclusion's sensitivity to the window is shown, not hidden.

## 1. Claim

NEAR Intents is a **real cross-chain demand source, higher since September**, and since spring 2026 it has created a **measurable on-chain buy-and-hold flow into NEAR**. But that flow absorbs only about **{wallet_inflow_share_of_issuance|pct0} of the new NEAR issued each year**.
- **Organic activity on the NEAR chain itself fell {organic_change_jan_to_latest|pctabs} from January to the latest month** ({organic_change_jan_to_aug|pctabs} peak-to-trough, January to August). {organic_tg_share_of_jan_to_aug_drop|pct0} of that fall is Telegram (`.tg`) wallet accounts.
- **The token trades at about {market_cap_to_captured_revenue|x0} its captured Intents revenue,** annualised from the latest 30 days. That window is near the best of the year; section 5 shows the others.

So today NEAR is best described as an **option on Intents' volume × take-rate growing faster than issuance**. HSP-029 would cut issuance, if it clears its remaining steps (section 4). It is not yet a token backed by the cash flows it captures. Section 5 lists the measurements that would change the verdict either way.

## 2. Evidence for (the demand is real, and some of it reaches NEAR)

- **FACT - large, higher-since-September volume.** 1Click swaps averaged **{oneclick_usd_per_day|musd}/day** over {clean_full_days} clean full days ({swaps_first_utc} to {swaps_last_utc}; {swaps_total|int} swaps, {swaps_duplicates} duplicates).
  - All NEAR Intents averaged **{intents_volume_usd_per_day|musd}/day** on DefiLlama ({defillama_window}).
  - Momentum depends on the window: the last 4 weeks are {intents_volume_4w_vs_prior_12w|r2}x the 12 weeks before, {intents_volume_8w_vs_prior_8w|r2}x for 8 weeks vs 8, and {intents_volume_4w_vs_prior_4w|r2}x for 4 vs 4.
  - 1Click is a median **{oneclick_share_of_intents_volume_median|pct0}** of that, with daily correlation **{oneclick_vs_intents_daily_corr|r2}**.
  - **INFERENCE:** this is consistent with 1Click being a stable slice of the whole. Both series come from NEAR-run sources (the Explorer API, and a NEAR-maintained Dune table behind DefiLlama), so this is only a partly independent check.
- **FACT - the volume is not inflated by bad prices.** {usd_share_priced_within_2pct|pct1} of the dollars are in swaps where USD out is within 2% of USD in. Same-asset transfers are only {same_asset_usd_share|pct1} of the USD.
- **FACT - users.** A median of {oneclick_users_per_day_median|int} distinct refund addresses use 1Click each day, out of {user_proxies_total|int} in the window. An address is a proxy for a person, not a person.
- **FACT - the fee unit is settled.** appFees.fee is in **basis points**. The docs say so, and on stablecoin-to-stablecoin swaps what users actually lost tracks the fee field with slope **{fee_unit_slope|r2}** across {fee_unit_groups} fee groups. The buyback wallet is paid on {buyback_fee_swap_share|pct0} of successful 1Click swaps.
- **FACT - bought-back NEAR is held in custody, not burned.** `buybacks.multisignature.near` grew in **{wallet_weeks_rising} of {wallet_weeks_total} weekly samples** since inflows began and holds **{wallet_balance_near|int} NEAR** ({wallet_balance_day}).
  - **Custody is not a lock.** It is a multisig, and its signers can move the NEAR. "Held" means "has not been moved so far", not "removed from supply".
  - Daily data starts 1 Jul. Since then, the only day with more than 10 NEAR leaving was **{wallet_outflow_days_over_10_near}**, {wallet_outflow_near_since_jul|int} NEAR in total ({wallet_outflow_share_of_inflows|pct1} of all NEAR received; its destination is not identified). Before July there are only weekly samples. It has never staked (max staked {wallet_max_staked_near}).
  - {wallet_inflows_from_intents_share|pct1} of its inbound receipts come from `intents.near`.
  - One inflow was not *new* fee flow: a **{wallet_sep09_treasury_transfer_near|int} NEAR** treasury transfer on 9 Sep, made through a Trezu DAO proposal.
  - **INFERENCE (high confidence):** this was the 1Click fund (`1csfundsadmin.sputnik-dao.near`) emptying into the buyback wallet. The fund peaked at {onecs_peak_near|int} NEAR ({onecs_peak_week}) and fell by {onecs_largest_fall_near|int} NEAR in the week sampled on {onecs_largest_fall_week}, matching the transfer to within {onecs_fall_vs_sep09_transfer|pct2}.
  - That also explains where captured revenue went in February-April, when the buyback wallet held almost nothing: it was parked in the 1Click fund, then moved into the buyback wallet. DefiLlama treats such hops between its revenue wallets as internal.
- **INFERENCE - size of the flow.** From 6 Oct to 8 Nov the wallet took in a mean of **{wallet_inflow_near_per_day|int} NEAR/day**. That is about **{wallet_inflow_share_of_issuance|pct0} of annual issuance today**, and **{wallet_inflow_share_of_issuance_hsp029|pct0}** at HSP-029's 1.6% end state. In dollars, section 3c values it at each day's price, so it can be compared with DefiLlama.
- **INFERENCE - the 4-5 Nov refund spike was not lost demand.**
  - FACT: {refund_spike_refunded|int} refunds, {refund_spike_intent_submit_failed_share|pct0} of them `INTENT_SUBMIT_FAILED` and {refund_spike_aurora_share|pct0} from Aurora referral codes.
  - FACT: Aurora's successful swaps stayed normal ({aurora_success_on_spike_days} on 4 and 5 Nov). The normal refund rate is {refund_rate_normal_median|pct1}.
  - The reading that these were extra retries is an inference.

## 3. Evidence against

- **FACT - organic NEAR-chain usage fell this year, mostly in Telegram wallets.** Accounts doing something other than the HOT game or self-transactions went from **{organic_signers_per_day_jan|int}/day in January** to **{organic_signers_per_day_latest|int}/day** in the latest month ({organic_change_jan_to_latest|pctsigned}).
  - **Peak and trough:** January was the busiest complete month ({organic_peak_month}) and August the quietest ({organic_trough_month}), so January to August ({organic_change_jan_to_aug|pctsigned}) is peak-to-trough.
  - **By account family:** Telegram (`.tg`) wallet accounts were {organic_tg_share_jan|pct0} of January's organic signers and {organic_tg_share_of_jan_to_aug_drop|pct0} of the January-to-August fall. Excluding them, organic signers changed {organic_ex_tg_change_jan_to_latest|pctsigned} from January to the latest month; named `.near` accounts changed {organic_dot_near_change_jan_to_latest|pctsigned}.

<!-- FAMILIES -->

  - The strictest weekly count (engaged *and* returning) went {strict_weekly_active_jan|int} → {strict_weekly_active_aug|int} → **{strict_weekly_active_latest|int}** per week, peaking in the week of {strict_weekly_active_peak} during the September-October incentive period. The January value is understated: "returning" needs four earlier weeks, and the data starts on 1 Jan.
- **FACT - low retention of new accounts.** A median of {retention_next_week_median|pct1} of a weekly cohort of *newly seen* organic accounts (Feb-Aug cohorts) comes back the next week, and {retention_weeks_1_4_median|pct1} within four weeks.
- **FACT - headline activity is inflated by one-transaction account bursts and one game.**
  - **Account bursts (INFERENCE: account factories):** {burst_feb_implicit_self_only|int} accounts in February and {burst_oct_kaiching_self_only|int} kaiching accounts in October each made about one transaction to themselves. The "3 Nov surge" was {burst_nov03_implicit_self_only|int} such accounts; organic unnamed signers were flat ({nov03_organic_hex}).
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
- **INFERENCE - price and usage: levels diverged, weekly moves did not.**
  - FACT: NEAR is {near_price_change_ytd|pctsigned} since 1 Jan 2026 (from {near_price_2026_01_01|usd2}) while organic usage fell over the year.
  - Week to week, NEAR's price and organic signers move together (same-week r {leadlag_same_week_organic_to_price}), and both peaked in September-October.
  - This data cannot say which drives which, or whether both follow the incentive period and the wider market (section 7).

## 3b. Volume is not value: who actually pays for NEAR's buyback

Every 1Click swap records the app that sent it (its referral code) and the fee it paid to `buybacks.multisignature.near`. Adding these up by app shows that **the volume and the buyback come from different places**. The data covers {channels_total} referral codes; {channels_paying_buyback} of them paid at least one cent in buyback fees over the six weeks.

- **The biggest source of volume pays almost nothing to NEAR.**
  - `{top_volume_channel}` sends **{top_volume_channel_usd_share|pct0} of 1Click volume** but only **{top_volume_channel_buyback_share|pct1} of the buyback fees**.
  - That is {top_volume_channel_buyback_bps|d1} bps on its volume, against {rest_buyback_bps|d1} bps for all other apps together.
  - Week by week its volume share ranged from {top_volume_channel_weekly_usd_share_min|pct0} to {top_volume_channel_weekly_usd_share_max|pct0}; its share of the buyback never went above {top_volume_channel_weekly_buyback_share_max|pct1}.
- **Small channels fund most of it.**
  - Swaps with no referral code are {no_referral_usd_share|pct0} of volume but **{no_referral_buyback_share|pct0} of the buyback**.
  - The 5 apps that pay the most fund {buyback_top5_channels_share|pct0} of the buyback while carrying {buyback_top5_channels_usd_share|pct0} of the volume.
  - {usd_share_paying_no_buyback|pct0} of volume comes from apps that paid less than one cent in buyback fees over the whole six weeks.
- **On average,** every $1M swapped through 1Click paid about ${oneclick_buyback_usd_per_million|int} into the buyback ({oneclick_buyback_bps|d1} bps).

<!-- CHANNELS -->

**INFERENCE - what this means for the option.** Section 1 calls NEAR an option on Intents volume × take-rate. This section shows the take-rate is not one number: it depends on *which apps* grow.
- Growth through a large aggregator paying {top_volume_channel_buyback_bps|d1} bps barely moves the buyback.
- Growth through wallets and direct users moves it many times faster per dollar.
- So "Intents volume is up" is weak evidence for NEAR holders on its own. The question to ask is *whose* volume grew.
- **A hypothetical, not a forecast:** if `{top_volume_channel}` paid the same average rate as everyone else, 1Click buyback fees would be about **{buyback_uplift_if_top_channel_paid_rest_rate|pct0} higher**. This is the bull case's lever: one fee arrangement moves NEAR's take a lot. It is equally the bear case's risk: the buyback rests on a few small channels.

**Caveats.**
- 1Click only, which is about {oneclick_share_of_intents_volume_median|pct0} of all Intents volume.
- Buyback fees = fee in basis points (settled in section 2) × the swap's USD value at swap time.
- A referral code is an app or integration, not a user.
- DefiLlama's captured revenue also counts other revenue wallets, so this is the 1Click part of the buyback, not all of NEAR's capture.

## 3c. Following the money: from fees to tokens, and the ceiling

**Three numbers that are often mixed up, on the same days.** All three are measured over {bridge_window} and annualised. They are different things, so we show them side by side rather than picking one.

| Layer | What it measures | USD / year |
|---|---|---|
| (a) 1Click buyback fees | fee to the buyback wallet (bps) × swap value, our 1Click download only | {bridge_oneclick_usd_per_year|musd} |
| (b) Buyback-wallet inflow | NEAR arriving in `buybacks.multisignature.near` each day × that day's NEAR price, all Intents channels | {bridge_wallet_usd_per_year|musd} |
| (c) DefiLlama captured revenue | NEAR swept into **three** NEAR wallets: the buyback wallet, `fefundsadmin.sputnik-dao.near` (front-end fund) and `1csfundsadmin.sputnik-dao.near` (1Click fund) | {bridge_defillama_usd_per_year|musd} |

- **(b) is {bridge_wallet_share_of_defillama|pct0} of (c)**, and the ratio is stable month to month (table below). The other {bridge_other_wallets_usd_per_year|musd}/yr is revenue DefiLlama assigns to its two other wallets, plus any measurement difference. Our "held, not sold" checks cover the buyback wallet only.
<!-- BRIDGE_MONTHLY -->

- **(a) is {bridge_oneclick_share_of_wallet|pct0} of (b),** roughly in line with 1Click's {oneclick_share_of_intents_volume_median|pct0} share of volume.
- Counting only the buyback wallet's inflow, NEAR trades at **{market_cap_to_wallet_inflow|x0}** instead of {market_cap_to_captured_revenue|x0}.

**The take-rate has a ceiling.**
- Users paid {intents_gross_fee_bps|d1} bps of volume in gross fees over the latest 30 days. NEAR kept {captured_share_of_gross_fees|pct0} of that ({captured_revenue_take_bps|d1} bps); the rest went to integrators and solvers.
- **If NEAR captured 100% of today's gross fees**, that would cover {gross_fees_to_issuance_usd|pct0} of issuance at 2.5%, or {gross_fees_to_issuance_usd_hsp029|pct0} at HSP-029's 1.6%, at today's price.
- Break-even needs a take-rate of about **{break_even_take_bps|d1} bps** of all Intents volume at 2.5% issuance, or {break_even_take_bps_hsp029|d1} bps at 1.6%. Both are above what users pay in total today.
- **INFERENCE:** closing the gap therefore needs more volume, higher fees, or lower issuance, not just a bigger share of today's fees.

**All three revenue wallets, read from the chain** (weekly samples, {supply_history_window}):

<!-- REVENUE_WALLETS -->

- Together they hold **{revenue_wallets_total_near|mnear} NEAR ({revenue_wallets_share_of_supply|pct2} of supply)**.
- The front-end fund `fefundsadmin.sputnik-dao.near` holds {fefunds_balance_near|mnear} NEAR. It has accumulated since before the buyback program began; weeks in which its balance fell by more than 1 NEAR: {fefunds_weeks_falling}.
- It is a Sputnik DAO treasury, so its members can vote to move funds. Its release rules are not published.

**Custody is not burn.** In this thesis:
- only tokens with on-chain burn evidence count as removed from supply;
- NEAR bought back and held in a multisig or DAO wallet is *custody*: it is out of the float only while it stays there.

## 3d. The agent economy, measured: could AI agents become NEAR's next demand?

This hackathon is built around AI agents, so the thesis has to ask whether agents are, or could become, a source of demand that reaches the NEAR token.

**We count an account as an "AI agent" only on identified evidence.** An address that transacts a lot could be a bot, a market maker, a script or a power user.
- **Tier 1:** the operator's own registry.
- **Tier 3:** automation proxies. These are *not* counted as agents.
- **Tier 4:** names chosen by the app itself, which prove nothing.

**Tier 1 - NEAR AI Agent Market, the operator's own public data** (snapshot {agent_market_fetched_utc}):
- **Platform totals:** {agent_market_live_agents|int} live agents, {agent_market_jobs_total|int} jobs posted all-time, {agent_market_delivered_jobs|int} delivered, {agent_market_jobs_this_week|int} this week.
- **Who does the work:** of the {agent_market_catalogue_agents|int} agents in the public catalogue, only **{agent_market_agents_with_a_delivered_job|int} ({agent_market_agents_with_a_delivered_job_share|pct0}) have ever delivered a job**. The 10 busiest did {agent_market_top10_share_of_delivered|pct0} of all delivered jobs.
- **When they arrived:** {agent_market_listed_since_oct_share|pct0} of catalogue agents were listed on or after 1 Oct 2026, the run-up to this hackathon. Listings are not usage.

<!-- AGENTS -->

- **How agents are paid (FACT, from the marketplace's own docs; see section 12):**
  - Jobs are priced in **USD (card, via Stripe) or USDC**. Balances are held by a third-party wallet provider.
  - Buyers pay no gas when a payment is held or released.
  - The marketplace keeps a 5% fee.
  - In the catalogue, **{agent_market_agents_payable_in_near} agents accept NEAR**: {agent_market_agents_usdc_only|int} take USDC only, and {agent_market_agents_usd_and_usdc|int} take USD or USDC.

**Tier 4 - 1Click swaps from apps whose names mention agents or bots:** {oneclick_agent_named_codes}. Together they made {oneclick_agent_named_swaps|int} swaps worth ${oneclick_agent_named_usd|int}, or {oneclick_agent_named_usd_share|pct2} of 1Click volume. Agents may also use 1Click without a referral code or under a generic one, so this is a floor, not a count.

**Tier 3 - automation, not agents:** the share of 1Click swaps from addresses making 10+ swaps a day rose from {heavy_user_share_first_week|pct1} to {heavy_user_share_last_week|pct1} (section 3). We cannot tell agents from bots, so none of this is counted as agent activity.

**INFERENCE - what this means for the token.**
- **Today:** NEAR's flagship agent marketplace is real and growing, but small. Its commerce settles in dollars and USDC, not in NEAR.
- **So agent demand reaches a NEAR holder only indirectly:** if agent payments are routed through NEAR Intents (for example USDC moved via Intents), they pay the same fees as any other swap, and part of those fees funds the buyback. Whether that already happens at scale is **not measured**: job values and routes are not public.
- **The size it would need to matter (a hypothetical, not a forecast):** to add captured revenue worth 10% of today's issuance at today's take-rate, agents would have to route about **{agent_volume_for_10pct_of_issuance_usd_per_day|musd} of payments per day** through Intents. That is a large share of all Intents volume today ({intents_volume_usd_per_day|musd}/day).
- **Bull case:** agents become the users that the "which apps pay" finding of section 3b rewards, routing through high-fee direct channels.
- **Bear case:** agent commerce grows in USDC on rails where NEAR is optional.
- **What would change our mind:** Agent Market or another agent platform settling in NEAR or through Intents with published volumes, or agent-labelled channels showing up in the fee data.

## 4. Staking, issuance and the catalyst calendar

**FACT** (RPC, {snapshot_block_time_utc}):

| Measure | Value |
|---|---|
| Total supply | {total_supply_near|int} NEAR |
| Current validator stake | {validator_stake_near|int} NEAR ({staked_share|pct1} of supply) |
| Max inflation | {max_inflation_rate|pct1} |
| Protocol treasury cut | {protocol_reward_rate|pct0} |

**INFERENCE:** the gross staking-yield ceiling is **{staking_yield_ceiling|pct1}** now and **{staking_yield_ceiling_hsp029|pct1}** at 1.6%.
- Issuance goes to stakers. So a holder who stakes roughly keeps their share of supply, while one who does not is diluted by about the inflation rate each year.
- The protocol treasury cut above is read from the RPC. Some press coverage of HSP-029 describes a 90/10 staker/treasury split; the on-chain parameter we read is the treasury cut shown here.
- Issuance in this thesis is the protocol's **maximum** (supply × inflation ceiling), which assumes full validator uptime.

**FACT - what actually happened to supply** (block-header `total_supply`, weekly samples, {supply_history_window}):
- Supply grew **{realised_supply_growth|pct2} a year**, or {realised_new_near_per_year|mnear} NEAR, net of everything burned. That is {realised_vs_ceiling_issuance|r2}x the maximum. So the 2.5% ceiling is, in practice, what holders are diluted by.
- **Burning is on, but small.** The live parameter `burnt_gas_reward` = {burnt_gas_reward} (read {protocol_config_read_utc}), so all gas fees are burned since HSP-027. Supply still grew at almost the full ceiling, so base-layer gas burn does little against issuance at today's usage.
- **Custody absorbed part of it.** Over the same days, the three revenue wallets together added NEAR equal to **{custody_share_of_realised_new_supply|pct0} of the net new supply**. Moves between the three wallets, like the 9 Sep transfer, cancel out in this total. That NEAR is out of the float only while it stays there.

**Catalyst calendar** (dates from the sources in section 12; statuses as read on 12 Nov 2026):

| Date | Event | Status | Why it matters here |
|---|---|---|---|
| 23 Feb 2026 | Captured Intents revenue starts funding NEAR buybacks (DefiLlama methodology) | in force | Start of the "since buybacks began" window in section 5 |
| 7 Jul 2026 | Confidential Intents generally available | in force | Swaps routed privately may be missing from public volume series (section 8) |
| Jun-Jul 2026 | HSP-027: the 30% developer gas rebate goes to 0%, so all gas is burned | **in force** (`burnt_gas_reward` = {burnt_gas_reward} on mainnet, read {protocol_config_read_utc}) | The only verified *burn* channel. It is small next to issuance (section 4). |
| 1 Oct 2026 | NEAR Intents exploit (~$3.8M, Omni deposit/withdraw bug); services paused, funds returned in full | resolved | Explains the 1 Oct hole in our swap data (section 9); a security risk (section 10) |
| 2 Nov 2026 | HSP-029 approved by House of Stake: inflation ceiling 2.5% → 1.6% over 24 months | approved, **not in force** | Section 6 |
| to 16 Nov 2026 | HSP-029 Security Council veto window | open | First of three remaining steps |
| + ~90 days | HSP-029 grace period, then a validator upgrade | pending | Earliest effect around mid-February 2027 (INFERENCE) |

## 5. What would change my mind (scorecard, checked on every build)

Each signal below has a numeric bullish and bearish condition in [`thesis.yaml`](thesis.yaml), set on 11 Nov 2026 after looking at this data (so they are not pre-registered; one signal was changed on 12 Nov, see below). `python build.py` looks up today's value and marks it green (bullish condition holds), red (bearish condition holds) or yellow (neither).

<!-- SCORECARD -->

**Correction to `buyback_outflows` (12 Nov 2026).**
- **What changed:** the first version measured the largest outflow in a rolling 90-day window. That window left out the wallet's only outflow (12,000 NEAR on 10 Jul 2026, about 2.3% of its balance then), so the signal scored green. Over the full daily record the same measure is red, and the scorecard verdict would have read "bearish". A verdict that one window choice can flip is not evidence.
- **Now:** the signal is all NEAR that ever left the wallet divided by all NEAR that came in, over every day of daily data. There is no window to choose. It is **{wallet_outflow_share_of_inflows|pct2}**, or **{wallet_outflow_share_of_inflows_ex_sep09|pct2}** without the 9 Sep treasury transfer. Both are under the 1% bearish line, so the signal is yellow, not green.
- **Still open:** the 10 Jul move is not explained publicly (multisig request, 9-10 Jul). The full log is in [docs/RED_TEAM_2026-11-11.md](docs/RED_TEAM_2026-11-11.md) section 6.

### 5b. Does the verdict survive other windows?

Three signals depend on how revenue is averaged: `take_rate`, `revenue_vs_dilution` and `valuation`. We re-score the whole scorecard with those three measured over different windows, all ending on the same day, with the same thresholds.

<!-- WINDOWS -->

**Reading, stated plainly.**
- Over the last 30, 90 and 180 days the verdict stays "working but not yet sufficient".
- Measured over the **whole buyback era** (since 23 Feb), revenue was lower. Valuation and revenue-vs-dilution both turn red, and the same rules read **bearish**.
- The difference is the September step-up in volume and take-rate. If it holds, the recent windows describe NEAR today. If it fades, the long window does.
- We report both, and do not pick the convenient one.

## 6. HSP-029 sensitivity: what it takes for buybacks to outweigh issuance

**INFERENCE.** These are a sensitivity table, not a forecast.
- **Held constant:** supply, stake and NEAR price stay at today's values, and bought-back NEAR stays held.
- **Activation:** HSP-029 is assumed to lower the inflation ceiling from 2.5% to 1.6% over 24 months once it activates. That is no earlier than mid-February 2027: after the 16 Nov veto window, a 90-day grace period and a validator upgrade. It is shown here as three levels, not a timeline.

<!-- SENSITIVITY -->

**What this says:**
- At today's pace, buybacks soak up about **{wallet_inflow_share_of_issuance|pct0}** of new NEAR.
- To fully offset issuance, the buyback-wallet inflow would have to be **{break_even_volume_x_today_at_current_take|d1}x** today's at 2.5% issuance, or **{break_even_volume_x_today_hsp029_at_current_take|d1}x** at 1.6%.
- The same multiple applies to Intents volume if the wallet's take-rate stays at {wallet_take_bps|d1} bps.
- HSP-029 cuts the required multiple by about a third ({break_even_volume_x_today_at_current_take|d1}x → {break_even_volume_x_today_hsp029_at_current_take|d1}x). A higher take-rate or much more volume has to close the rest, and the take-rate is capped by gross fees (section 3c).

This is why the thesis is an option: it pays off only if **volume x take-rate** grows several-fold while issuance falls.

## 7. Lead-lag: does Intents activity move NEAR's price or usage?

**Method (INFERENCE):**
- **Series:** weekly log changes of all-Intents volume (DefiLlama), NEAR price, organic NEAR signers (BigQuery q10), and two controls: BTC price (the market factor) and Solana DEX volume (a placebo). The sample is {leadlag_weeks} complete weeks (first and last week starting: {leadlag_weekly_first_last}).
- **Tests:** for each lag from -4 to +4 weeks we compute Pearson r with a 95% confidence interval from a moving-block bootstrap. Blocks of 4 weeks keep the autocorrelation, and a fixed seed makes reruns identical.
- **Robustness:** the test is repeated without the September-October incentive weeks, and on daily data (lags of ±7 days).

<!-- LEADLAG -->

**Reading, stated plainly:**
- **Low power.** With {leadlag_weeks} weeks, only |r| above about **{leadlag_weekly_critical_r|r2}** is distinguishable from noise, and real effects smaller than about **{leadlag_weekly_min_detectable_r|r2}** would usually be missed.
- **No evidence that Intents volume leads NEAR's price or on-chain usage.**
  - Of the {leadlag_intents_tests} weekly lead/lag tests where Intents volume is the first series, **{leadlag_intents_significant}** had a confidence interval excluding 0.
  - Across all {leadlag_weekly_nonzero_lag_tests} weekly lead/lag tests (including the placebo and BTC), {leadlag_weekly_nonzero_lag_significant} did, against about {leadlag_weekly_expected_false_positives|d1} expected by chance. Adjacent lags are not independent, so that is a rough guide only.
  - The hits that did appear are not about Intents. Organic signers this week vs price next week gives r {leadlag_organic_to_price_lag1|r2}, which is plausibly the weekly-averaging echo of the same-week link below.
- **Same-week moves.**
  - NEAR price moves with BTC in the same week (r, CI: {leadlag_same_week_btc_to_price}; beta {leadlag_btc_beta|r2}).
  - It also moves with organic NEAR signers (r, CI: {leadlag_same_week_organic_to_price}). This data cannot say which drives which, or whether both follow the wider market.
- **Intents volume and price.**
  - Same-week r, CI: {leadlag_same_week_intents_to_price}; with BTC removed: {leadlag_same_week_intents_to_price_ex_btc}.
  - The placebo, Solana DEX volume, gives {leadlag_same_week_solana_dex_to_price}.

## 8. What we could not measure

- **AI agents on NEAR:** not measurable. There is no published label set, and rising repeat-swapper share cannot be attributed to agents.
- **Intents users on the NEAR chain:** not measurable with BigQuery, because `intents.near` signs settlements.
- **Who runs the 27 Oct wallet:** not found. The 9 Sep transfer is very likely from the 1Click fund (section 2), but the Trezu proposal's signer set is not checked.
- **Cause of the HOT game's summer decline and its 3-4 Nov jump:** not found.
- **A causal link between Intents activity and NEAR's price:** not testable here. Section 7 finds no lead-lag, but with low power. It uses DefiLlama's all-Intents series (from January 2026), because our own 1Click download covers only six weeks.
- **The documented 20 bps minimum for 1Click's fee share vs observed 1-5 bps buyback fees:** unresolved.
- **Why the buyback wallet's 12,000 NEAR left on 10 Jul:** not found.
- **Confidential Intents volume:** not measured.
  - Since 7 Jul 2026, swaps can settle privately. Press reports put that at a large share of near.com's volume (section 12); not verified here.
  - Our 1Click download and DefiLlama's series may miss part of it, while its fees may still reach NEAR's revenue wallets. If so, measured take-rates would be biased upward. The direction and size are **unknown**.
- **What the other two revenue wallets will do with their NEAR:** `fefundsadmin.sputnik-dao.near` and `1csfundsadmin.sputnik-dao.near` are DAO treasuries. Weekly balances are in section 3c; daily flows and release rules are not measured.
- **Market share against other cross-chain routes** (Across, Relay, LayerZero/Stargate, deBridge, THORChain, Wormhole): not measured. Their methodologies differ from Intents', so we do not state a share.

## 9. Data caveats

- **Gaps:** the swap file has gaps in the source API itself: {source_gap_hours|d1} hours, {source_gap_share_of_window|pct1} of the window, on 1 Oct, 20 Oct and 2 Nov. These days are excluded from averages.
  - The 1 Oct hole (08:34-12:16 UTC) coincides with the service pause after the NEAR Intents exploit that day (section 4), so it is most likely a real pause, not missing data.
  - An early estimate in the red-team log (about 14.4 h) came before the gaps were re-checked with the API.
- "User" = refund address, a proxy: one person can control many addresses, and one address can be a service.
- DefiLlama's Intents volume comes from a Dune table maintained by NEAR, so it is only partly independent of our source.
- Peer multiples use base-layer gas fees, whose methodology differs by chain.
- **Prices:**
  - Valuation and issuance in USD use the NEAR price at fetch time ({near_price_usd|usd2}).
  - The bridge in section 3c values each day's buyback inflow at that day's price.
  - The year-to-date change uses DefiLlama's daily close.

## 10. Risk matrix

| Risk | Evidence in this repo | What would make it worse | Direction for the thesis |
|---|---|---|---|
| **Value capture is policy, not protocol** | NEAR keeps {captured_share_of_gross_fees|pct0} of gross fees; the buyback wallet's fee varies by app (section 3b) | Fee splits renegotiated down; large apps routing around fees | Bearish |
| **Concentration** | Top 5 apps {top5_referrals_usd_share|pct0} of 1Click volume; {top_volume_channel} alone {top_volume_channel_usd_share|pct0}, paying {top_volume_channel_buyback_bps|d1} bps | One integrator leaving | Bearish for volume; small effect on the buyback (section 3b) |
| **Custody and release** | {revenue_wallets_total_near|mnear} NEAR across a multisig and two DAO treasuries; one unexplained outflow from the buyback wallet on 10 Jul | Any sale or transfer from the revenue wallets | Bearish (would turn the `buyback_outflows` signal red) |
| **Security** | The 1 Oct exploit (~$3.8M, funds returned, section 4) | A repeat without recovery | Bearish |
| **Measurement blind spots** | Confidential Intents; refund-address proxy; 1Click-only microdata (sections 8-9) | Private settlement growing | Unknown |
| **Incentive-driven demand** | Volume, take-rate, organic usage and price all peaked in Sep-Oct (sections 3, 5b) | Activity falling back to pre-September levels | Bearish |
| **Governance** | HSP-029 approved but not in force (section 4) | Veto, delay or non-adoption by validators | Bearish (keeps 2.5% issuance) |
| **Competition** | Not measured (section 8) | Share loss to other cross-chain routes | Bearish |

## 11. Methodology appendix: every hand-picked choice

So that anyone can attack them, these are all the windows and thresholds we chose by hand. All were chosen on 11-12 Nov 2026, after seeing the data.
- **Days excluded from 1Click averages:** 28 Sep and 10 Nov (partial), and 1 Oct, 20 Oct, 2 Nov (source gaps).
- **DefiLlama window:** 30 days ending 2 days before the newest row ({defillama_window}). Section 5b shows 90 days, 180 days and since 23 Feb.
- **Buyback inflow pace:** 6 Oct-8 Nov mean.
- **Outflow signal:** the whole daily record (1 Jul-9 Nov); days with more than 10 NEAR leaving are listed separately.
- **Usage baselines:** January vs August vs the latest month (section 3 shows the whole monthly series by family). L4 baselines use January's and August's full weeks. Retention uses the Feb-Aug cohorts.
- **Incentive weeks** (lead-lag robustness): 14 Sep-19 Oct.
- **Lead-lag:** weekly means, lags -4..+4. Moving-block bootstrap with blocks of 4 weeks and 2,000 draws (daily: blocks of 14 days, 400 draws), seed 20261111.
- **Momentum:** 4 weeks vs the 12 before (8 vs 8 and 4 vs 4 are shown in section 2).
- **HSP-029 end state:** 1.6% (from the approved proposal).
- **Scorecard thresholds:** `thesis.yaml`, set after seeing the data. These are monitoring thresholds, not pre-registered tests.

## 12. Sources for typed facts (all read 11-12 Nov 2026)

- DefiLlama NEAR Intents fee adapter: the three revenue wallets, and buybacks from 23 Feb 2026. https://github.com/DefiLlama/dimension-adapters/blob/master/fees/near-intents/index.ts
- NEAR JSON-RPC `EXPERIMENTAL_protocol_config` (`max_inflation_rate`, `protocol_reward_rate`, `burnt_gas_reward`) and block-header `total_supply`: public archival RPC, pinned in `data/onchain/` by `pipeline/chain_history.py`.
- 1Click fee configuration (fee in basis points): https://docs.near-intents.org/integration/distribution-channels/1click-api/fee-config
- HSP-029 approval, 24-month schedule, grace period and validator upgrade: https://www.theblock.co/news/defi/2026-11-03-near-governance-approves-token-issuance-432378 ; veto window to 16 Nov: https://www.altcoinbuzz.io/near-issuance-cut-to-1-6-passes-vote-staking-yield-set-to-fall
- HSP-027 (developer gas rebate removed, all gas burned): https://cryptobriefing.com/near-protocol-governance-eliminates-developer-gas-rebate/
- 1 Oct exploit, pause and return of funds: https://www.theblock.co/news/ecosystems/2026-10-01-near-intents-halts-services-after-3-8-million-exploit-promises-full-compensation-417404 ; https://cointelegraph.com/news/near-intents-recovers-entire-stolen-38m-after-ultimatum-to-exploiter
- NEAR AI Agent Market: payments in USD or USDC, a third-party wallet provider, no gas, 5% fee. https://docs.market.near.ai/concepts/payments-and-disputes.md ; https://docs.market.near.ai/builders/faq.md ; public data: https://market.near.ai/v1/platform/stats and https://market.near.ai/v1/agents (snapshot by `pipeline/agent_market.py`)
- Confidential Intents general availability (7 Jul 2026) and share reports: https://glitchwire.com/news/nears-confidential-intents-reaches-general-availability-bringing-privacy-infrast/ ; https://nansen.ai/post/nansen-near-quarterly-report-q2-2026

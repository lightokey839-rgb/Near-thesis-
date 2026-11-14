-- title: Accounts credited at epoch boundaries without being validators (a test for a protocol treasury cut), Sep-Oct 2026
-- sentence: If 10% of issuance went to a protocol treasury, one non-validator account would be credited about 60 times a month at epoch boundaries, with about 273,000 NEAR a month in total; if none appears, the on-chain 0% treasury cut holds.
-- optional: true
-- NOT RUN for the thesis (no billing project was available on 14 Nov 2026). Run it on purpose with:
--   python pipeline/bq_run.py q34
-- How to read the result:
--   * Validator rewards are applied in account_changes rows with update_reason = 'VALIDATOR_ACCOUNTS_UPDATE'.
--     Validators and staking pools have a staked balance; a treasury account would not.
--   * An account here with ~60 epoch credits a month (one per ~12-hour epoch) and credits summing to roughly
--     10% of issuance (about 273K NEAR a month at 2.5% on 1.31B NEAR) would contradict the RPC's protocol_reward_rate = 0.
--   * No such account, or only small credits, is consistent with the RPC. Either way, THESIS.md section 4 keeps the
--     treasury cut OPEN until this has been run and pinned.
WITH ch AS (
  SELECT block_date, block_height, index_in_block, affected_account_id,
         affected_account_nonstaked_balance / 1e24 AS bal, affected_account_staked_balance / 1e24 AS staked
  FROM `bigquery-public-data.crypto_near_mainnet_us.account_changes`
  WHERE block_date BETWEEN '2026-09-01' AND '2026-10-31'
    AND update_reason = 'VALIDATOR_ACCOUNTS_UPDATE'
),
prev AS (
  -- the same account's previous balance, from any change, so a credit is measured as a balance increase
  SELECT c.*, (
    SELECT p.affected_account_nonstaked_balance / 1e24
    FROM `bigquery-public-data.crypto_near_mainnet_us.account_changes` p
    WHERE p.block_date BETWEEN '2026-08-25' AND '2026-10-31'
      AND p.affected_account_id = c.affected_account_id
      AND (p.block_height < c.block_height OR (p.block_height = c.block_height AND p.index_in_block < c.index_in_block))
    ORDER BY p.block_height DESC, p.index_in_block DESC
    LIMIT 1) AS bal_before
  FROM ch c
  WHERE c.staked = 0
)
SELECT
  FORMAT_DATE('%Y-%m', block_date) AS month,
  affected_account_id,
  COUNT(*) AS epoch_updates,
  SUM(GREATEST(bal - IFNULL(bal_before, bal), 0)) AS near_credited
FROM prev
GROUP BY month, affected_account_id
HAVING COUNT(*) >= 10
ORDER BY month, near_credited DESC
LIMIT 200

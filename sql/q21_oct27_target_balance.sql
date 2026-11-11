-- title: 27 Oct event - daily balance of the unnamed address, 20 Oct to 9 Nov
-- sentence: Shows how much NEAR the address collected on 27 Oct and whether it was moved out afterwards.
-- Uses account_changes (balance after every change) instead of the heavy args column.
WITH ch AS (
  SELECT block_date, block_height, index_in_block, update_reason,
         affected_account_nonstaked_balance / 1e24 AS bal, affected_account_staked_balance / 1e24 AS staked
  FROM `bigquery-public-data.crypto_near_mainnet_us.account_changes`
  WHERE block_date BETWEEN '2026-10-20' AND '2026-11-09'
    AND affected_account_id = '282acb8e0fea9c3b2a87f01ba8a3eaff8447d1958adf4bdd1a81d6a7720547ef'
),
d AS (
  SELECT *, bal - LAG(bal) OVER (ORDER BY block_height, index_in_block) AS delta FROM ch
)
SELECT
  block_date,
  COUNT(*) AS changes,
  ARRAY_AGG(bal ORDER BY block_height DESC, index_in_block DESC LIMIT 1)[OFFSET(0)] AS end_of_day_near,
  MAX(staked) AS max_staked_near,
  SUM(IF(delta > 0, delta, 0)) AS inflow_near,
  SUM(IF(delta < 0, -delta, 0)) AS outflow_near,
  COUNTIF(delta < -1) AS outflows_over_1_near,
  STRING_AGG(DISTINCT update_reason) AS update_reasons
FROM d
GROUP BY block_date
ORDER BY block_date

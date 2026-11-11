-- title: Buyback wallet (buybacks.multisignature.near) - daily NEAR balance, inflows and outflows 1 Jul to 9 Nov 2026
-- sentence: If bought-back NEAR were burned or sold, the balance would fall; a balance that only rises means the NEAR is being held.
WITH ch AS (
  SELECT block_date, block_height, index_in_block, update_reason,
         affected_account_nonstaked_balance / 1e24 AS bal, affected_account_staked_balance / 1e24 AS staked
  FROM `bigquery-public-data.crypto_near_mainnet_us.account_changes`
  WHERE block_date BETWEEN '2026-07-01' AND '2026-11-09'
    AND affected_account_id = 'buybacks.multisignature.near'
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
  MIN(delta) AS largest_single_outflow_near
FROM d
GROUP BY block_date
ORDER BY block_date

-- title: Buyback wallet - every balance change on 9 Sep 2026, the day it gained about 515k NEAR
-- sentence: Lists the transactions behind the one-off jump in the buyback wallet so anyone can look them up on an explorer.
WITH ch AS (
  SELECT block_date, block_timestamp_utc, block_height, index_in_block, update_reason,
         caused_by_transaction_hash, caused_by_receipt_id,
         affected_account_nonstaked_balance / 1e24 AS bal
  FROM `bigquery-public-data.crypto_near_mainnet_us.account_changes`
  WHERE block_date BETWEEN '2026-09-08' AND '2026-09-09'
    AND affected_account_id = 'buybacks.multisignature.near'
),
d AS (
  SELECT *, bal - LAG(bal) OVER (ORDER BY block_height, index_in_block) AS delta FROM ch
)
SELECT block_date, block_timestamp_utc, update_reason, ROUND(delta, 4) AS delta_near, ROUND(bal, 4) AS balance_after_near,
       caused_by_transaction_hash, caused_by_receipt_id
FROM d
WHERE block_date = '2026-09-09' AND ABS(delta) >= 1000
ORDER BY block_height, index_in_block

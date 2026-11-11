-- title: Buyback wallet - every balance change of 1,000 NEAR or more 1 Jul to 9 Nov 2026
-- optional: true
-- Costly (~100+ GB). Run by name only if q30 shows outflows worth tracing:  python pipeline/bq_run.py q31
-- sentence: Lists each large move in or out of the buyback wallet with the transaction that caused it, so anyone can check it on an explorer.
WITH ch AS (
  SELECT block_date, block_timestamp_utc, block_height, index_in_block, update_reason,
         caused_by_transaction_hash, caused_by_receipt_id,
         affected_account_nonstaked_balance / 1e24 AS bal
  FROM `bigquery-public-data.crypto_near_mainnet_us.account_changes`
  WHERE block_date BETWEEN '2026-07-01' AND '2026-11-09'
    AND affected_account_id = 'buybacks.multisignature.near'
),
d AS (
  SELECT *, bal - LAG(bal) OVER (ORDER BY block_height, index_in_block) AS delta FROM ch
)
SELECT block_date, block_timestamp_utc, update_reason, ROUND(delta, 4) AS delta_near, ROUND(bal, 4) AS balance_after_near,
       caused_by_transaction_hash, caused_by_receipt_id
FROM d
WHERE ABS(delta) >= 1000
ORDER BY block_height, index_in_block

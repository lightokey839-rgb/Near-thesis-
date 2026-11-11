-- title: Helper table - one row per signing account per day, 1 Jan to 9 Nov 2026
-- sentence: Built once from the public NEAR transactions table so every account chart reads this small table instead of rescanning the chain.
-- No PARTITION BY on purpose: BigQuery Sandbox deletes partitions older than 60 days.
CREATE OR REPLACE TABLE `{{project}}.{{dataset}}.signer_day`
CLUSTER BY block_date, signer AS
SELECT
  block_date,
  signer_account_id AS signer,
  COUNT(*) AS txs,
  COUNTIF(receiver_account_id = signer_account_id) AS self_txs,
  COUNTIF(receiver_account_id = 'game.hot.tg') AS game_txs,
  COUNT(DISTINCT receiver_account_id) AS receivers,
  -- counterparties other than the HOT game contract and the account itself
  COUNT(DISTINCT IF(receiver_account_id != 'game.hot.tg' AND receiver_account_id != signer_account_id,
                    receiver_account_id, NULL)) AS other_receivers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN '2026-01-01' AND '2026-11-09'
GROUP BY block_date, signer

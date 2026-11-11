-- title: 27 Oct event - what the 12,028 sending accounts did earlier in 2026
-- sentence: Shows when the accounts that swept NEAR to one address on 27 Oct were last active, and whether they were HOT game accounts, before going quiet.
WITH senders AS (
  SELECT DISTINCT signer_account_id AS a
  FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
  WHERE block_date = '2026-10-27'
    AND receiver_account_id = '282acb8e0fea9c3b2a87f01ba8a3eaff8447d1958adf4bdd1a81d6a7720547ef'
),
hist AS (
  SELECT d.signer, MIN(d.block_date) AS first_day, MAX(IF(d.block_date < '2026-10-27', d.block_date, NULL)) AS last_day_before,
         COUNTIF(d.block_date < '2026-10-27') AS active_days_before, SUM(IF(d.block_date < '2026-10-27', d.game_txs, 0)) AS game_txs_before,
         SUM(IF(d.block_date < '2026-10-27', d.txs, 0)) AS txs_before
  FROM `{{project}}.{{dataset}}.signer_day` d JOIN senders s ON s.a = d.signer
  GROUP BY d.signer
)
SELECT
  DATE_TRUNC(first_day, MONTH) AS first_active_month_2026,
  DATE_TRUNC(last_day_before, MONTH) AS last_active_month_before_oct27,
  COUNT(*) AS accounts,
  COUNTIF(game_txs_before > 0) AS accounts_with_game_txs,
  SUM(txs_before) AS txs_before,
  APPROX_QUANTILES(active_days_before, 2)[OFFSET(1)] AS median_active_days_before,
  (SELECT COUNT(*) FROM senders) AS senders_total
FROM hist
GROUP BY 1, 2
ORDER BY accounts DESC

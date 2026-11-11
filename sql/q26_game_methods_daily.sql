-- title: HOT game (game.hot.tg) calls by method on seven sample days, 7 Jul to 1 Oct
-- sentence: Shows which game action fell as daily game signers dropped from about 101k (7 Jul) to about 40k (15 Sep).
-- Seven sample days instead of every day keeps the heavy args column cheap to read.
SELECT
  block_date,
  JSON_VALUE(args, '$.method_name') AS method,
  COUNT(*) AS calls,
  COUNT(DISTINCT receipt_predecessor_account_id) AS callers
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date IN ('2026-07-07', '2026-08-01', '2026-08-20', '2026-09-01', '2026-09-10', '2026-09-15', '2026-10-01')
  AND receipt_receiver_account_id = 'game.hot.tg'
  AND action_kind = 'FUNCTION_CALL'
GROUP BY 1, 2
HAVING calls >= 100
ORDER BY 1, calls DESC

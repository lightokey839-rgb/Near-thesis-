-- title: 27 Oct event - who sent to the unnamed address, and what they sent
-- sentence: Breaks down the one-off transactions sent to address 282acb...47ef on 26-28 Oct by type of sending account, action and NEAR attached.
-- Cost note: the args column (needed for the NEAR amount) is read for 26-28 Oct only.
WITH tx AS (
  SELECT block_date, signer_account_id AS signer, converted_into_receipt_id AS rid, status
  FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
  WHERE block_date BETWEEN '2026-10-26' AND '2026-10-28'
    AND receiver_account_id = '282acb8e0fea9c3b2a87f01ba8a3eaff8447d1958adf4bdd1a81d6a7720547ef'
),
act AS (
  SELECT receipt_id, action_kind,
         JSON_VALUE(args, '$.method_name') AS method,
         SAFE_CAST(JSON_VALUE(args, '$.deposit') AS BIGNUMERIC) / 1e24 AS deposit_near
  FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
  WHERE block_date BETWEEN '2026-10-26' AND '2026-10-28'
    AND receipt_receiver_account_id = '282acb8e0fea9c3b2a87f01ba8a3eaff8447d1958adf4bdd1a81d6a7720547ef'
)
SELECT
  tx.block_date,
  tx.status,
  CASE WHEN REGEXP_CONTAINS(signer, r'^[0-9a-f]{64}$') THEN 'implicit_hex'
       WHEN REGEXP_CONTAINS(signer, r'^0x[0-9a-f]{40}$') THEN 'eth_implicit'
       WHEN ENDS_WITH(signer, '.tg') THEN 'dot_tg'
       WHEN ENDS_WITH(signer, '.near') THEN 'dot_near'
       ELSE 'other' END AS signer_kind,
  REGEXP_EXTRACT(signer, r'([^.]+\.[^.]+)$') AS parent_account,
  act.action_kind, act.method,
  COUNT(*) AS txs, COUNT(DISTINCT signer) AS signers,
  SUM(act.deposit_near) AS deposit_near,
  APPROX_QUANTILES(act.deposit_near, 2)[OFFSET(1)] AS median_deposit_near
FROM tx LEFT JOIN act ON act.receipt_id = tx.rid
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY 1, txs DESC

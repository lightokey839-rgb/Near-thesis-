-- title: 27 Oct event - where the unnamed address sent its NEAR, 20 Oct to 31 Oct
-- sentence: Names the accounts that received NEAR from address 282acb...47ef, including the 78,677 NEAR it moved out on 29 Oct.
SELECT
  block_date,
  receipt_receiver_account_id AS receiver,
  action_kind,
  JSON_VALUE(args, '$.method_name') AS method,
  COUNT(*) AS actions,
  SUM(SAFE_CAST(JSON_VALUE(args, '$.deposit') AS BIGNUMERIC)) / 1e24 AS deposit_near
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date BETWEEN '2026-10-20' AND '2026-10-31'
  AND receipt_predecessor_account_id = '282acb8e0fea9c3b2a87f01ba8a3eaff8447d1958adf4bdd1a81d6a7720547ef'
GROUP BY 1, 2, 3, 4
ORDER BY 1, deposit_near DESC
LIMIT 200

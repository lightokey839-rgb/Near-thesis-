-- title: 3 Nov event - who funded the unnamed accounts first seen on 2-4 Nov
-- sentence: If a few funders created most new unnamed accounts, the 3 Nov rise was a campaign or a product launch, not broad organic growth.
-- Skips the heavy args column, so amounts are not shown here.
WITH first_seen AS (
  SELECT signer, MIN(block_date) AS first_day
  FROM `{{project}}.{{dataset}}.signer_day` GROUP BY signer
),
new_hex AS (
  SELECT signer AS a, first_day FROM first_seen
  WHERE first_day BETWEEN '2026-11-02' AND '2026-11-04'
    AND REGEXP_CONTAINS(signer, r'^[0-9a-f]{64}$')
),
inc AS (
  SELECT ra.receipt_receiver_account_id AS a, ra.receipt_predecessor_account_id AS funder, n.first_day,
         ROW_NUMBER() OVER (PARTITION BY ra.receipt_receiver_account_id
                            ORDER BY ra.block_height, ra.index_in_action_receipt) AS rn
  FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` ra
  JOIN new_hex n ON n.a = ra.receipt_receiver_account_id
  WHERE ra.block_date BETWEEN '2026-10-20' AND '2026-11-04'
    AND ra.receipt_predecessor_account_id != 'system'
    AND ra.receipt_predecessor_account_id != ra.receipt_receiver_account_id
),
agg AS (
  SELECT first_day, funder, COUNT(*) AS accounts_first_funded
  FROM inc WHERE rn = 1
  GROUP BY 1, 2
)
SELECT * FROM agg
QUALIFY ROW_NUMBER() OVER (PARTITION BY first_day ORDER BY accounts_first_funded DESC) <= 20
ORDER BY first_day, accounts_first_funded DESC

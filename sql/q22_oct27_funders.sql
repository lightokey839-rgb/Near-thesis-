-- title: 27 Oct event - who first funded the 12,028 sending accounts
-- sentence: If one account funded most of the senders, the event was one operator's campaign rather than 12,028 independent users.
-- Looks back 30 days (27 Sep - 27 Oct). Skips the heavy args column, so amounts are not shown here.
WITH senders AS (
  SELECT DISTINCT signer_account_id AS a
  FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
  WHERE block_date = '2026-10-27'
    AND receiver_account_id = '282acb8e0fea9c3b2a87f01ba8a3eaff8447d1958adf4bdd1a81d6a7720547ef'
),
inc AS (
  SELECT ra.receipt_receiver_account_id AS a, ra.receipt_predecessor_account_id AS funder,
         ra.block_date, ra.action_kind,
         ROW_NUMBER() OVER (PARTITION BY ra.receipt_receiver_account_id
                            ORDER BY ra.block_height, ra.index_in_action_receipt) AS rn
  FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` ra
  JOIN senders s ON s.a = ra.receipt_receiver_account_id
  WHERE ra.block_date BETWEEN '2026-09-27' AND '2026-10-27'
    AND ra.receipt_predecessor_account_id != 'system'
    AND ra.receipt_predecessor_account_id != ra.receipt_receiver_account_id
)
SELECT funder, action_kind, MIN(block_date) AS first_day, MAX(block_date) AS last_day,
       COUNT(*) AS accounts_first_funded,
       (SELECT COUNT(*) FROM senders) AS senders_total
FROM inc WHERE rn = 1
GROUP BY 1, 2
ORDER BY accounts_first_funded DESC
LIMIT 50

-- title: Buyback wallet - who sends to it and who it sends to, weekly, 1 Sep to 9 Nov
-- sentence: Names the accounts on the other side of the buyback wallet's receipts, showing where its NEAR comes from and where any of it goes.
-- Skips the heavy args column (amounts come from q30/q31 instead).
SELECT
  DATE_TRUNC(block_date, WEEK(MONDAY)) AS week,
  IF(receipt_receiver_account_id = 'buybacks.multisignature.near', 'in', 'out') AS direction,
  IF(receipt_receiver_account_id = 'buybacks.multisignature.near',
     receipt_predecessor_account_id, receipt_receiver_account_id) AS counterparty,
  action_kind,
  COUNT(*) AS actions
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date BETWEEN '2026-09-01' AND '2026-11-09'
  AND (receipt_receiver_account_id = 'buybacks.multisignature.near'
       OR receipt_predecessor_account_id = 'buybacks.multisignature.near')
  AND receipt_predecessor_account_id != receipt_receiver_account_id
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, actions DESC

-- title: 3 Nov event - which contracts the unnamed (64-hex) signers used, 30 Oct to 6 Nov
-- sentence: Lists the top contracts called by new and returning unnamed accounts each day around 3 Nov.
WITH first_seen AS (
  SELECT signer, MIN(block_date) AS first_day
  FROM `{{project}}.{{dataset}}.signer_day` GROUP BY signer
),
tx AS (
  SELECT block_date, signer_account_id AS signer, receiver_account_id AS receiver
  FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
  WHERE block_date BETWEEN '2026-10-30' AND '2026-11-06'
    AND REGEXP_CONTAINS(signer_account_id, r'^[0-9a-f]{64}$')
    AND receiver_account_id != 'game.hot.tg'
    AND receiver_account_id != signer_account_id
),
agg AS (
  SELECT tx.block_date, (f.first_day = tx.block_date) AS signer_new_that_day, tx.receiver,
         COUNT(DISTINCT tx.signer) AS signers, COUNT(*) AS txs
  FROM tx JOIN first_seen f USING (signer)
  GROUP BY 1, 2, 3
)
SELECT * FROM agg
QUALIFY ROW_NUMBER() OVER (PARTITION BY block_date, signer_new_that_day ORDER BY signers DESC) <= 15
ORDER BY block_date, signer_new_that_day, signers DESC

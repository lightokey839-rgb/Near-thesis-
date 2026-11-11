-- title: Who made the self-transaction bursts (Feb 2026, 2-3 Oct, 3 Nov)
-- sentence: Groups accounts that only sent transactions to themselves by account family, to show these bursts come from a few account factories, not from users.
SELECT
  CASE WHEN block_date BETWEEN '2026-02-01' AND '2026-02-28' THEN 'feb_2026'
       WHEN block_date BETWEEN '2026-10-02' AND '2026-10-08' THEN 'oct_02_08'
       WHEN block_date = '2026-11-03' THEN 'nov_03'
       ELSE 'other' END AS burst,
  CASE WHEN REGEXP_CONTAINS(signer, r'^[0-9a-f]{64}$') THEN '(implicit_hex)'
       WHEN REGEXP_CONTAINS(signer, r'^0x[0-9a-f]{40}$') THEN '(eth_implicit)'
       ELSE IFNULL(REGEXP_EXTRACT(signer, r'\.([^.]+\.[^.]+)$'), REGEXP_EXTRACT(signer, r'([^.]+)$')) END AS account_family,
  COUNT(DISTINCT signer) AS accounts,
  SUM(txs) AS txs,
  COUNT(DISTINCT block_date) AS days
FROM `{{project}}.{{dataset}}.signer_day`
WHERE (block_date BETWEEN '2026-02-01' AND '2026-02-28' OR block_date BETWEEN '2026-10-02' AND '2026-10-08' OR block_date = '2026-11-03')
  AND other_receivers = 0 AND game_txs = 0 AND self_txs = txs
GROUP BY 1, 2
QUALIFY ROW_NUMBER() OVER (PARTITION BY burst ORDER BY COUNT(DISTINCT signer) DESC) <= 8
ORDER BY burst, accounts DESC

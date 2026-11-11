-- title: Organic implicit (64-hex) signers per day - new vs returning, 1 Oct to 9 Nov
-- sentence: Tests whether the 3 Nov rise in unnamed-account signers came from brand-new accounts or from existing ones waking up.
WITH first_seen AS (
  SELECT signer, MIN(block_date) AS first_day
  FROM `{{project}}.{{dataset}}.signer_day` GROUP BY signer
)
SELECT
  d.block_date,
  COUNT(*) AS organic_hex_signers,
  COUNTIF(f.first_day = d.block_date) AS new_that_day,
  COUNTIF(f.first_day < d.block_date) AS seen_before,
  COUNTIF(d.other_receivers >= 2) AS with_2plus_counterparties
FROM `{{project}}.{{dataset}}.signer_day` d
JOIN first_seen f USING (signer)
WHERE d.block_date BETWEEN '2026-10-01' AND '2026-11-09'
  AND d.other_receivers > 0
  AND REGEXP_CONTAINS(d.signer, r'^[0-9a-f]{64}$')
GROUP BY d.block_date
ORDER BY d.block_date

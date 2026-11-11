-- title: Daily signing accounts by segment, Jan-Nov 2026
-- sentence: Most daily NEAR signers are HOT game accounts; the "organic" line counts accounts that sent at least one transaction to something other than the game or themselves, excluding the kaiching self-transaction factory.
SELECT
  block_date,
  COUNT(*) AS all_signers,
  COUNTIF(game_txs > 0) AS game_signers,
  COUNTIF(game_txs = txs) AS game_only_signers,
  COUNTIF(ENDS_WITH(signer, '.users.kaiching')) AS kaiching_factory_signers,
  COUNTIF(other_receivers = 0 AND game_txs < txs) AS self_only_signers,
  COUNTIF(other_receivers > 0 AND NOT ENDS_WITH(signer, '.users.kaiching')) AS organic_signers,
  COUNTIF(other_receivers > 0 AND NOT ENDS_WITH(signer, '.users.kaiching')
          AND REGEXP_CONTAINS(signer, r'^[0-9a-f]{64}$')) AS organic_hex_implicit,
  COUNTIF(other_receivers > 0 AND NOT ENDS_WITH(signer, '.users.kaiching')
          AND REGEXP_CONTAINS(signer, r'^0x[0-9a-f]{40}$')) AS organic_eth_implicit,
  COUNTIF(other_receivers > 0 AND NOT ENDS_WITH(signer, '.users.kaiching') AND ENDS_WITH(signer, '.tg')) AS organic_tg,
  COUNTIF(other_receivers > 0 AND NOT ENDS_WITH(signer, '.users.kaiching') AND ENDS_WITH(signer, '.near')) AS organic_dot_near,
  SUM(txs) AS txs_all,
  SUM(game_txs) AS txs_game
FROM `{{project}}.{{dataset}}.signer_day`
GROUP BY block_date
ORDER BY block_date

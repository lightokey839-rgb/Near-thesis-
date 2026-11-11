-- title: Weekly "real active accounts" under four stricter definitions
-- sentence: Each step down removes more accounts that look automated or one-off; the bottom line (engaged and returning) is our most conservative count of real users.
-- L1 organic: sent >=1 tx to something other than game.hot.tg or itself, not a *.users.kaiching account.
-- L2 engaged: L1 and (organic on >=2 days that week, or >=2 distinct counterparties on one day).
-- L3 returning: L1 and also L1 in one of the previous 4 weeks.
-- L4: both L2 and L3.
-- Approximation: counterparties are counted per day, not de-duplicated across the week.
WITH w AS (
  SELECT
    DATE_TRUNC(block_date, WEEK(MONDAY)) AS week,
    signer,
    COUNT(*) AS active_days,
    COUNTIF(other_receivers > 0) AS organic_days,
    MAX(other_receivers) AS max_daily_counterparties,
    LOGICAL_AND(game_txs = txs) AS game_only,
    LOGICAL_OR(ENDS_WITH(signer, '.users.kaiching')) AS kaiching
  FROM `{{project}}.{{dataset}}.signer_day`
  GROUP BY week, signer
),
l1 AS (
  SELECT *, LAG(week) OVER (PARTITION BY signer ORDER BY week) AS prev_l1_week
  FROM w
  WHERE organic_days > 0 AND NOT kaiching
),
a AS (
  SELECT week, COUNT(*) AS all_signers, COUNTIF(game_only) AS game_only_signers,
         COUNTIF(NOT game_only) AS non_game_signers
  FROM w GROUP BY week
),
b AS (
  SELECT week,
    COUNT(*) AS l1_organic,
    COUNTIF(organic_days >= 2 OR max_daily_counterparties >= 2) AS l2_engaged,
    COUNTIF(prev_l1_week >= DATE_SUB(week, INTERVAL 28 DAY)) AS l3_returning,
    COUNTIF((organic_days >= 2 OR max_daily_counterparties >= 2)
            AND prev_l1_week >= DATE_SUB(week, INTERVAL 28 DAY)) AS l4_engaged_and_returning,
    COUNTIF(REGEXP_CONTAINS(signer, r'^[0-9a-f]{64}$')) AS l1_hex_implicit
  FROM l1 GROUP BY week
)
SELECT a.*, b.* EXCEPT (week)
FROM a LEFT JOIN b USING (week)
ORDER BY week

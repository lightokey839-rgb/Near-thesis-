-- title: Weekly retention of organic accounts by first-seen week
-- sentence: Of the accounts first seen doing something other than the HOT game in a given week, this shows how many came back in later weeks.
-- Caveat: "first seen" means first seen since 1 Jan 2026, so January cohorts include older users.
WITH l1 AS (
  SELECT DISTINCT DATE_TRUNC(block_date, WEEK(MONDAY)) AS week, signer
  FROM `{{project}}.{{dataset}}.signer_day`
  WHERE other_receivers > 0 AND NOT ENDS_WITH(signer, '.users.kaiching')
),
first_week AS (SELECT signer, MIN(week) AS cohort FROM l1 GROUP BY signer),
j AS (
  SELECT f.cohort, f.signer, DATE_DIFF(l.week, f.cohort, WEEK) AS k
  FROM first_week f JOIN l1 l USING (signer)
)
SELECT
  cohort,
  COUNT(DISTINCT signer) AS accounts,
  COUNT(DISTINCT IF(k = 1, signer, NULL)) AS active_week_1,
  COUNT(DISTINCT IF(k BETWEEN 1 AND 4, signer, NULL)) AS active_weeks_1_to_4,
  COUNT(DISTINCT IF(k BETWEEN 5 AND 8, signer, NULL)) AS active_weeks_5_to_8,
  DATE_DIFF(DATE '2026-11-09', cohort, WEEK) AS weeks_observable
FROM j
GROUP BY cohort
ORDER BY cohort

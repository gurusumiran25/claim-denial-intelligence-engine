-- 04: denial rate by filing lag bucket (days_to_file is synthesized, see ADR-009)
SELECT
  CASE
    WHEN l.days_to_file <= 30 THEN '1: 0-30 days'
    WHEN l.days_to_file <= 60 THEN '2: 31-60 days'
    WHEN l.days_to_file <= 90 THEN '3: 61-90 days'
    ELSE '4: 91+ days'
  END AS days_to_file_bucket,
  COUNT(*) AS claims,
  ROUND(AVG(l.is_denied), 4) AS denial_rate
FROM claims_dw.claim_labels AS l
GROUP BY days_to_file_bucket
ORDER BY days_to_file_bucket;

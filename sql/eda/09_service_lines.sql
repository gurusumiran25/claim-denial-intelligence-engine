-- 09: denial rate by number of service lines and claim type
SELECT
  u.claim_type,
  CASE
    WHEN u.n_lines <= 1 THEN '1 line'
    WHEN u.n_lines <= 5 THEN '2-5 lines'
    ELSE '6+ lines'
  END AS line_bucket,
  COUNT(*) AS claims,
  ROUND(AVG(l.is_denied), 4) AS denial_rate
FROM claims_dw.claims_unified AS u
JOIN claims_dw.claim_labels AS l USING (claim_id)
GROUP BY u.claim_type, line_bucket
ORDER BY u.claim_type, line_bucket;

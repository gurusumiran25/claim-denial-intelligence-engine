-- 08: denial rate by coverage status (coverage_active comes from the real beneficiary files)
SELECT
  u.coverage_active,
  COUNT(*) AS claims,
  ROUND(AVG(l.is_denied), 4) AS denial_rate
FROM claims_dw.claims_unified AS u
JOIN claims_dw.claim_labels AS l USING (claim_id)
GROUP BY u.coverage_active
ORDER BY u.coverage_active;

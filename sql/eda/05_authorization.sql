-- 05: denial rate by authorization status (synthesized fields, see ADR-009)
SELECT
  l.auth_required,
  l.auth_on_file,
  COUNT(*) AS claims,
  ROUND(AVG(l.is_denied), 4) AS denial_rate
FROM claims_dw.claim_labels AS l
GROUP BY l.auth_required, l.auth_on_file
ORDER BY l.auth_required, l.auth_on_file;

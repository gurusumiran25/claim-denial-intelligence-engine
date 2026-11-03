-- 01: claims, denial rate and dollars by claim type
SELECT
  u.claim_type,
  COUNT(*) AS claims,
  SUM(l.is_denied) AS denied,
  ROUND(AVG(l.is_denied), 4) AS denial_rate,
  ROUND(SUM(u.amount)) AS total_amount,
  ROUND(SUM(IF(l.is_denied = 1, u.amount, 0))) AS denied_amount,
  ROUND(SAFE_DIVIDE(SUM(IF(l.is_denied = 1, u.amount, 0)), SUM(u.amount)), 4) AS denied_dollar_share
FROM claims_dw.claims_unified AS u
JOIN claims_dw.claim_labels AS l USING (claim_id)
GROUP BY u.claim_type
ORDER BY claims DESC;

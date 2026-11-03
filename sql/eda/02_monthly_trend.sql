-- 02: denial rate and denied dollars by service month (checks for drift over time)
SELECT
  DATE_TRUNC(u.from_dt, MONTH) AS month,
  COUNT(*) AS claims,
  ROUND(AVG(l.is_denied), 4) AS denial_rate,
  ROUND(SUM(IF(l.is_denied = 1, u.amount, 0))) AS denied_amount
FROM claims_dw.claims_unified AS u
JOIN claims_dw.claim_labels AS l USING (claim_id)
GROUP BY month
ORDER BY month;

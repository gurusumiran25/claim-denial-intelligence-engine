-- 06: denial rate by amount decile within each claim type
WITH scored AS (
  SELECT
    u.claim_type,
    u.amount,
    l.is_denied,
    NTILE(10) OVER (PARTITION BY u.claim_type ORDER BY u.amount) AS amount_decile
  FROM claims_dw.claims_unified AS u
  JOIN claims_dw.claim_labels AS l USING (claim_id)
)
SELECT
  claim_type,
  amount_decile,
  COUNT(*) AS claims,
  ROUND(MIN(amount)) AS min_amount,
  ROUND(MAX(amount)) AS max_amount,
  ROUND(AVG(is_denied), 4) AS denial_rate
FROM scored
GROUP BY claim_type, amount_decile
ORDER BY claim_type, amount_decile;

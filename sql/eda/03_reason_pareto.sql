-- 03: denial reasons (CARC) as a Pareto, by claim count and by dollars
WITH reasons AS (
  SELECT
    l.carc_code,
    COUNT(*) AS denied_claims,
    ROUND(SUM(u.amount)) AS denied_amount
  FROM claims_dw.claims_unified AS u
  JOIN claims_dw.claim_labels AS l USING (claim_id)
  WHERE l.is_denied = 1
  GROUP BY l.carc_code
)
SELECT
  carc_code,
  denied_claims,
  ROUND(SAFE_DIVIDE(denied_claims, SUM(denied_claims) OVER ()), 4) AS share_of_denials,
  ROUND(SAFE_DIVIDE(SUM(denied_claims) OVER (ORDER BY denied_claims DESC), SUM(denied_claims) OVER ()), 4) AS cumulative_share,
  denied_amount,
  ROUND(SAFE_DIVIDE(denied_amount, SUM(denied_amount) OVER ()), 4) AS share_of_denied_dollars
FROM reasons
ORDER BY denied_claims DESC;

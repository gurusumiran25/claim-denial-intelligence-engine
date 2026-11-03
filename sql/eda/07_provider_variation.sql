-- 07: how much do providers differ? (providers with at least 100 claims)
WITH provider_rates AS (
  SELECT
    u.provider_id,
    COUNT(*) AS claims,
    AVG(l.is_denied) AS denial_rate
  FROM claims_dw.claims_unified AS u
  JOIN claims_dw.claim_labels AS l USING (claim_id)
  GROUP BY u.provider_id
  HAVING COUNT(*) >= 100
)
SELECT
  COUNT(*) AS providers_with_100_plus_claims,
  ROUND(AVG(denial_rate), 4) AS mean_rate,
  ROUND(APPROX_QUANTILES(denial_rate, 100)[OFFSET(10)], 4) AS p10,
  ROUND(APPROX_QUANTILES(denial_rate, 100)[OFFSET(50)], 4) AS p50,
  ROUND(APPROX_QUANTILES(denial_rate, 100)[OFFSET(90)], 4) AS p90,
  ROUND(APPROX_QUANTILES(denial_rate, 100)[OFFSET(99)], 4) AS p99,
  ROUND(MAX(denial_rate), 4) AS max_rate
FROM provider_rates;

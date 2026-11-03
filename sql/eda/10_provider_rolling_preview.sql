-- 10: preview of a leakage-safe feature (Week 3): each provider's denial rate over the
-- 90 days BEFORE each service date (the current day is excluded). Shown for the 5 busiest providers.
WITH top_providers AS (
  SELECT provider_id
  FROM claims_dw.claims_unified
  GROUP BY provider_id
  ORDER BY COUNT(*) DESC
  LIMIT 5
),
daily AS (
  SELECT
    u.provider_id,
    u.from_dt,
    COUNT(*) AS claims,
    SUM(l.is_denied) AS denied
  FROM claims_dw.claims_unified AS u
  JOIN claims_dw.claim_labels AS l USING (claim_id)
  WHERE u.provider_id IN (SELECT provider_id FROM top_providers)
  GROUP BY u.provider_id, u.from_dt
)
SELECT
  provider_id,
  from_dt,
  claims,
  denied,
  SUM(claims) OVER w AS prior_90d_claims,
  SUM(denied) OVER w AS prior_90d_denied,
  ROUND(SAFE_DIVIDE(SUM(denied) OVER w, SUM(claims) OVER w), 4) AS prior_90d_denial_rate
FROM daily
WINDOW w AS (
  PARTITION BY provider_id
  ORDER BY UNIX_DATE(from_dt)
  RANGE BETWEEN 90 PRECEDING AND 1 PRECEDING
)
ORDER BY provider_id, from_dt
LIMIT 60;

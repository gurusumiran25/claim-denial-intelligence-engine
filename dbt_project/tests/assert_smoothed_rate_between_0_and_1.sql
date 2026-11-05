select claim_id, provider_denial_rate_smoothed
from {{ ref('fct_claim_features') }}
where provider_denial_rate_smoothed < 0 or provider_denial_rate_smoothed > 1

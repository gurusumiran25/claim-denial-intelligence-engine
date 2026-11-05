{% set lag = var('feedback_lag_days') %}
{% set span = var('history_days') %}
-- Recompute provider history the slow way for a small sample of claims and compare.
-- Window: service days from (day - lag - span) to (day - lag), i.e. strictly before the claim.
with sample as (
    select claim_id, provider_id, day_index, provider_prior_claims, provider_prior_denied
    from {{ ref('fct_claim_features') }}
    where right(claim_id, 4) = '7777'
),

brute as (
    select
        s.claim_id,
        count(p.claim_id) as claims_check,
        coalesce(sum(l.is_denied), 0) as denied_check
    from sample as s
    left join {{ ref('stg_claims') }} as p
        on p.provider_id = s.provider_id
        and p.day_index between s.day_index - {{ lag + span }} and s.day_index - {{ lag }}
    left join {{ ref('stg_claim_labels') }} as l
        on l.claim_id = p.claim_id
    group by s.claim_id
)

select s.claim_id, s.provider_prior_claims, b.claims_check, s.provider_prior_denied, b.denied_check
from sample as s
inner join brute as b on s.claim_id = b.claim_id
where s.provider_prior_claims != b.claims_check
    or s.provider_prior_denied != b.denied_check

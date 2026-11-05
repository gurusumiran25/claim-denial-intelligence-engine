{% set span = var('member_history_days') %}
-- Recompute member history for a sample of claims: window is the span days before the claim day.
with sample as (
    select claim_id, bene_id, day_index, member_claims_prior_90d
    from {{ ref('fct_claim_features') }}
    where right(claim_id, 4) = '7777'
),

brute as (
    select s.claim_id, count(p.claim_id) as claims_check
    from sample as s
    left join {{ ref('stg_claims') }} as p
        on p.bene_id = s.bene_id
        and p.day_index between s.day_index - {{ span }} and s.day_index - 1
    group by s.claim_id
)

select s.claim_id, s.member_claims_prior_90d, b.claims_check
from sample as s
inner join brute as b on s.claim_id = b.claim_id
where s.member_claims_prior_90d != b.claims_check

-- Denied claims with their reason, for the root-cause analysis (Week 5).
-- carc_code lives here, never in fct_claim_features.
select
    c.claim_id,
    c.claim_type,
    c.provider_id,
    c.from_dt,
    c.claim_year,
    c.claim_month,
    c.amount,
    l.carc_code,
    l.days_to_file,
    l.auth_required,
    l.auth_on_file,
    c.coverage_active,
    c.n_lines,
    c.procedure_code
from {{ ref('stg_claims') }} as c
inner join {{ ref('stg_claim_labels') }} as l
    on c.claim_id = l.claim_id
where l.is_denied = 1

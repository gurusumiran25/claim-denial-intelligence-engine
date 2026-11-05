{% set m = var('smoothing_strength') %}
{% set prior = var('prior_denial_rate') %}
-- One row per claim: model-ready features, target and time split.
-- Every history feature uses only dates before the claim (see tests/ for the brute-force check).
select
    -- ids and time (not features)
    c.claim_id,
    c.bene_id,
    c.provider_id,
    c.from_dt,
    c.claim_year,
    c.day_index,
    case
        when c.from_dt <= cast('{{ var("train_end") }}' as date) then 'train'
        when c.from_dt <= cast('{{ var("valid_end") }}' as date) then 'valid'
        else 'test'
    end as split,

    -- claim features
    c.claim_type,
    c.amount,
    ln(c.amount) as amount_log,
    c.n_lines,
    cast(c.procedure_code = 'UNKNOWN' as {{ dbt.type_int() }}) as procedure_unknown,
    substr(c.primary_dx, 1, 3) as dx_group,
    c.drg_code,
    c.los_days,
    c.claim_month,

    -- member features
    c.age_at_claim,
    c.sex,
    cast(c.coverage_active as {{ dbt.type_int() }}) as coverage_active,
    py.chronic_count_prior_year,
    coalesce(mh.member_claims_prior_90d, 0) as member_claims_prior_90d,

    -- submission features (synthesized, ADR-009)
    l.days_to_file,
    cast(l.auth_required as {{ dbt.type_int() }}) as auth_required,
    cast(l.auth_on_file as {{ dbt.type_int() }}) as auth_on_file,

    -- provider history features
    ph.provider_prior_claims,
    ph.provider_prior_denied,
    ph.provider_claims_prior_30d,
    (ph.provider_prior_denied + {{ m }} * {{ prior }})
        / (ph.provider_prior_claims + {{ m }}) as provider_denial_rate_smoothed,

    -- target
    l.is_denied
from {{ ref('stg_claims') }} as c
inner join {{ ref('stg_claim_labels') }} as l
    on c.claim_id = l.claim_id
left join {{ ref('int_provider_history') }} as ph
    on c.provider_id = ph.provider_id and c.day_index = ph.day_index
left join {{ ref('int_member_history') }} as mh
    on c.bene_id = mh.bene_id and c.day_index = mh.day_index
left join {{ ref('int_member_prior_year') }} as py
    on c.bene_id = py.bene_id and c.claim_year = py.claim_year

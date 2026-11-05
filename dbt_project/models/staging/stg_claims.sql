-- One row per claim. Adds calendar fields and an integer day index used by the history windows.
select
    claim_id,
    claim_type,
    bene_id,
    coalesce(provider_id, 'UNKNOWN') as provider_id,
    rendering_npi,
    from_dt,
    thru_dt,
    primary_dx,
    procedure_code,
    drg_code,
    los_days,
    n_lines,
    amount,
    age_at_claim,
    sex,
    coverage_active,
    extract(year from from_dt) as claim_year,
    extract(month from from_dt) as claim_month,
    {{ dbt.datediff("cast('2008-01-01' as date)", "from_dt", "day") }} as day_index
from {{ source('claims_dw', 'claims_unified') }}

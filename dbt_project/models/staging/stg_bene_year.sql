{% set flags = [
    'sp_alzheimer', 'sp_chf', 'sp_kidney', 'sp_cancer', 'sp_copd',
    'sp_depression', 'sp_diabetes', 'sp_ischemic_heart', 'sp_osteoporosis', 'sp_ra_oa', 'sp_stroke'
] %}
-- One row per member per year, with a count of chronic conditions (flag value 1 = present).
select
    bene_id,
    year as bene_year,
    birth_dt,
    death_dt,
    sex,
    hi_mons,
    smi_mons,
    {% for f in flags -%}
    (case when {{ f }} = 1 then 1 else 0 end){% if not loop.last %} +{% endif %}
    {% endfor %}as chronic_count
from {{ source('claims_dw', 'bene_year') }}

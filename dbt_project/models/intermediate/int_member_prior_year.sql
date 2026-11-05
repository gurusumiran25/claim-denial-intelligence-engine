-- Chronic condition count from the PREVIOUS calendar year, labelled with the year it can be used in.
-- Claims in 2008 have no prior-year row, so their value is null.
select
    bene_id,
    bene_year + 1 as claim_year,
    chronic_count as chronic_count_prior_year
from {{ ref('stg_bene_year') }}

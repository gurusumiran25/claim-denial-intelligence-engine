{% set span = var('member_history_days') %}
-- Claims by the same member in the days before each service day (current day excluded).
with daily as (
    select bene_id, day_index, count(*) as claims
    from {{ ref('stg_claims') }}
    group by bene_id, day_index
)

select
    bene_id,
    day_index,
    coalesce(sum(claims) over w, 0) as member_claims_prior_90d
from daily
window w as (
    partition by bene_id
    order by day_index
    range between {{ span }} preceding and 1 preceding
)

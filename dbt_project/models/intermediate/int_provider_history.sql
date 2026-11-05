{% set lag = var('feedback_lag_days') %}
{% set span = var('history_days') %}
-- For each provider-day: denial history over the window that ends `feedback_lag_days` before the day
-- (so outcomes that would not yet be known are never used) and a 30-day volume count.
-- The current day is never included.
select
    provider_id,
    day_index,
    coalesce(sum(claims) over history, 0) as provider_prior_claims,
    coalesce(sum(denied) over history, 0) as provider_prior_denied,
    coalesce(sum(claims) over recent, 0) as provider_claims_prior_30d
from {{ ref('int_provider_daily') }}
window
    history as (
        partition by provider_id
        order by day_index
        range between {{ lag + span }} preceding and {{ lag }} preceding
    ),
    recent as (
        partition by provider_id
        order by day_index
        range between 30 preceding and 1 preceding
    )

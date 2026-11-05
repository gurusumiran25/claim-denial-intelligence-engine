-- Claims and denials per provider per day (the building block for provider history).
select
    c.provider_id,
    c.day_index,
    count(*) as claims,
    sum(l.is_denied) as denied
from {{ ref('stg_claims') }} as c
inner join {{ ref('stg_claim_labels') }} as l
    on c.claim_id = l.claim_id
group by c.provider_id, c.day_index

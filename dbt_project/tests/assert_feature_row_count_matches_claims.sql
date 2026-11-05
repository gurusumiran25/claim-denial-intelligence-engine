-- Every claim must appear exactly once in the feature table.
select f.n_features, c.n_claims
from (select count(*) as n_features from {{ ref('fct_claim_features') }}) as f
cross join (select count(*) as n_claims from {{ ref('stg_claims') }}) as c
where f.n_features != c.n_claims

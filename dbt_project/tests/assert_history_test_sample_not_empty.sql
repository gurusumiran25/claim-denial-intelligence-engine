-- Guards the brute-force history tests: they must have claims to check.
select 'no sample claims found' as problem
from (select 1 as one) as t
where (select count(*) from {{ ref('fct_claim_features') }} where right(claim_id, 4) = '7777') = 0

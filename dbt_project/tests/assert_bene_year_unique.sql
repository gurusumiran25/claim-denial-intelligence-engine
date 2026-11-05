-- One row per member per year in the beneficiary table.
select bene_id, year, count(*) as n
from {{ source('claims_dw', 'bene_year') }}
group by bene_id, year
having count(*) > 1

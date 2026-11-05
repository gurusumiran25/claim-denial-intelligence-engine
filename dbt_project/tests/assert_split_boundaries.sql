-- No train row after train_end, no valid row outside its window, no test row before the window.
select claim_id, split, from_dt
from {{ ref('fct_claim_features') }}
where (split = 'train' and from_dt > cast('{{ var("train_end") }}' as date))
    or (split = 'valid' and (from_dt <= cast('{{ var("train_end") }}' as date)
        or from_dt > cast('{{ var("valid_end") }}' as date)))
    or (split = 'test' and from_dt <= cast('{{ var("valid_end") }}' as date))

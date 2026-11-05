{% set forbidden = ['carc_code', 'p_denial_true', 'denial_rule_id'] %}
{% set cols = adapter.get_columns_in_relation(ref('fct_claim_features')) | map(attribute='name') | map('lower') | list %}
{% set bad = [] %}
{% for c in forbidden %}{% if c in cols %}{% do bad.append(c) %}{% endif %}{% endfor %}
-- Fails (returns a row) if any leakage column appears in the feature table.
select '{{ bad | join(",") }}' as forbidden_columns
from (select 1 as one) as t
{% if bad | length == 0 %}where false{% endif %}

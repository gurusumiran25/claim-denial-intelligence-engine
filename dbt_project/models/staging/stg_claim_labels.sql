-- Labels and synthesized submission fields.
-- LEAKAGE GUARD: denial_rule_id and p_denial_true are deliberately NOT selected here.
select
    claim_id,
    days_to_file,
    auth_required,
    auth_on_file,
    is_denied,
    carc_code
from {{ source('claims_dw', 'claim_labels') }}

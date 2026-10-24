# Data Dictionary (DRAFT, verify against the CMS codebook on day 1)

## A. Target claim table (`claims_unified`), one row per claim

| Column | Type | Source | Notes |
|---|---|---|---|
| claim_id | string | all claim files (CLM_ID) | Primary key |
| bene_id | string | DESYNPUF_ID | Member |
| provider_id | string | PRVDR_NUM (inpatient/outpatient), NPI fields (carrier) | Decide which ID to use per claim type |
| claim_type | enum | derived | inpatient, outpatient, carrier |
| from_dt | date | CLM_FROM_DT | Service start |
| thru_dt | date | CLM_THRU_DT | Service end |
| procedure_code | string | HCPCS_CD_1 (primary) | Primary procedure |
| primary_dx | string | ICD9_DGNS_CD_1 | Primary diagnosis |
| amount | float | CLM_PMT_AMT (or line payment sums for carrier) | Paid amount used as dollar proxy |
| days_to_file | int | simulated/derived | Gap from service end to submission (synthesized, see simulator) |
| auth_required | bool | simulated | Whether the service type needs prior auth |
| auth_on_file | bool | simulated | Authorization present at submission |
| coverage_active | bool | derived from beneficiary file | Member covered on service date |

## B. Simulated outputs (added by `simulator/simulate_denials.py`)

| Column | Type | Use |
|---|---|---|
| is_denied | int | **Target** |
| carc_code | string | Denial reason (for root cause and RAG). Not a feature. |
| denial_rule_id | string | LEAKAGE, never a feature |
| p_denial_true | float | LEAKAGE, never a feature |

## C. Columns that must never be model inputs
`is_denied`, `carc_code`, `denial_rule_id`, `p_denial_true`, anything computed after adjudication.

## D. Raw file field reference (to confirm on day 1)
Fill in actual names and counts after downloading:

| File | Rows | Key fields observed | Notes |
|---|---|---|---|
| Inpatient claims | TBD | TBD | |
| Outpatient claims | TBD | TBD | |
| Carrier claims | TBD | TBD | Line-level, needs aggregation to claim level |
| Beneficiary summary | TBD | TBD | Coverage months, demographics |

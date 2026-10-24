# Data Dictionary (v2, verified against real DE-SynPUF Sample 1 headers, 24 Oct 2026)

## A. Raw files (row counts from the inspection script)

| File | Rows | Columns | Grain | Key fields |
|---|---|---|---|---|
| Beneficiary Summary 2008 | 116,352 | 32 | one row per member per year | DESYNPUF_ID |
| Beneficiary Summary 2009 | 114,538 | 32 | same | DESYNPUF_ID |
| Beneficiary Summary 2010 | 112,754 | 32 | same | DESYNPUF_ID |
| Inpatient Claims | 66,773 | 81 | one row per claim (has SEGMENT) | CLM_ID, DESYNPUF_ID, PRVDR_NUM |
| Outpatient Claims | 790,790 | 76 | one row per claim (has SEGMENT) | CLM_ID, DESYNPUF_ID, PRVDR_NUM |
| Carrier Claims 1A | 2,370,667 | 142 | one row per claim, up to 13 service lines in wide columns | CLM_ID, DESYNPUF_ID |
| Carrier Claims 1B | 2,370,668 | 142 | same | CLM_ID, DESYNPUF_ID |

Total claims across the three types: 5,598,898 (to be confirmed by `scripts/profile_claims.py`).
Not downloaded: Prescription Drug Events (out of scope for now).

## B. Format notes (read before writing any code)

- **Dates** are integers like `20090315` (YYYYMMDD). Parse with `pd.to_datetime(s.astype(str), format="%Y%m%d")`.
- **Codes** are ICD-9 (2008 to 2010 era) and HCPCS, not ICD-10.
- **Amounts** are Medicare payment amounts, not billed charges.
- **Carrier files are wide.** There is one row per claim, with service lines stored in numbered columns (`HCPCS_CD_1` to `_13`, `LINE_NCH_PMT_AMT_1` to `_13`, and so on). A claim has no single provider-number column. Use `TAX_NUM_n` and `PRF_PHYSN_NPI_n`.
- **Carrier files are big** (about 1.2 GB each, 142 columns). Always load with `usecols` and `chunksize`.
- **Beneficiary files are yearly snapshots** with coverage months, death date and chronic-condition flags for that year.

## C. Target table `claims_unified` (one row per claim) and source mapping

| Column | Inpatient | Outpatient | Carrier |
|---|---|---|---|
| claim_id | CLM_ID | CLM_ID | CLM_ID |
| claim_type | "inpatient" | "outpatient" | "carrier" |
| bene_id | DESYNPUF_ID | DESYNPUF_ID | DESYNPUF_ID |
| provider_id | PRVDR_NUM | PRVDR_NUM | TAX_NUM_1 (proposed, billing entity) |
| rendering_npi | AT_PHYSN_NPI | AT_PHYSN_NPI | PRF_PHYSN_NPI_1 |
| from_dt | CLM_FROM_DT | CLM_FROM_DT | CLM_FROM_DT |
| thru_dt | CLM_THRU_DT | CLM_THRU_DT | CLM_THRU_DT |
| primary_dx | ICD9_DGNS_CD_1 | ICD9_DGNS_CD_1 | ICD9_DGNS_CD_1 |
| procedure_code | HCPCS_CD_1, else ICD9_PRCDR_CD_1 | HCPCS_CD_1, else ICD9_PRCDR_CD_1 | HCPCS_CD_1 |
| n_lines | count of non-null HCPCS_CD_n | count of non-null HCPCS_CD_n | count of non-null HCPCS_CD_1..13 |
| amount | CLM_PMT_AMT | CLM_PMT_AMT | sum of LINE_NCH_PMT_AMT_1..13 |
| drg_code | CLM_DRG_CD | null | null |
| los_days | CLM_UTLZTN_DAY_CNT | null | null |

Null rates for procedure_code and the inpatient-only fields are unknown until the profile script runs.

## D. Columns derived from the beneficiary files

- `age_at_claim` from BENE_BIRTH_DT and from_dt
- `sex` from BENE_SEX_IDENT_CD
- `coverage_active` (derived, replaces random coverage in the toy data):
  - member must appear in the beneficiary file for the claim's year
  - inpatient claims: BENE_HI_CVRAGE_TOT_MONS > 0
  - outpatient and carrier claims: BENE_SMI_CVRAGE_TOT_MONS > 0
  - BENE_DEATH_DT must be empty or on/after from_dt
- Chronic flags (SP_DIABETES, SP_CHF and so on) are yearly. To avoid using information from later in the year, use the **previous year's** flags when building features.

## E. Synthesized columns (not in the raw data)

| Column | How it is made |
|---|---|
| days_to_file | seeded random distribution, documented in the simulator |
| auth_required | rule based on claim type and amount, plus noise |
| auth_on_file | seeded random, high probability when required |

## F. Simulated outputs (added by `simulator/simulate_denials.py`)

| Column | Use |
|---|---|
| is_denied | **Target** |
| carc_code | Denial reason (root cause and RAG). Not a feature. |
| denial_rule_id | LEAKAGE, never a feature |
| p_denial_true | LEAKAGE, never a feature |

## G. Never use as model features

- `is_denied`, `carc_code`, `denial_rule_id`, `p_denial_true`
- Post-adjudication money fields: `NCH_*` deductible and coinsurance fields, `LINE_BENE_*`, `LINE_COINSRNC_AMT_n`, `LINE_PRCSG_IND_CD_n`, `CLM_PASS_THRU_PER_DIEM_AMT`
- `amount` is allowed as a claim-value feature and for dollar ranking, with the caveat in ADR-007 (it is a payment amount standing in for the billed amount)

## H. Open checks (run `scripts/profile_claims.py`)

1. Is CLM_ID unique inside each file, and across the three claim types?
2. What does SEGMENT mean in practice, and is (CLM_ID, SEGMENT) the true key?
3. Null rates for procedure_code, dates, provider fields
4. Provider cardinality: PRVDR_NUM vs TAX_NUM_1 vs PRF_PHYSN_NPI_1
5. Share of claims whose member appears in the beneficiary file for that year
6. Amount distributions (zeros, extreme values)

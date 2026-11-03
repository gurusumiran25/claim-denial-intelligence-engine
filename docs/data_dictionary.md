# Data Dictionary (v3, profiled on the real DE-SynPUF Sample 1 files, 24 Oct 2026)

## A. Raw files (verified by `scripts/inspect_raw.py` and `scripts/profile_claims.py`)

| File | Rows | Columns | Grain | Key |
|---|---|---|---|---|
| Beneficiary Summary 2008 | 116,352 | 32 | member per year | DESYNPUF_ID |
| Beneficiary Summary 2009 | 114,538 | 32 | member per year | DESYNPUF_ID |
| Beneficiary Summary 2010 | 112,754 | 32 | member per year | DESYNPUF_ID |
| Inpatient Claims | 66,773 | 81 | claim record | (CLM_ID, SEGMENT) |
| Outpatient Claims | 790,790 | 76 | claim record | (CLM_ID, SEGMENT) |
| Carrier Claims 1A + 1B | 2,370,667 + 2,370,668 = 4,741,335 | 142 | one row per claim, up to 13 service lines in wide columns | CLM_ID |

Rows total 5,598,898. Unique CLM_ID values total 5,587,855. The difference of 11,043 rows is the repeated CLM_IDs (68 inpatient and 10,975 outpatient), which are the SEGMENT 2 rows that have a SEGMENT 1 partner. CLM_ID never repeats across claim types.
Not downloaded: Prescription Drug Events (out of scope).

## B. Findings from profiling

- **Inpatient and outpatient SEGMENT 2 rows (confirmed by `scripts/check_segments.py`):** every SEGMENT 2 row (68 inpatient, 11,253 outpatient) has a null `CLM_FROM_DT` and `CLM_THRU_DT`, and every null-date row is a SEGMENT 2 row. They are not copies of the SEGMENT 1 row with the same CLM_ID: the member always matches, but the provider matches in only about 30% of pairs, the diagnosis never matches (inpatient diagnosis is 100% null), and amounts are much larger (inpatient mean 18,790 vs 9,564; outpatient 1,354 vs 268). 278 outpatient SEGMENT 2 rows have no SEGMENT 1 partner. SEGMENT 1 rows are unique by CLM_ID (66,705 inpatient, 779,537 outpatient). Decision: drop SEGMENT 2 rows (ADR-008).
- **Carrier:** no duplicate CLM_ID, no SEGMENT column. 58% of claims have a single service line, the mean is 1.87 lines, and 0.7% (32,253) have no line codes at all.
- **Dates:** inpatient and outpatient claims start as early as Nov and Dec 2007. Beneficiary files only cover 2008 to 2010. Carrier dates run 2008-01-01 to 2010-12-31.
- **Amounts:**
  - Negative values exist (min -8,000 inpatient, -100 outpatient). Zero shares are 3.2% inpatient, 3.8% outpatient and 10.1% carrier.
  - Values look rounded (multiples of 10 up to 1,000).
  - The maximum equals the 99th percentile for inpatient (57,000) and outpatient (3,300), so facility amounts look capped. Carrier is not capped (max 6,080).
- **Procedure fields:** inpatient `HCPCS_CD_1` is 100% null and `ICD9_PRCDR_CD_1` is 42.7% null (`CLM_DRG_CD` is complete). Outpatient `ICD9_PRCDR_CD_1` is 100% null and `HCPCS_CD_1` is 18.3% null.
- **Provider counts:** 2,675 PRVDR_NUM (inpatient), 6,294 PRVDR_NUM (outpatient), 232,675 TAX_NUM_1 and 614,977 PRF_PHYSN_NPI_1 (carrier). TAX_NUM_1 gives about 20 claims per provider on average, NPI about 8.

## C. Format notes

- Dates are integers like `20090315`. Parse with `pd.to_datetime(s.astype(str), format="%Y%m%d")`.
- Codes are ICD-9 and HCPCS (2008 to 2010 era).
- Amounts are Medicare payment amounts, not billed charges.
- Carrier files are about 1.2 GB each with 142 columns. Always load with `usecols` and `chunksize`.

## D. Target table `claims_unified` (one row per claim) and source mapping

| Column | Inpatient | Outpatient | Carrier |
|---|---|---|---|
| claim_id | CLM_ID (SEGMENT 1 rows only) | CLM_ID (SEGMENT 1 rows only) | CLM_ID |
| claim_type | "inpatient" | "outpatient" | "carrier" |
| bene_id | DESYNPUF_ID | DESYNPUF_ID | DESYNPUF_ID |
| provider_id | "F:" + PRVDR_NUM | "F:" + PRVDR_NUM | "T:" + TAX_NUM_1 |
| rendering_npi | AT_PHYSN_NPI | AT_PHYSN_NPI | PRF_PHYSN_NPI_1 |
| from_dt | CLM_FROM_DT | CLM_FROM_DT | CLM_FROM_DT |
| thru_dt | CLM_THRU_DT | CLM_THRU_DT | CLM_THRU_DT |
| primary_dx | ICD9_DGNS_CD_1 | ICD9_DGNS_CD_1 | ICD9_DGNS_CD_1 |
| procedure_code | ICD9_PRCDR_CD_1, else "UNKNOWN" | HCPCS_CD_1, else "UNKNOWN" | HCPCS_CD_1, else "UNKNOWN" |
| drg_code | CLM_DRG_CD | null | null |
| los_days | CLM_UTLZTN_DAY_CNT | null | null |
| n_lines | 1 | count of non-null HCPCS_CD_n | count of non-null HCPCS_CD_1..13 |
| amount | CLM_PMT_AMT | CLM_PMT_AMT | sum of LINE_NCH_PMT_AMT_1..13 |

The "F:" and "T:" prefixes keep facility and billing-entity IDs from colliding.

## E. Derived from the beneficiary files

- `age_at_claim` from BENE_BIRTH_DT and from_dt; `sex` from BENE_SEX_IDENT_CD
- `coverage_active`: member appears in the beneficiary file for the claim year; inpatient needs BENE_HI_CVRAGE_TOT_MONS > 0; outpatient and carrier need BENE_SMI_CVRAGE_TOT_MONS > 0; BENE_DEATH_DT is empty or on/after from_dt
- Chronic flags (SP_*) are yearly. Use the **previous year's** flags to avoid using information from later in the claim year.

## F. Synthesized columns (not in the raw data)

| Column | How it is made |
|---|---|
| days_to_file | seeded random distribution, documented in the simulator |
| auth_required | rule based on claim type and amount, plus noise |
| auth_on_file | seeded random, high probability when required |

## G. Simulated outputs (`simulator/simulate_denials.py`)

| Column | Use |
|---|---|
| is_denied | **Target** |
| carc_code | Denial reason (root cause and RAG). Not a feature. |
| denial_rule_id | LEAKAGE, never a feature |
| p_denial_true | LEAKAGE, never a feature |

## H. Never use as model features

- `is_denied`, `carc_code`, `denial_rule_id`, `p_denial_true`
- Post-adjudication money fields: `NCH_*` deductible and coinsurance fields, `LINE_BENE_*`, `LINE_COINSRNC_AMT_n`, `LINE_PRCSG_IND_CD_n`, `CLM_PASS_THRU_PER_DIEM_AMT`
- `amount` may be used as a claim-value feature and for dollar ranking, with the caveat in ADR-007

## I. Open checks

1. ~~What SEGMENT 2 rows are~~ resolved: null-date records, dropped (ADR-008)
2. Share of claims whose member appears in the beneficiary file for that year
3. How many claims each filter in ADR-008 removes (log in Week 2)
4. Whether the duplicate-claim rule needs primary_dx and amount in its key (many procedure codes are "UNKNOWN")

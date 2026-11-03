# Decision Log

Format: ID, date, decision, why, alternatives considered. Add one entry for every non-trivial choice. These make great interview answers.

## ADR-001: Denial labels are simulated
- **Date:** 2026-10-24
- **Decision:** Generate the denial label from versioned rules in `simulator/denial_rules.yaml` using a logistic model (rule effects + provider effect + noise).
- **Why:** Public claims data has no real adjudication outcome. A transparent simulator is honest and reproducible.
- **Safeguards:** hidden (non-observable) rules and noise so the model cannot trivially reverse the YAML; `p_denial_true` and `denial_rule_id` are leakage columns and are never model inputs; README states labels are simulated.
- **Alternatives:** use a different public dataset with real denials (none found that is both open and claim-level); skip the label problem (not credible).

## ADR-002: Claim-level grain, one row per claim
- **Date:** 2026-10-24
- **Decision:** Unified table with one row per claim across inpatient, outpatient and carrier claim types.
- **Why:** The decision to review or fix happens per claim; keeps features and ranking simple.
- **Note:** DE-SynPUF amounts are payment amounts, not billed charges. We use `amount` (paid/allowed proxy) for expected-loss ranking and say so in the README.

## ADR-003: Time-based validation
- **Date:** 2026-10-24
- **Decision:** Train on earlier months, validate and test on later months. No random shuffle.
- **Why:** Mirrors production and avoids leaking future provider history into the past.

## ADR-004: LightGBM as the main model
- **Date:** 2026-10-24
- **Decision:** Gradient boosted trees on tabular features, with logistic regression as an interpretable baseline.
- **Why:** Strong on mixed tabular data, handles missing values and categories well, fast to iterate, works with SHAP. Deep learning adds cost without clear benefit here.

## ADR-005: Metrics that match the business
- **Date:** 2026-10-24
- **Decision:** Primary metrics are PR-AUC, recall at top-k and dollars protected at top-k, with ROC-AUC and calibration as secondary.
- **Why:** Denials are imbalanced, and the reviewer has limited capacity. Accuracy would be misleading.

## ADR-002 correction (24 Oct 2026)
- Earlier note said carrier claims are line level. The real files show one row per claim with up to 13 service lines stored in wide columns, so no row aggregation is needed. See ADR-007.

## ADR-006: Dataset mix, DE-SynPUF Sample 1 only (ACCEPTED)
- **Date:** 2026-10-24
- **Decision:** Use DE-SynPUF Sample 1 only: 3 beneficiary files plus inpatient, outpatient and both carrier files. Defer Synthea.
- **Why:** The profile shows 5.6 million claim records, which is already large. Beneficiary files supply real coverage and demographics. Synthea would add setup time (Java, generation, mapping) for little value now.
- **Revisit:** Week 3, if we need payer or authorization-style fields that DE-SynPUF lacks. Prescription Drug Events are out of scope.
- **Alternatives:** DE-SynPUF plus Synthea (more realism, more work); Synthea only (smaller, less credible).

## ADR-007: Claim grain, IDs and amount (ACCEPTED, updated after profiling)
- **Date:** 2026-10-24
- **Decision:**
  - One row per claim record across the three claim types (`claims_unified`).
  - `claim_id` = CLM_ID. It is unique once SEGMENT 2 rows are dropped (ADR-008). An earlier draft used CLM_ID + SEGMENT.
  - `provider_id` = "F:" + PRVDR_NUM for inpatient and outpatient, "T:" + TAX_NUM_1 for carrier. `rendering_npi` is kept separately.
  - `amount` = CLM_PMT_AMT for facility claims, sum of LINE_NCH_PMT_AMT_1..13 for carrier.
  - `procedure_code`: inpatient ICD9_PRCDR_CD_1, outpatient and carrier HCPCS_CD_1, else "UNKNOWN". Inpatient also keeps `drg_code`.
- **Why:** Denials and reviews happen per claim. Carrier has no facility number, and the tax number has far more claims per provider than the physician NPI (about 20 vs 8), which helps provider-history features. Procedure fields differ by file (inpatient HCPCS is 100% null, outpatient ICD-9 procedure is 100% null).
- **Caveats:** Amounts are payment amounts, not billed charges. They look rounded, and facility amounts look capped (max equals the 99th percentile). We state this in the README limitations. Post-adjudication money fields are excluded from features.

## ADR-008: Modeling population (ACCEPTED, confirmed by `check_segments.py`)
- **Date:** 2026-10-24
- **Decision:** Build the modeling table from claims that pass all of these:
  1. `SEGMENT` = 1 for inpatient and outpatient (drops 68 + 11,253 rows)
  2. `from_dt` is not null and falls between 2008-01-01 and 2010-12-31 (drops the 2007 starts)
  3. `amount` > 0 (drops negative and zero payments)
- **Evidence:** All SEGMENT 2 rows have null dates, and every null-date row is SEGMENT 2. They are not copies of the SEGMENT 1 row: the provider matches in only about 30% of pairs, the diagnosis never matches, and the amounts are about 2 to 5 times larger. Adding their amounts to SEGMENT 1 would mix different providers and services, so we drop them. Without a date they also cannot be time-split, coverage-checked or given a days-to-file value.
- **Expected population before filters 2 and 3:** 66,705 inpatient + 779,537 outpatient + 4,741,335 carrier = 5,587,577 claims. Log the exact count removed by each filter in Week 2.
- **Alternatives:** merge SEGMENT 2 amounts into SEGMENT 1 (rejected, see evidence); keep zero and negative amounts as their own class (adds noise).

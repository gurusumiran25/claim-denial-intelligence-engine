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

## ADR-006: Dataset mix, DE-SynPUF Sample 1 only (PROPOSED)
- **Date:** 2026-10-24
- **Decision:** Use DE-SynPUF Sample 1 only: 3 beneficiary files plus inpatient, outpatient and both carrier files. Defer Synthea.
- **Why:** About 5.6 million claims, which is already large. Beneficiary files supply real coverage and demographics. Synthea would add setup time (Java, generation, mapping) for little extra value in Week 1.
- **Revisit:** Week 3, if we need payer or authorization-style fields that DE-SynPUF lacks. Prescription Drug Events are out of scope.
- **Alternatives:** DE-SynPUF plus Synthea (more realism, more work); Synthea only (smaller, less credible).

## ADR-007: Claim grain, provider ID and amount (PROPOSED)
- **Date:** 2026-10-24
- **Decision:**
  - One row per claim across the three claim types (`claims_unified`).
  - `provider_id` = PRVDR_NUM for inpatient and outpatient, TAX_NUM_1 for carrier (billing entity); `rendering_npi` kept separately.
  - `amount` = CLM_PMT_AMT for facility claims, sum of LINE_NCH_PMT_AMT_1..13 for carrier.
  - `procedure_code` = HCPCS_CD_1, falling back to ICD9_PRCDR_CD_1 for facility claims.
- **Why:** Denials and reviews happen per claim. Carrier files have no facility number, and the tax number is the closest billing-entity identifier.
- **Caveat:** DE-SynPUF has paid amounts only, not billed charges. We treat `amount` as a proxy for claim value and say so in the README. Post-adjudication money fields are excluded from features.
- **To confirm:** provider cardinality and null rates from `scripts/profile_claims.py` before locking this in.

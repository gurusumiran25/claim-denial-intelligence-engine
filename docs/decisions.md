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

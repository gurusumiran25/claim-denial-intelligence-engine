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
- **Result of the first full build (24 Oct 2026):** 5,598,898 raw rows became 5,072,824 claims (inpatient 64,276; outpatient 746,779; carrier 4,261,769). Removed: 11,321 SEGMENT 2 rows, 536 claims starting before 2008, 2,616 negative amounts and 511,601 zero amounts (479,566 of them carrier). No bad dates, no missing amounts, no duplicate claim IDs. Every claim's member was found in that year's beneficiary file, and `coverage_active` is False for 0.8% of kept claims.

## ADR-009: Synthesized submission fields and label calibration (PROPOSED)
- **Date:** 2026-10-24
- **Decision:**
  - `days_to_file`: lognormal, median 18 days, sigma 0.9, capped at 365 (about 3.7% of claims above 90 days).
  - `auth_required`: inpatient 90%; other claims when the amount is above their claim-type 90th percentile, plus 3% at random.
  - `auth_on_file`: always true when not required; 85% when required.
  - The simulator's `base_logit` is calibrated so the overall denial rate hits a target (default 10%), instead of a hand-picked constant.
  - Labels live in a separate table `claim_labels` keyed by `claim_id` and are joined to features later (BigQuery and dbt in Weeks 2 and 3).
  - The duplicate-claim rule matches on member, provider, date, procedure, primary diagnosis and amount, because many procedure codes are "UNKNOWN".
- **Why:** The raw data has no filing lag or authorization information, so these fields must be synthesized, seeded and documented. A fixed target rate keeps experiments comparable. A separate label table keeps leakage columns away from the features by construction.
- **Limits to state in the README:** the denial label, filing lag and authorization status are all simulated, so absolute model scores say how well patterns are recovered, not how a real payer behaves.
- **Review item:** CO-16 (hidden missing-information rule plus baseline noise) may dominate denial reasons. Check its share in the label report and rebalance if it is above about 40%.

### ADR-009 update: denial rules v0.2 (24 Oct 2026)
- **Why:** The first real label run (rules v0.1) gave CO-16 as 50.6% of denials and CO-18 (duplicates) as 0%. Half the denials came from baseline randomness, and the duplicate rule never fired because the real data has no exact repeats.
- **Changes:**
  - Two observable rules added: `missing_procedure_code` (CO-4, outpatient and carrier only, effect 1.7) and `many_service_lines` (CO-97, 6 or more lines, effect 1.3).
  - Hidden `missing_information` rate lowered from 5% to 3%.
  - Observable rule effects scaled up by about 1.3 so more of the denial pattern can be learned from features.
  - Duplicate key is now member, provider, date, procedure and primary diagnosis (amount removed), and claims with an UNKNOWN procedure are never flagged.
- **Estimate on a frame with the real marginals (before the real rerun):** CO-16 falls from about 50% to about 34%, and the oracle ROC-AUC (an upper bound for any model) is about 0.84.
- **Open item:** the duplicate rule may still fire rarely. Check its count in the new label report. If it is near zero, either inject a small share of simulated resubmissions or drop the rule and its reason code.

### ADR-009 result (24 Oct 2026): rules v0.2 on the real table
- CO-16 share fell to 30.3% (from 50.6%) and the oracle ROC-AUC is 0.850. Overall denial rate 9.99%; outpatient 14.5%, inpatient 13.8%, carrier 9.1%.
- The duplicate rule fires on only 5 of 5,072,824 claims (CO-18 share 0.0%) because DE-SynPUF has no exact repeat claims. Decision: leave the rule in place, exclude CO-18 from the reason analysis, and say so in the README. Simulated resubmissions are a possible later addition.

## ADR-011: Time-based split (PROPOSED, 2026-11-03)
- **Decision:** Train on service dates in 2008 and 2009 (3,844,106 claims), validate on Jan to Jun 2010 (807,486), test on Jul to Dec 2010 (421,232). No random shuffling. Provider history and other history features use only earlier dates.
- **Why:** This mirrors deployment, where the model scores future claims. The EDA shows volume and denial rate shifting over time (about 10.5% in 2008, 9.7% in 2009, 9.5% in 2010, with volume falling through 2010), so the late-2010 test set is a harder and more honest check.
- **Risk:** The test period is smaller and has a different mix. Report metrics by claim type and by month.

## ADR-012: Leakage-safe feature design in dbt (2026-11-05)
- **Decision:** Features in `fct_claim_features` use only information available before the service date. Provider denial history covers a 90-day window that ends 30 days before the claim (the feedback lag), is smoothed toward a fixed 10% prior with the weight of 50 claims, and falls back to the prior when there is no history. Member history excludes the current day. Chronic condition counts come from the previous year. `claim_year` is kept as a time column but is not a feature. `carc_code` and the simulator's hidden columns never enter the feature table.
- **Why:** Denial outcomes arrive after submission, so a provider's yesterday is not known today. The EDA showed provider rates are noisy at small volumes, so shrinkage is needed.
- **Checks:** 48 dbt tests, including brute-force recomputation of the history windows on a sample of claims and a guard against label columns in the feature table.
- **Limits:** 2008 claims have no prior-year chronic counts, and the first 120 days of 2008 have no provider history.

# Project Log: Claim Denial Intelligence Engine

Running record of what was built, what was found, what was decided and what went wrong. It is the single source for the final documentation pack. Updated at every milestone.

- **Owner:** M Guru Sumiran
- **Repo:** github.com/gurusumiran25/claim-denial-intelligence-engine
- **Started:** 24 Oct 2026
- **Last updated:** 3 Nov 2026
- **Overall progress:** about 33% (weighted by effort)

## 1. Status

| Phase | Status |
|---|---|
| Week 1: repo, CI, data download and profiling, data dictionary, dataset and grain decisions | Done (Synthea deferred, ADR-006) |
| Week 2: modeling table, simulated labels, BigQuery load, EDA | Done: 10 EDA queries run, findings written |
| Week 3: dbt feature layer (leakage-safe features) | Next |
| Week 4: baselines, LightGBM, calibration, SHAP, ROI | Not started |
| Week 5: RAG appeal copilot, root-cause analysis | Not started |
| Week 6: API, Streamlit app, Docker, deploy, packaging | Not started |
| Week 7: buffer, launch, interview prep | Not started |

## 2. Timeline

| Date | What happened |
|---|---|
| 24 Oct 2026 | Plan written. Repo created and scaffold pushed. CI green. DE-SynPUF Sample 1 downloaded (7 files) after the first carrier download attempts failed in Chrome. |
| 24 Oct to 3 Nov | Raw files profiled. `SEGMENT` 2 rows investigated. Data dictionary v3. ADR-001 to ADR-008. `claims_unified` built. Denial simulator v0.1, then v0.2. |
| 3 Nov 2026 | Full build and label run on real data. BigQuery sandbox project and dataset `claims_dw` created. Three tables loaded and verified. 10 EDA queries run on BigQuery. |

## 3. Key numbers

**Raw data (DE-SynPUF Sample 1)**
- Beneficiary files: 116,352 (2008), 114,538 (2009), 112,754 (2010) rows
- Inpatient 66,773 rows, outpatient 790,790 rows, carrier 4,741,335 rows (two files)
- Total claim rows 5,598,898; unique CLM_ID 5,587,855; no CLM_ID overlap across claim types

**Modeling table `claims_unified` (ADR-008)**
- Removed: 11,321 SEGMENT 2 rows, 536 claims starting before 2008, 2,616 negative amounts, 511,601 zero amounts
- Kept: 5,072,824 claims (inpatient 64,276; outpatient 746,779; carrier 4,261,769)
- `coverage_active` false for 0.8% (40,084); every member found in that year's beneficiary file

**Labels (rules v0.2, calibrated to a 10% target)**
- Overall denial rate 9.99%; carrier 9.14%, inpatient 13.78%, outpatient 14.51%
- Reasons: CO-16 30.3%, CO-29 24.0%, CO-197 12.6%, CO-11 8.3%, CO-4 8.3%, CO-27 6.1%, CO-50 5.9%, CO-97 4.7%, CO-18 about 0
- Dollars denied: 17.8% of $1,259.0M ($224.2M)
- Oracle ROC-AUC 0.850; oracle top-10% precision 0.566, recall 0.567 (upper bound for any model)

**Warehouse**
- BigQuery dataset `claims_dw` (US, sandbox): `claims_unified`, `claim_labels`, `bene_year`
- Verified: join returns 5,072,824 rows; denial rates match the label report

**Code quality:** 21 automated tests pass; CI runs ruff and pytest on every push.

## 4. Findings so far

### 4.1 Data findings
1. Carrier claims are one row per claim with up to 13 service lines in wide columns; no row aggregation needed (corrected an earlier assumption, ADR-002 correction).
2. `SEGMENT` 2 rows (68 inpatient, 11,253 outpatient) all have null dates, differ from the matching `SEGMENT` 1 row in provider and diagnosis, and have much larger amounts. They are dropped, not merged (ADR-008).
3. Facility claims start as early as Nov 2007, but beneficiary files cover only 2008 to 2010; 536 claims fell outside the window.
4. Amounts: negatives (reversals), 3% to 10% zeros, rounded values, and facility maximums equal to the 99th percentile (looks capped).
5. Procedure fields differ by file: inpatient HCPCS is 100% null (ICD-9 procedure 42.7% null, DRG complete); outpatient ICD-9 procedure is 100% null (HCPCS 18.3% null).
6. Carrier has no facility ID; `TAX_NUM_1` gives about 20 claims per provider on average versus about 8 for the physician NPI.
7. Codes are ICD-9 and HCPCS; dates are integers (YYYYMMDD).
8. Claim volume drops sharply in the second half of 2010.

### 4.2 Labeling findings
1. Rules v0.1 left CO-16 at 50.6% of denials (baseline noise) and the duplicate rule never fired.
2. v0.2 added two observable rules from real data patterns (missing procedure code, 6+ service lines), strengthened observable effects by about 30%, tightened the duplicate key, and calibrated `base_logit` to a target rate. CO-16 fell to 30.3%; oracle ROC-AUC is 0.850.
3. The duplicate rule still fires on only 5 claims; left in place and excluded from analysis (ADR-009 result).

### 4.3 EDA findings (Week 2)
See `docs/eda_findings.md` (9 findings). Headlines:
- Outpatient loses the most dollars (28.7% of its dollars denied).
- Three reasons explain 66.8% of denied claims; by dollars CO-197 (35.4%) and CO-50 (18.0%) rank higher.
- Late filing is a cliff at 90 days (66.7% vs about 7.8%); missing authorization gives 66.3% vs 8.1%.
- Risk is concentrated in the top amount decile and in claims with 6+ lines.
- Provider rates vary (p10 5.9% to p90 15.5%), but sampling noise needs smoothing.
- Claims with inactive coverage are denied 76.6% of the time.

## 5. Decisions index

| ADR | Decision | Status |
|---|---|---|
| 001 | Denial labels are simulated | Accepted |
| 002 | Claim-level grain (carrier correction added) | Accepted |
| 003 | Time-based validation | Accepted |
| 004 | LightGBM as main model, logistic regression baseline | Accepted |
| 005 | Business metrics: PR-AUC, recall and dollars at top-k | Accepted |
| 006 | DE-SynPUF Sample 1 only; Synthea deferred | Accepted |
| 007 | One row per claim; ID, provider and amount rules | Accepted |
| 008 | Modeling population filters | Accepted |
| 009 | Synthesized submission fields; calibrated labels; rules v0.2 and result | Accepted |
| 010 | Load cleaned tables into BigQuery, not raw CSVs | Accepted |
| 011 | Time split: train 2008 to 2009, validate H1 2010, test H2 2010 | Proposed |

## 6. Problems hit and how they were fixed (lessons)

| Problem | Fix | Lesson |
|---|---|---|
| Virtual environment was created in the outer folder and every new terminal opened without it | Activate with `..\.venv\Scripts\activate`; open VS Code on the inner project folder | Check the prompt for `(.venv)` and the folder name before running anything |
| `ModuleNotFoundError: pandas` | The venv was not active | Same as above |
| Carrier files failed to download in Chrome | Retried one at a time | Large downloads fail silently; verify file sizes |
| An early assumption that carrier files needed line-to-claim aggregation | Profiling showed one row per claim in wide format | Profile before designing; log corrections in the decision log |
| Label rules v0.1: CO-16 at 50.6%, duplicate rule dead | Added observable rules, calibrated base rate, reported oracle ceiling | Report the achievable ceiling and trigger counts after every simulation change |
| `gcloud` not found in terminals opened before install; commands typed into the init prompt | Restart VS Code; run commands only at a normal prompt | New installs reach only new windows |
| Parquet nanosecond timestamps risk loading badly into BigQuery | Export script converts to DATE | Match types to the warehouse |
| BigQuery sandbox: tables expire after 60 days; no DML or streaming | Reload with `bq load --replace` if needed | Check platform limits before designing |

## 7. Open items, risks and assumptions

- **Realistic expectations:** the oracle ceiling is 0.85 ROC-AUC. A real model on observable features will score lower (my guess: high 0.7s to low 0.8s); to be measured in Week 4.
- **Simulated pipeline:** all label-driven results must be presented as pattern recovery, not payer behavior (ADR-001).
- **Time drift:** denial rate and volume change by year; confirm cause with a mix-by-month query.
- **Provider feature:** needs smoothing and a fallback for providers with no history.
- **BigQuery expiry:** tables created 3 Nov 2026 expire after 60 days; the project is due earlier, but keep the `bq load` commands handy.
- **Not yet done:** dbt, model, RAG, API, app, deployment, demo video, final README.

## 8. Metrics tracker (fill in as results arrive)

| Metric | Baseline (logistic) | LightGBM | Notes |
|---|---|---|---|
| ROC-AUC (test, H2 2010) | | | oracle ceiling 0.850 |
| PR-AUC (test) | | | |
| Recall at top 10% | | | oracle 0.567 |
| Precision at top 10% | | | oracle 0.566 |
| Dollars protected at top 10% | | | |
| Calibration (Brier / curve) | | | |

| RAG metric | Value |
|---|---|
| Retrieval hit rate | |
| Groundedness rate | |
| Hallucinated policy cases | |

## 9. Interview talking points so far

- **Why simulate labels?** Public claims data has no adjudication outcome. A versioned, seeded, calibrated simulator is transparent and reproducible, and I report the ceiling so scores are interpretable.
- **How did you keep it honest?** Hidden rules, provider effects and noise inside the simulator; leakage columns (`p_denial_true`, `denial_rule_id`) separated into the label table; README states the labels are simulated.
- **What did the data teach you?** SEGMENT 2 rows, wide carrier format, capped amounts, and zero-paid claims; each led to a logged decision.
- **How did you iterate?** Rules v0.1 produced a dominant generic reason and a dead rule; I measured it, fixed it, and added a ceiling metric.
- **Why a warehouse?** Features and marts are built in SQL (BigQuery, dbt) and joined to labels by `claim_id`; the sandbox limits shaped what to load.
- **Why a leakage-safe provider feature?** Rolling history windows that exclude the current day, smoothed for small samples.

## 10. Final documentation pack (delivered at the end of the project)

1. Final README (problem, architecture diagram, results, limitations, how to run)
2. Architecture and data lineage document
3. Data dictionary (final) and decision log (final)
4. EDA findings and feature documentation
5. Model card and evaluation report (baseline vs LightGBM, calibration, SHAP, ROI)
6. RAG evaluation report
7. Runbook (setup, load, train, serve, deploy)
8. Demo script and 3-minute video outline
9. Resume bullets, LinkedIn post, interview Q&A (2, 5 and 10 minute versions)
10. Lessons learned

## 11. How this log is maintained

At each milestone the log gets an appended block (a short entry for the findings, numbers and decisions of that step). Everything in the repo's `docs/` folder is the source of truth.

## Update 8 Nov 2026: Weeks 3 and 4
- **Week 3 (dbt):** the feature table `fct_claim_features` is built in BigQuery with 21 leakage-safe features; split counts match ADR-011 exactly. Bugs fixed on the way: numeric accepted-values tests needed `quote: false` on BigQuery, and one claim with a null provider is mapped to UNKNOWN.
- **Week 4 (model):** LightGBM beats logistic regression and the constant baselines, reaches about 89% of the oracle's PR-AUC and 94% of its recall at 10%, is stable from validation to test, and is well calibrated. Expected-loss ranking catches 90% of denied dollars in the top 10% (74% by probability). See `docs/model_card.md` and `reports/model_report.md`.
- **Lessons:** isotonic calibration created ties and lowered PR-AUC, so Platt scaling is used. MLflow was skipped in favor of `reports/run_log.csv` to avoid dependency conflicts with dbt.
- **Progress:** about 55%. Next: Week 5 (root-cause analysis and the RAG appeal copilot).

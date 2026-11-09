# Model Card: Claim Denial Risk Model

**Version:** 1.1 (9 Nov 2026) | **Owner:** M Guru Sumiran | **Code:** `src/training/`, results in `reports/`

## 1. Summary
A LightGBM classifier that scores each healthcare claim for the probability of denial before submission. Claims are ranked by expected dollar loss (probability x claim amount), and each score is explained with TreeSHAP. It is the core of the Claim Denial Intelligence Engine.

**Important:** the denial labels are simulated (ADR-001, ADR-009). The model shows how well realistic denial patterns can be recovered from claim features. It says nothing about how a real payer behaves.

## 2. Intended use
- **Intended:** prioritizing which claims a reviewer should check before submission, and explaining why a claim looks risky.
- **Not intended:** automatic denial or approval of care, anything affecting patients, or use on real payer data without re-validation.

## 3. Data
- Claims: CMS DE-SynPUF Sample 1 (public, synthetic Medicare claims), 5,072,824 claims after cleaning (ADR-007, ADR-008).
- Labels: simulated from versioned rules v0.2 plus provider effects and noise, calibrated to a 10% denial rate (ADR-009).
- Synthesized fields: filing lag and authorization status (ADR-009). Coverage comes from the real beneficiary files.
- Time split (ADR-011): train 2008 to 2009 (3,844,106 claims), validation Jan to Jun 2010 (807,486), test Jul to Dec 2010 (421,232). Denial rate: 10.16% train, 9.56% test.

## 4. Features (19)
Claim: claim type, amount, log amount, service lines, unknown-procedure flag, length of stay, month. Member: age, sex, coverage active, chronic conditions in the previous year, member claims in the prior 90 days. Submission: days to file, authorization required, authorization on file. Provider history (90-day window ending 30 days before the claim, smoothed toward 10%): prior claims, prior denials, claims in the last 30 days, smoothed denial rate.
The diagnosis group and DRG code were tested and removed (see section 6). Leakage controls (ADR-012): history features use only earlier dates, reason codes and simulator internals never enter the feature table, and dbt tests check the windows against a brute-force recomputation.

## 5. Training
LightGBM (63 leaves, learning rate 0.05, early stopping on validation logloss, 185 trees). Same data and seed give identical results. A Platt-scaling step was fitted on validation, but it did not improve calibration (section 6), so the serving code uses the raw LightGBM probabilities.

## 6. Performance (test period, Jul to Dec 2010)

| Model | ROC-AUC | PR-AUC | Recall at top 10% | Lift at 10% | Brier |
|---|---|---|---|---|---|
| Base rate only | 0.500 | 0.096 | 0.103 | 1.0 | 0.0865 |
| Claim-type rate | 0.539 | 0.105 | 0.147 | 1.5 | 0.0861 |
| Logistic regression | 0.759 | 0.418 | 0.494 | 4.9 | 0.0690 |
| **LightGBM (19 features)** | **0.783** | **0.497** | **0.521** | **5.2** | **0.0626** |
| Oracle (true probability) | 0.842 | 0.557 | 0.555 | 5.6 | 0.0592 |

- LightGBM beats logistic regression by 0.024 ROC-AUC and 0.079 PR-AUC, and reaches about 89% of the oracle's PR-AUC and 94% of its recall at 10%. The oracle sees hidden rules and noise that no feature carries, so it is an upper bound.
- Stable over time: validation ROC-AUC 0.7866, test 0.7828.
- Calibration: expected calibration error 0.0014 raw and 0.0016 after Platt scaling. The raw probabilities are already well calibrated.
- Ablation: with the diagnosis group and DRG included (21 features), test ROC-AUC was 0.7819 and PR-AUC 0.4960. Removing them was no worse and simpler (ADR-013). This applies to the simulated labels, which do not depend on diagnosis; real data may differ.

## 7. Subgroups (test)

| Claim type | Claims | Denial rate | ROC-AUC | PR-AUC | Recall at 10% |
|---|---|---|---|---|---|
| Carrier | 357,801 | 8.8% | 0.767 | 0.471 | 0.518 |
| Outpatient | 59,107 | 14.0% | 0.822 | 0.572 | 0.440 |
| Inpatient | 4,324 | 13.5% | 0.830 | 0.536 | 0.443 |

Inpatient has few test claims, so its numbers are noisy.

## 8. Explainability
Top features by mean absolute SHAP value (log-odds): days to file (0.255), service lines (0.174), authorization on file (0.130), unknown procedure (0.103), amount (0.086), provider smoothed denial rate (0.072), claim type (0.053), coverage active (0.047). These match the simulator's rules, which is the expected result for a model that recovers the pattern. Coverage ranks lower on average because it is rare (0.8% of claims), even though its effect on those claims is very large.

## 9. Business view (test period; assumptions: $10 review cost per claim, 50% of caught denials fixed)

| Reviewed share | Denied dollars caught, ranked by probability | Ranked by expected loss | Net benefit, probability | Net benefit, expected loss |
|---|---|---|---|---|
| 1% | 17% | 57% | $1.36M | $4.74M |
| 5% | 47% | 82% | $3.73M | $6.71M |
| 10% | 72% | 90% | $5.64M | $7.20M |
| 20% | 86% | 94% | $6.38M | $7.13M |

Ranking by expected loss beats ranking by probability at every capacity. Net benefit peaks near a 10% review share under these assumptions, because extra reviews cost more than they recover.
The review cost and fix rate are placeholders. The advantage of expected-loss ranking is also helped by the simulator's amount-driven rules and by rounded, capped facility amounts.

## 10. Limitations
- Labels, filing lag and authorization are simulated, so absolute scores do not transfer to a real payer.
- Test covers only the second half of 2010, when claim volume is lower.
- 2008 claims have no prior-year chronic counts and no provider history in their first 120 days.
- Amounts are Medicare payment amounts, rounded, and facility amounts look capped.
- The duplicate-claim reason (CO-18) is not usable because the data has no exact repeats.
- No demographic fairness analysis beyond claim type: the data is synthetic and carries few member attributes.

## 11. Monitoring plan (if deployed)
Track the denial rate and score distribution by week, the share of claims with no provider history, and calibration by month. Retrain when calibration error exceeds 0.01, PR-AUC drops by more than 0.03 on a recent labeled window, or the feature distributions (days to file, amount, claim mix) shift materially.

## 12. Reproduce
```
python -m src.training.export_features
python -m src.training.train --drop "dx_group,drg_code"
```
Outputs: `reports/model_report.md`, tables, `reports/figures/`, and model files in `models/` (not committed).

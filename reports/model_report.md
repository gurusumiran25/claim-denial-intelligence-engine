# Model report

Generated 2026-11-09T12:37:04 (commit 89f4865). Labels are simulated (ADR-001), so scores show how well patterns are recovered, not how a real payer behaves.

## Data split (ADR-011)
- train 3,844,106 claims, valid 807,486, test 421,232
- training denial rate 0.1016; test denial rate 0.0956

## Model comparison
| model | split | roc_auc | pr_auc | recall_at_10 | precision_at_10 | lift_at_10 | brier | log_loss |
|---|---|---|---|---|---|---|---|---|
| base rate only | valid | 0.5000 | 0.0940 | 0.1009 | 0.0948 | 1.0085 | 0.0852 | 0.3119 |
| claim-type rate | valid | 0.5389 | 0.1039 | 0.1507 | 0.1416 | 1.5067 | 0.0848 | 0.3100 |
| logistic regression | valid | 0.7623 | 0.4202 | 0.4969 | 0.4669 | 4.9691 | 0.0676 | 0.2502 |
| LightGBM | valid | 0.7866 | 0.4978 | 0.5275 | 0.4957 | 5.2751 | 0.0615 | 0.2305 |
| LightGBM calibrated | valid | 0.7866 | 0.4978 | 0.5275 | 0.4957 | 5.2751 | 0.0615 | 0.2305 |
| oracle (true probability) | valid | 0.8427 | 0.5543 | 0.5600 | 0.5262 | 5.5996 | 0.0583 | 0.2155 |
| base rate only | test | 0.5000 | 0.0956 | 0.1029 | 0.0983 | 1.0288 | 0.0865 | 0.3154 |
| claim-type rate | test | 0.5387 | 0.1054 | 0.1472 | 0.1406 | 1.4715 | 0.0861 | 0.3136 |
| logistic regression | test | 0.7588 | 0.4175 | 0.4936 | 0.4717 | 4.9356 | 0.0690 | 0.2544 |
| LightGBM | test | 0.7828 | 0.4967 | 0.5206 | 0.4976 | 5.2061 | 0.0626 | 0.2341 |
| LightGBM calibrated | test | 0.7828 | 0.4967 | 0.5206 | 0.4976 | 5.2061 | 0.0626 | 0.2342 |
| oracle (true probability) | test | 0.8416 | 0.5565 | 0.5552 | 0.5306 | 5.5518 | 0.0592 | 0.2184 |

## Review queue on the test period (assumptions: review cost $10.00 per claim, 50% of caught denials fixed)
| review_share | claims_reviewed | precision_by_probability | recall_by_probability | recall_by_expected_loss | dollars_share_by_probability | net_benefit_by_probability | dollars_share_by_expected_loss | net_benefit_by_expected_loss | dollars_share_random |
|---|---|---|---|---|---|---|---|---|---|
| 0.0100 | 4213.0000 | 0.8770 | 0.0918 | 0.0573 | 0.1658 | 1358265.0000 | 0.5664 | 4740640.0000 | 0.0100 |
| 0.0500 | 21062.0000 | 0.6921 | 0.3621 | 0.2289 | 0.4662 | 3725880.0000 | 0.8200 | 6713620.0000 | 0.0500 |
| 0.1000 | 42124.0000 | 0.4976 | 0.5206 | 0.3914 | 0.7173 | 5635430.0000 | 0.9022 | 7197130.0000 | 0.1000 |
| 0.2000 | 84247.0000 | 0.3081 | 0.6448 | 0.5845 | 0.8554 | 6380430.0000 | 0.9442 | 7129845.0000 | 0.2000 |

## Calibration (test)
- expected calibration error: raw 0.0014, Platt 0.0016

## By claim type (test, calibrated LightGBM)
| claim_type | claims | denial_rate | roc_auc | pr_auc | recall_at_10 |
|---|---|---|---|---|---|
| carrier | 357801 | 0.0877 | 0.7673 | 0.4711 | 0.5179 |
| inpatient | 4324 | 0.1346 | 0.8297 | 0.5361 | 0.4433 |
| outpatient | 59107 | 0.1403 | 0.8216 | 0.5715 | 0.4397 |

## Top features by mean |SHAP|
| feature | mean_abs_shap |
|---|---|
| days_to_file | 0.2548 |
| n_lines | 0.1738 |
| auth_on_file | 0.1299 |
| procedure_unknown | 0.1030 |
| amount | 0.0862 |
| provider_denial_rate_smoothed | 0.0718 |
| claim_type | 0.0534 |
| coverage_active | 0.0471 |
| auth_required | 0.0278 |
| amount_log | 0.0222 |
| provider_prior_denied | 0.0145 |
| provider_prior_claims | 0.0110 |

Figures are in `reports/figures/`.

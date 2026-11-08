# Model report

Generated 2026-11-08T12:44:35 (commit a3cdb1a). Labels are simulated (ADR-001), so scores show how well patterns are recovered, not how a real payer behaves.

## Data split (ADR-011)
- train 3,844,106 claims, valid 807,486, test 421,232
- training denial rate 0.1016; test denial rate 0.0956

## Model comparison
| model | split | roc_auc | pr_auc | recall_at_10 | precision_at_10 | lift_at_10 | brier | log_loss |
|---|---|---|---|---|---|---|---|---|
| base rate only | valid | 0.5000 | 0.0940 | 0.1009 | 0.0948 | 1.0085 | 0.0852 | 0.3119 |
| claim-type rate | valid | 0.5389 | 0.1039 | 0.1507 | 0.1416 | 1.5067 | 0.0848 | 0.3100 |
| logistic regression | valid | 0.7623 | 0.4202 | 0.4969 | 0.4669 | 4.9691 | 0.0676 | 0.2502 |
| LightGBM | valid | 0.7855 | 0.4964 | 0.5271 | 0.4953 | 5.2710 | 0.0616 | 0.2307 |
| LightGBM calibrated | valid | 0.7855 | 0.4964 | 0.5271 | 0.4953 | 5.2710 | 0.0616 | 0.2307 |
| oracle (true probability) | valid | 0.8427 | 0.5543 | 0.5600 | 0.5262 | 5.5996 | 0.0583 | 0.2155 |
| base rate only | test | 0.5000 | 0.0956 | 0.1029 | 0.0983 | 1.0288 | 0.0865 | 0.3154 |
| claim-type rate | test | 0.5387 | 0.1054 | 0.1472 | 0.1406 | 1.4715 | 0.0861 | 0.3136 |
| logistic regression | test | 0.7588 | 0.4175 | 0.4936 | 0.4717 | 4.9356 | 0.0690 | 0.2544 |
| LightGBM | test | 0.7819 | 0.4960 | 0.5203 | 0.4972 | 5.2026 | 0.0627 | 0.2343 |
| LightGBM calibrated | test | 0.7819 | 0.4960 | 0.5203 | 0.4972 | 5.2026 | 0.0627 | 0.2343 |
| oracle (true probability) | test | 0.8416 | 0.5565 | 0.5552 | 0.5306 | 5.5518 | 0.0592 | 0.2184 |

## Review queue on the test period (assumptions: review cost $10.00 per claim, 50% of caught denials fixed)
| review_share | claims_reviewed | precision_by_probability | recall_by_probability | recall_by_expected_loss | dollars_share_by_probability | net_benefit_by_probability | dollars_share_by_expected_loss | net_benefit_by_expected_loss | dollars_share_random |
|---|---|---|---|---|---|---|---|---|---|
| 0.0100 | 4213.0000 | 0.8778 | 0.0919 | 0.0567 | 0.1644 | 1346320.0000 | 0.5682 | 4755475.0000 | 0.0100 |
| 0.0500 | 21062.0000 | 0.6904 | 0.3612 | 0.2287 | 0.4663 | 3727135.0000 | 0.8197 | 6711080.0000 | 0.0500 |
| 0.1000 | 42124.0000 | 0.4972 | 0.5203 | 0.3907 | 0.7391 | 5819345.0000 | 0.9023 | 7197665.0000 | 0.1000 |
| 0.2000 | 84247.0000 | 0.3076 | 0.6438 | 0.5832 | 0.8622 | 6437485.0000 | 0.9440 | 7128705.0000 | 0.2000 |

## Calibration (test)
- expected calibration error: raw 0.0022, Platt 0.0020

## By claim type (test, calibrated LightGBM)
| claim_type | claims | denial_rate | roc_auc | pr_auc | recall_at_10 |
|---|---|---|---|---|---|
| carrier | 357801 | 0.0877 | 0.7661 | 0.4705 | 0.5184 |
| inpatient | 4324 | 0.1346 | 0.8303 | 0.5296 | 0.4313 |
| outpatient | 59107 | 0.1403 | 0.8213 | 0.5709 | 0.4401 |

## Top features by mean |SHAP|
| feature | mean_abs_shap |
|---|---|
| days_to_file | 0.2543 |
| n_lines | 0.1740 |
| auth_on_file | 0.1300 |
| procedure_unknown | 0.1044 |
| amount | 0.0892 |
| provider_denial_rate_smoothed | 0.0766 |
| claim_type | 0.0474 |
| coverage_active | 0.0469 |
| dx_group | 0.0357 |
| auth_required | 0.0330 |
| amount_log | 0.0148 |
| provider_claims_prior_30d | 0.0095 |

Figures are in `reports/figures/`.

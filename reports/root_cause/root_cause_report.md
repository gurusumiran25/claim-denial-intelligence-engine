# Root-cause analysis of denied claims

Reasons come from the simulator (ADR-001, ADR-009), so this shows what the pipeline can surface, not how a real payer behaves. CO-16 also absorbs the simulator's unexplained baseline denials.

- Denied claims: 506,661; denied dollars: $224,200,920
- Top 3 reasons by claim count: CO-16 (30.3%), CO-29 (24.0%), CO-197 (12.6%)
- Top 3 reasons by dollars: CO-197 (35.4%), CO-50 (18.0%), CO-29 (15.2%)
- Recommended route by denied dollars: appeal 70.2%, corrected claim 26.3%, no appeal 3.5%

## Denial reasons ranked by dollars
| carc_code | denied_claims | denied_dollars | claims_share | dollars_share | cum_dollars_share | rank_by_claims |
|---|---|---|---|---|---|---|
| CO-197 | 63856 | 79,313,200.0000 | 0.1260 | 0.3538 | 0.3538 | 3 |
| CO-50 | 29731 | 40,429,950.0000 | 0.0587 | 0.1803 | 0.5341 | 7 |
| CO-29 | 121485 | 34,031,680.0000 | 0.2398 | 0.1518 | 0.6859 | 2 |
| CO-16 | 153267 | 29,144,690.0000 | 0.3025 | 0.1300 | 0.8159 | 1 |
| CO-4 | 41855 | 17,969,180.0000 | 0.0826 | 0.0801 | 0.8960 | 5 |
| CO-11 | 42020 | 11,924,430.0000 | 0.0829 | 0.0532 | 0.9492 | 4 |
| CO-27 | 30721 | 7,822,470.0000 | 0.0606 | 0.0349 | 0.9841 | 6 |
| CO-97 | 23721 | 3,561,770.0000 | 0.0468 | 0.0159 | 1.0000 | 8 |
| CO-18 | 5 | 3,550.0000 | 0.0000 | 0.0000 | 1.0000 | 9 |

## Root-cause categories and owners
| root_cause | owner | fixability | denied_claims | denied_dollars | dollars_share |
|---|---|---|---|---|---|
| Authorization not obtained | Front desk and scheduling | preventable | 63856 | 79,313,200.0000 | 0.3538 |
| Documentation does not support necessity | Clinical documentation | correctable | 29731 | 40,429,950.0000 | 0.1803 |
| Late submission | Billing office | preventable | 121485 | 34,031,680.0000 | 0.1518 |
| Missing or invalid claim data | Registration and billing | preventable | 153267 | 29,144,690.0000 | 0.1300 |
| Coding error | Coding team | preventable | 41855 | 17,969,180.0000 | 0.0801 |
| Coding error | Coding team | correctable | 42020 | 11,924,430.0000 | 0.0532 |
| Eligibility not verified | Registration | preventable | 30721 | 7,822,470.0000 | 0.0349 |
| Coding and bundling | Coding team | correctable | 23721 | 3,561,770.0000 | 0.0159 |
| Duplicate submission | Billing office | preventable | 5 | 3,550.0000 | 0.0000 |

## Provider concentration
- Providers with at least one denial: 101,623
- Top 1% of providers hold 57.1% of denied dollars, top 5% hold 80.6%, top 10% hold 86.7%

## Top providers by denied dollars
| provider_id | denied_claims | denied_dollars | claims | denial_rate |
|---|---|---|---|---|
| T:532092265 | 12320 | 1,902,130.0000 | 82143 | 0.1500 |
| F:23006G | 187 | 1,402,220.0000 | 1056 | 0.1771 |
| F:1000AH | 279 | 1,069,760.0000 | 2301 | 0.1213 |
| T:294540272 | 5436 | 941,710.0000 | 62790 | 0.0866 |
| F:1700JJ | 785 | 902,860.0000 | 3709 | 0.2116 |
| F:3600NG | 302 | 889,180.0000 | 2217 | 0.1362 |
| F:0502NA | 1590 | 848,860.0000 | 9366 | 0.1698 |
| F:3100JN | 331 | 831,450.0000 | 2256 | 0.1467 |
| F:1100TC | 322 | 703,080.0000 | 2261 | 0.1424 |
| F:2600ZT | 130 | 696,950.0000 | 784 | 0.1658 |

## Prevention actions by reason
| carc_code | reason | owner | fixability | prevention |
|---|---|---|---|---|
| CO-197 | Prior authorization missing | Front desk and scheduling | preventable | Check authorization requirements at scheduling; Block claim release when a required authorization is missing |
| CO-50 | Medical necessity | Clinical documentation | correctable | Make sure notes state the clinical indication; Send the supporting record when the claim is high value |
| CO-29 | Timely filing | Billing office | preventable | Track days from service to submission and alert at 30 and 60 days; Work rejected claims within 5 days so resubmission stays inside the limit |
| CO-16 | Claim lacks required information | Registration and billing | preventable | Add required-field checks to the claim scrubber; Validate identifiers at registration |
| CO-4 | Procedure code problem | Coding team | preventable | Require a procedure code on every outpatient and professional line; Check modifier rules in the scrubber |
| CO-11 | Diagnosis inconsistent with procedure | Coding team | correctable | Add diagnosis-to-procedure checks to the scrubber; Coder review of high-volume codes |
| CO-27 | Coverage ended or inactive | Registration | preventable | Verify eligibility on the day of service; Re-verify before billing for long stays |
| CO-97 | Bundled service | Coding team | correctable | Run NCCI edits in the claim scrubber before submission; Review modifier use on multi-line claims |
| CO-18 | Duplicate claim | Billing office | preventable | Check claim status before resubmitting; Use the clearinghouse duplicate check |

Figures are in `reports/root_cause/figures/`.

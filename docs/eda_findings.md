# EDA Findings (Week 2)

Source: the 10 queries in `sql/eda/`, run on BigQuery (`claims_dw`) on 3 Nov 2026. Raw outputs are in `docs/eda_results/` and `docs/eda_results_all.txt`.

Important: the denial labels, filing lag and authorization fields are simulated (ADR-001, ADR-009). Findings about them describe the simulator and what a model can recover, not how a real payer behaves. Findings about amounts, claim types, service lines, providers and coverage start from real DE-SynPUF fields.

## Finding 1: Outpatient claims lose the largest share of their dollars
- **Query:** 01_overview_by_type
- **What I saw:** Overall denial rate is 9.99%, but by claim type it is 9.14% (carrier), 13.78% (inpatient) and 14.51% (outpatient). In dollars, 17.8% of all payment dollars sit on denied claims ($224.2M of $1,259.0M). Outpatient is the worst at 28.7% of its dollars, against 15.7% (carrier) and 15.6% (inpatient).
- **So what for modeling:** Claim count and claim dollars tell different stories. The expected-loss ranking (probability x amount) is the right target for a review queue, and model results should be reported by claim type.

## Finding 2: Three reasons explain two thirds of denials, but dollars rank them differently
- **Query:** 03_reason_pareto
- **What I saw:** CO-16 (30.3%), CO-29 late filing (24.0%) and CO-197 missing authorization (12.6%) make up 66.8% of denied claims. By dollars the order changes: CO-197 is 35.4% of denied dollars, CO-50 high-amount review is 18.0% (from only 5.9% of claims), CO-29 is 15.2% and CO-16 is 13.0%. CO-18 (duplicates) has 5 claims.
- **So what for modeling:** The root-cause view (Week 5) should show both counts and dollars. Authorization problems are the biggest money lever. The duplicate rule is effectively dead because DE-SynPUF has no exact repeat claims.

## Finding 3: Late filing is a cliff, not a slope
- **Query:** 04_days_to_file
- **What I saw:** Denial rate is flat at about 7.8% for claims filed within 90 days (0 to 30, 31 to 60, 61 to 90) and jumps to 66.7% for the 184,368 claims filed after 90 days.
- **So what for modeling:** This is the simulator's timely-filing threshold, so tree models will find it easily. In a real payer the effect would be smoother, so I should not present this as a discovered business pattern.

## Finding 4: Missing authorization multiplies denial risk about eight times
- **Query:** 05_authorization
- **What I saw:** Claims that need no authorization are denied 8.1% of the time. Claims that need one and have none on file are denied 66.3% (103,047 claims). Claims that need one and have it are denied 14.0%.
- **So what for modeling:** `auth_required` and `auth_on_file` are strong observable features (synthesized, ADR-009). The 14.0% vs 8.1% gap for claims with authorization on file reflects inpatient claims carrying other risks.

## Finding 5: Risk is concentrated in the top amount decile
- **Query:** 06_amount_deciles
- **What I saw:** Within each claim type, denial rates are flat for most of the amount range, then jump in the top decile: carrier 22.7% (amounts 200 to 6,080) against 7.4% to 7.9% below; outpatient 33.8% (700 to 3,300) against 10.5% to 15.5%; inpatient 18.4% (19,000 to 57,000) against about 12% to 14%. Amounts are rounded and floored (carrier decile 1 is all $10), and facility amounts look capped at 57,000 and 3,300.
- **So what for modeling:** Use amount relative to claim type (percentile within type), not raw amount. State the rounding and capping in the README limitations.

## Finding 6: Providers differ, but part of the spread is noise
- **Query:** 07_provider_variation
- **What I saw:** Among 7,311 providers with at least 100 claims, the mean denial rate is 10.3%, the median 9.7%, p10 5.9%, p90 15.5%, p99 21.8% and the maximum 33.6%.
- **So what for modeling:** A provider's history should help. At 100 claims the sampling error alone is about 3 percentage points, so the provider rate must be smoothed (shrunk toward the overall rate) in Week 3, and computed only from earlier dates.

## Finding 7: Coverage problems and long claims are strong risk flags
- **Query:** 08_coverage, 09_service_lines
- **What I saw:** Claims where `coverage_active` is false (40,084, 0.8%) are denied 76.6% of the time, against 9.5% for covered claims. Claims with 6 or more service lines are denied 24.2% (carrier) and 29.8% (outpatient), against 8.0% to 10.2% for claims with 1 to 5 lines.
- **So what for modeling:** `coverage_active` comes from the real beneficiary files, which makes it the most defensible feature. Include `n_lines` and its buckets.

## Finding 8: Volume and denial rate drift over time
- **Query:** 02_monthly_trend
- **What I saw:** Monthly claims rise from 69,518 (Jan 2008) to about 170,000 and stay there through 2009, then fall steadily in 2010 to 41,674 (Dec 2010). By year there are 1,832,034 claims in 2008, 2,012,072 in 2009 and 1,228,718 in 2010. Denial rate drifts from about 10.5% (2008) to 9.7% (2009) and 9.5% (2010).
- **So what for modeling:** The simulator has no time effect, so the drift most likely comes from changes in claim mix over time (to be confirmed with a mix-by-month query). Proposed time split (ADR-011): train on 2008 and 2009 (3,844,106 claims), validate on Jan to Jun 2010 (807,486), test on Jul to Dec 2010 (421,232).

## Finding 9: The leakage-safe provider feature works as designed
- **Query:** 10_provider_rolling_preview
- **What I saw:** For the busiest provider (a carrier tax ID), the 90-day prior-window rate is NULL on day one, then settles near 6.6% to 7.1% within about six weeks. The window excludes the current day, so it uses history only.
- **So what for modeling:** NULLs for new providers need a fallback (the overall rate). The window query is the prototype for the dbt feature in Week 3.

## Data caveats to put in the README
- Labels, filing lag and authorization status are simulated; absolute model scores say how well patterns are recovered, not how a real payer behaves.
- Amounts are Medicare payment amounts, rounded, floored, and facility amounts look capped.
- 511,601 zero-paid and 2,616 negative-paid claims were excluded (ADR-008).
- Claim volume drops sharply in the second half of 2010.
- DE-SynPUF has no exact duplicate claims, so the duplicate denial reason is not usable.

## Questions to follow up
- Does claim mix by month explain the drift in denial rate? (query to add)
- How much of the provider spread survives after smoothing?
- Which features does a model find that the rules did not explicitly encode (provider history, dx combinations)?

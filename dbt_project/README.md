# dbt project: claim_denial

Builds the model-ready feature layer on BigQuery from the three loaded tables (`claims_dw.claims_unified`, `claims_dw.claim_labels`, `claims_dw.bene_year`). Output dataset: `claims_analytics`.

## Layers

| Layer | Models | Purpose |
|---|---|---|
| staging (views) | `stg_claims`, `stg_claim_labels`, `stg_bene_year` | Clean column set, calendar fields, `day_index`. Leakage columns (`denial_rule_id`, `p_denial_true`) are never selected. |
| intermediate (tables) | `int_provider_daily`, `int_provider_history`, `int_member_history`, `int_member_prior_year` | Rolling history windows and prior-year member attributes. |
| marts (tables) | `fct_claim_features`, `fct_denied_claims` | `fct_claim_features`: one row per claim with 21 features, the target and the time split. `fct_denied_claims`: denied claims with reason codes for root-cause analysis. |

## Leakage rules (ADR-012)

- History features use only earlier service dates. The current day is never included.
- Provider denial history uses a window that ends 30 days before the claim (`feedback_lag_days`), because a denial outcome is not known right after submission. Window length is 90 days (`history_days`).
- The provider rate is shrunk toward a fixed prior (`prior_denial_rate` = 0.10, `smoothing_strength` = 50 virtual claims). A provider with no history gets the prior.
- Member chronic-condition counts come from the previous calendar year; 2008 claims are null.
- `claim_year` is kept as a time column but is not a feature.
- `carc_code` appears only in `fct_denied_claims`.

## Feature columns (21)

claim_type, amount, amount_log, n_lines, procedure_unknown, dx_group, drg_code, los_days, claim_month, age_at_claim, sex, coverage_active, chronic_count_prior_year, member_claims_prior_90d, days_to_file, auth_required, auth_on_file, provider_prior_claims, provider_prior_denied, provider_claims_prior_30d, provider_denial_rate_smoothed.

Other columns: ids and time (`claim_id`, `bene_id`, `provider_id`, `from_dt`, `claim_year`, `day_index`), `split`, and the target `is_denied`.

## Time split (ADR-011)

train: service date up to 2009-12-31; valid: 2010-01-01 to 2010-06-30; test: after 2010-06-30.

## Tests (48)

- Generic: unique, not_null, accepted_values and relationships on keys, the split, the target and the source tables.
- Singular (in `tests/`):
  - every claim appears once in the feature table
  - no label columns in the feature table
  - provider and member history match a brute-force recomputation on a sample of claims
  - the sample is not empty
  - smoothed rate between 0 and 1
  - split boundaries respected
  - one row per member per year in `bene_year`

## How to run

```
dbt debug
dbt build            # models and tests
dbt docs generate
dbt docs serve       # lineage graph at http://localhost:8080
```

Setup: copy `profiles.yml.example` to `~/.dbt/profiles.yml`, set your project ID, and run `gcloud auth application-default login`. Create the dataset once: `bq mk --dataset --location=US claims_analytics`.

## Known limits

- First 120 days of 2008 have no provider history (30-day lag plus 90-day window), so those claims use the prior rate.
- Chronic condition counts are null for 2008 claims.
- One claim in the real data has no provider; staging maps it to `UNKNOWN` (the source check warns).
- Flag coding (1 = condition present) follows the CMS codebook and is checked only for values 1 and 2.
- BigQuery sandbox: tables expire after 60 days; rerun `dbt build` to recreate them.

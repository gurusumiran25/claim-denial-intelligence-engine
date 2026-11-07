"""Feature lists and preparation for the denial model.

The feature table comes from dbt (`fct_claim_features`). Columns are split into ids and time
(never features), the target, and 21 features. High-cardinality categories are capped using the
training period only, so validation and test never influence the category list.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET = "is_denied"
ID_COLS = ["claim_id", "bene_id", "provider_id", "from_dt", "claim_year", "day_index", "split"]
CATEGORICAL = ["claim_type", "dx_group", "drg_code", "sex"]
NUMERIC = [
    "amount",
    "amount_log",
    "n_lines",
    "procedure_unknown",
    "los_days",
    "claim_month",
    "age_at_claim",
    "coverage_active",
    "chronic_count_prior_year",
    "member_claims_prior_90d",
    "days_to_file",
    "auth_required",
    "auth_on_file",
    "provider_prior_claims",
    "provider_prior_denied",
    "provider_claims_prior_30d",
    "provider_denial_rate_smoothed",
]
FEATURES = CATEGORICAL + NUMERIC
MAX_LEVELS = 300
MIN_COUNT = 100
LEVEL_OTHER = "OTHER"
LEVEL_MISSING = "MISSING"


def fit_categories(train: pd.DataFrame) -> dict[str, list[str]]:
    """Category levels per column, from the training rows only."""
    spec: dict[str, list[str]] = {}
    for col in CATEGORICAL:
        counts = train[col].dropna().astype(str).value_counts()
        counts = counts[counts >= MIN_COUNT].head(MAX_LEVELS)
        spec[col] = [str(v) for v in counts.index]
    return spec


def prepare(
    df: pd.DataFrame, spec: dict[str, list[str]]
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Return the feature frame, the target and the claim amount."""
    X = pd.DataFrame(index=df.index)
    for col in CATEGORICAL:
        levels = spec[col]
        vals = df[col].astype("string").fillna(LEVEL_MISSING)
        vals = vals.where(vals.isin(levels + [LEVEL_MISSING]), LEVEL_OTHER)
        X[col] = pd.Categorical(
            vals.astype(object), categories=levels + [LEVEL_OTHER, LEVEL_MISSING]
        )
    for col in NUMERIC:
        X[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")
    y = df[TARGET].to_numpy(dtype="int8")
    amount = pd.to_numeric(df["amount"], errors="coerce").to_numpy(dtype="float64")
    return X, y, amount

"""TreeSHAP contributions from a trained LightGBM model (log-odds scale).

LightGBM computes exact TreeSHAP values with predict(pred_contrib=True), so no extra library
is needed. The API and the appeal copilot reuse these functions to name the top drivers of a
claim's risk.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def shap_contributions(model, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return (contributions [n, n_features], bias [n])."""
    contrib = model.booster_.predict(X, pred_contrib=True)
    return contrib[:, :-1], contrib[:, -1]


def top_drivers(model, X: pd.DataFrame, k: int = 5) -> list[list[dict]]:
    """For each row, the k features with the largest absolute contribution."""
    contrib, _ = shap_contributions(model, X)
    names = list(X.columns)
    out: list[list[dict]] = []
    for i in range(len(X)):
        order = np.argsort(-np.abs(contrib[i]))[:k]
        out.append(
            [
                {
                    "feature": names[j],
                    "value": None if pd.isna(X.iloc[i, j]) else str(X.iloc[i, j]),
                    "shap": float(contrib[i, j]),
                }
                for j in order
            ]
        )
    return out

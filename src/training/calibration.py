"""Probability calibration that keeps the ranking intact.

Platt scaling fits a logistic curve on the model's log-odds, so the mapping is strictly increasing:
no ties are created and the review-queue ranking is unchanged. (Isotonic regression was tried first
and lowered PR-AUC because it collapses scores into plateaus.)
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p)).reshape(-1, 1)


class PlattCalibrator:
    def __init__(self) -> None:
        self._lr = LogisticRegression(C=1e6, max_iter=200)

    def fit(self, raw: np.ndarray, y: np.ndarray) -> PlattCalibrator:
        self._lr.fit(_logit(raw), y)
        return self

    def predict(self, raw: np.ndarray) -> np.ndarray:
        return self._lr.predict_proba(_logit(raw))[:, 1]

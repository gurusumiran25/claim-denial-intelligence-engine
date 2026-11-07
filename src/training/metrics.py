"""Ranking, calibration and business metrics for the denial model."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

REVIEW_FRACTIONS = (0.01, 0.05, 0.10, 0.20)


def top_k_index(score: np.ndarray, frac: float) -> np.ndarray:
    n = len(score)
    k = max(1, int(np.ceil(frac * n)))
    if k >= n:
        return np.arange(n)
    return np.argpartition(-score, k - 1)[:k]


def recall_at_k(y: np.ndarray, score: np.ndarray, frac: float) -> float:
    idx = top_k_index(score, frac)
    return float(y[idx].sum() / max(int(y.sum()), 1))


def precision_at_k(y: np.ndarray, score: np.ndarray, frac: float) -> float:
    return float(y[top_k_index(score, frac)].mean())


def dollars_captured(
    y: np.ndarray, amount: np.ndarray, rank_score: np.ndarray, frac: float
) -> float:
    idx = top_k_index(rank_score, frac)
    return float((amount[idx] * y[idx]).sum())


def net_benefit(captured: float, n_reviewed: int, fix_rate: float, review_cost: float) -> float:
    """Dollars saved by fixing a share of caught denials, minus the cost of reviewing."""
    return fix_rate * captured - review_cost * n_reviewed


def basic_metrics(y: np.ndarray, p: np.ndarray, frac: float = 0.10) -> dict[str, float]:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    base = float(y.mean())
    prec = precision_at_k(y, p, frac)
    return {
        "roc_auc": float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan"),
        "pr_auc": float(average_precision_score(y, p)),
        "recall_at_10": recall_at_k(y, p, frac),
        "precision_at_10": prec,
        "lift_at_10": prec / base if base > 0 else float("nan"),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p)),
    }


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> tuple[pd.DataFrame, float]:
    """Quantile-binned reliability table and the expected calibration error."""
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False)
    tab = df.groupby("bin").agg(n=("y", "size"), mean_pred=("p", "mean"), observed=("y", "mean"))
    ece = float((tab["n"] / tab["n"].sum() * (tab["mean_pred"] - tab["observed"]).abs()).sum())
    return tab.reset_index(), ece


def topk_table(
    y: np.ndarray,
    amount: np.ndarray,
    p: np.ndarray,
    fractions: tuple[float, ...] = REVIEW_FRACTIONS,
    fix_rate: float = 0.5,
    review_cost: float = 10.0,
) -> pd.DataFrame:
    """Review-queue results for ranking by probability and by expected loss (p x amount)."""
    total_denied_dollars = float((amount * y).sum())
    expected_loss = p * amount
    rows = []
    for frac in fractions:
        n_reviewed = len(top_k_index(p, frac))
        row = {
            "review_share": frac,
            "claims_reviewed": n_reviewed,
            "precision_by_probability": precision_at_k(y, p, frac),
            "recall_by_probability": recall_at_k(y, p, frac),
            "recall_by_expected_loss": recall_at_k(y, expected_loss, frac),
        }
        for name, rank in (("probability", p), ("expected_loss", expected_loss)):
            captured = dollars_captured(y, amount, rank, frac)
            row[f"dollars_share_by_{name}"] = captured / total_denied_dollars
            row[f"net_benefit_by_{name}"] = net_benefit(captured, n_reviewed, fix_rate, review_cost)
        row["dollars_share_random"] = frac
        rows.append(row)
    return pd.DataFrame(rows)


def cumulative_gain_curve(
    y: np.ndarray, amount: np.ndarray, rank_score: np.ndarray, points: int = 100
) -> tuple[np.ndarray, np.ndarray]:
    """Share of denied dollars captured as more of the ranked queue is reviewed."""
    order = np.argsort(-rank_score, kind="mergesort")
    cum = np.cumsum((amount * y)[order])
    total = cum[-1] if len(cum) and cum[-1] > 0 else 1.0
    xs = np.linspace(0.0, 1.0, points + 1)
    idx = np.clip((xs * len(order)).astype(int) - 1, 0, len(order) - 1)
    ys = np.where(xs == 0, 0.0, cum[idx] / total)
    return xs, ys

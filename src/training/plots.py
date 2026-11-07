"""Figures for the model report. Saved as PNG files."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402

DPI = 110


def _save(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)


def roc_pr(y: np.ndarray, scores: dict[str, np.ndarray], path: Path) -> None:
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4))
    for name, p in scores.items():
        fpr, tpr, _ = roc_curve(y, p)
        a.plot(fpr, tpr, label=name)
        prec, rec, _ = precision_recall_curve(y, p)
        b.plot(rec, prec, label=name)
    a.plot([0, 1], [0, 1], "k--", lw=0.8)
    a.set(xlabel="False positive rate", ylabel="True positive rate", title="ROC (test)")
    b.axhline(y.mean(), color="k", ls="--", lw=0.8)
    b.set(xlabel="Recall", ylabel="Precision", title="Precision-recall (test)")
    a.legend()
    _save(fig, path)


def calibration(tables: dict[str, pd.DataFrame], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4.5))
    top = max(float(t["observed"].max()) for t in tables.values())
    ax.plot([0, top], [0, top], "k--", lw=0.8, label="perfect")
    for name, t in tables.items():
        ax.plot(t["mean_pred"], t["observed"], marker="o", label=name)
    ax.set(
        xlabel="Mean predicted probability",
        ylabel="Observed denial rate",
        title="Calibration (test)",
    )
    ax.legend()
    _save(fig, path)


def gains(curves: dict[str, tuple[np.ndarray, np.ndarray]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    for name, (xs, ys) in curves.items():
        ax.plot(xs, ys, label=name)
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, label="random")
    ax.set(
        xlabel="Share of claims reviewed",
        ylabel="Share of denied dollars caught",
        title="Cumulative dollar gains (test)",
    )
    ax.legend()
    _save(fig, path)


def shap_bar(importance: pd.Series, path: Path, top: int = 15) -> None:
    s = importance.sort_values(ascending=False).head(top)[::-1]
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.barh(s.index, s.values)
    ax.set(xlabel="Mean |SHAP value| (log-odds)", title="Global feature importance")
    _save(fig, path)


def shap_summary(
    contrib: np.ndarray, X: pd.DataFrame, path: Path, top: int = 12, seed: int = 0
) -> None:
    rng = np.random.default_rng(seed)
    names = list(X.columns)
    order = np.argsort(-np.abs(contrib).mean(axis=0))[:top][::-1]
    fig, ax = plt.subplots(figsize=(7, 6))
    for row, j in enumerate(order):
        vals = X.iloc[:, j]
        if pd.api.types.is_numeric_dtype(vals):
            color = vals.rank(pct=True).fillna(0.5).to_numpy()
            ax.scatter(
                contrib[:, j],
                row + rng.normal(0, 0.08, len(vals)),
                c=color,
                cmap="coolwarm",
                s=4,
                vmin=0,
                vmax=1,
            )
        else:
            ax.scatter(contrib[:, j], row + rng.normal(0, 0.08, len(vals)), c="gray", s=4)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([names[j] for j in order])
    ax.axvline(0, color="k", lw=0.6)
    ax.set(xlabel="SHAP value (log-odds)", title="Feature effects (red = high value, blue = low)")
    _save(fig, path)

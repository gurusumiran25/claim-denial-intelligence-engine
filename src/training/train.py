"""Train and evaluate the denial model: baselines, LightGBM, calibration, SHAP and review-queue ROI.

Run from the project root with the venv active:
    python -m src.training.export_features
    python -m src.training.train

Time split (ADR-011): train = 2008 to 2009, valid = Jan to Jun 2010, test = Jul to Dec 2010.
Early stopping uses the validation rows; calibration is fitted on validation; the test rows are only
used for the final numbers.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.explain.drivers import shap_contributions, top_drivers
from src.training import plots
from src.training.calibration import PlattCalibrator
from src.training.features import FEATURES, ID_COLS, NUMERIC, TARGET, fit_categories, prepare
from src.training.metrics import (
    REVIEW_FRACTIONS,
    basic_metrics,
    calibration_table,
    cumulative_gain_curve,
    topk_table,
)

warnings.filterwarnings("ignore", message="The argument 'eval_set'")

FEATURES_DEFAULT = Path("data/processed/features.parquet")
LABELS_DEFAULT = Path("data/processed/claim_labels.parquet")
LR_CATEGORICAL = ["claim_type", "sex"]


def md_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def lr_pipeline(seed: int) -> Pipeline:
    numeric = [c for c in NUMERIC]
    pre = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            ("cat", OneHotEncoder(handle_unknown="ignore"), LR_CATEGORICAL),
        ]
    )
    return Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=300, random_state=seed))])


def lr_frame(X: pd.DataFrame) -> pd.DataFrame:
    out = X[NUMERIC + LR_CATEGORICAL].copy()
    for c in LR_CATEGORICAL:
        out[c] = out[c].astype(str)
    return out


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return "unknown"


def load_oracle(labels_path: Path, claim_ids: pd.Series) -> np.ndarray | None:
    if not labels_path.exists():
        return None
    lab = pq.read_table(labels_path, columns=["claim_id", "p_denial_true"]).to_pandas()
    merged = pd.DataFrame({"claim_id": claim_ids.to_numpy()}).merge(lab, on="claim_id", how="left")
    if merged["p_denial_true"].isna().any():
        return None
    return merged["p_denial_true"].to_numpy()


def by_group(df: pd.DataFrame, y: np.ndarray, p: np.ndarray, col: str) -> pd.DataFrame:
    rows = []
    for key, idx in df.groupby(col, observed=True).indices.items():
        yy, pp = y[idx], p[idx]
        if len(idx) < 50 or yy.sum() == 0 or yy.sum() == len(yy):
            continue
        m = basic_metrics(yy, pp)
        rows.append(
            {
                col: str(key),
                "claims": len(idx),
                "denial_rate": float(yy.mean()),
                "roc_auc": m["roc_auc"],
                "pr_auc": m["pr_auc"],
                "recall_at_10": m["recall_at_10"],
            }
        )
    return pd.DataFrame(rows)


def run(
    features_path: Path,
    reports_dir: Path,
    models_dir: Path,
    labels_path: Path = LABELS_DEFAULT,
    lr_rows: int = 1_000_000,
    train_rows: int | None = None,
    n_estimators: int = 1000,
    shap_rows: int = 20_000,
    review_cost: float = 10.0,
    fix_rate: float = 0.5,
    seed: int = 42,
    drop: tuple[str, ...] = (),
) -> dict:
    figures = reports_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(features_path, columns=ID_COLS + FEATURES + [TARGET])
    train = df[df["split"] == "train"]
    valid = df[df["split"] == "valid"].reset_index(drop=True)
    test = df[df["split"] == "test"].reset_index(drop=True)
    if train_rows and len(train) > train_rows:
        train = train.sample(train_rows, random_state=seed)
    train = train.reset_index(drop=True)
    print(f"rows: train {len(train):,}, valid {len(valid):,}, test {len(test):,}")

    gbm_cols = [c for c in FEATURES if c not in set(drop)]
    if drop:
        print(f"LightGBM without: {', '.join(drop)}")
    spec = fit_categories(train)
    Xtr, ytr, _ = prepare(train, spec)
    Xva, yva, ava = prepare(valid, spec)
    Xte, yte, ate = prepare(test, spec)

    # ---- baselines and model ----
    base_rate = float(ytr.mean())
    type_rate = train.groupby("claim_type")[TARGET].mean()

    def p_type(frame: pd.DataFrame) -> np.ndarray:
        return frame["claim_type"].map(type_rate).fillna(base_rate).to_numpy()

    print("training logistic regression baseline ...")
    lr_idx = np.random.default_rng(seed).choice(len(Xtr), min(lr_rows, len(Xtr)), replace=False)
    lr = lr_pipeline(seed).fit(lr_frame(Xtr.iloc[lr_idx]), ytr[lr_idx])

    print("training LightGBM ...")
    gbm = lgb.LGBMClassifier(
        n_estimators=n_estimators,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=200,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        cat_smooth=50,
        min_data_per_group=100,
        random_state=seed,
        n_jobs=-1,
        verbose=-1,
    )
    gbm.fit(
        Xtr[gbm_cols],
        ytr,
        eval_set=[(Xva[gbm_cols], yva)],
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )
    best_iter = int(gbm.best_iteration_ or n_estimators)
    print(f"LightGBM best iteration: {best_iter}")

    pva_gbm = gbm.predict_proba(Xva[gbm_cols])[:, 1]
    calibrator = PlattCalibrator().fit(pva_gbm, yva)

    def predict_all(X: pd.DataFrame, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        raw = gbm.predict_proba(X[gbm_cols])[:, 1]
        return {
            "base rate only": np.full(len(X), base_rate),
            "claim-type rate": p_type(frame),
            "logistic regression": lr.predict_proba(lr_frame(X))[:, 1],
            "LightGBM": raw,
            "LightGBM calibrated": calibrator.predict(raw),
        }

    preds = {"valid": predict_all(Xva, valid), "test": predict_all(Xte, test)}
    ys = {"valid": yva, "test": yte}
    frames = {"valid": valid, "test": test}

    # ---- metrics table ----
    rows = []
    for split in ("valid", "test"):
        for name, p in preds[split].items():
            rows.append({"model": name, "split": split, **basic_metrics(ys[split], p)})
        oracle = load_oracle(labels_path, frames[split]["claim_id"])
        if oracle is not None:
            rows.append(
                {
                    "model": "oracle (true probability)",
                    "split": split,
                    **basic_metrics(ys[split], oracle),
                }
            )
    metrics_df = pd.DataFrame(rows)
    metrics_df.to_csv(reports_dir / "metrics_table.csv", index=False)

    # ---- review queue and ROI (test) ----
    p_cal = preds["test"]["LightGBM calibrated"]
    topk = topk_table(yte, ate, p_cal, REVIEW_FRACTIONS, fix_rate, review_cost)
    topk.to_csv(reports_dir / "topk_table.csv", index=False)

    # ---- calibration (test) ----
    cal_raw, ece_raw = calibration_table(yte, preds["test"]["LightGBM"])
    cal_cal, ece_cal = calibration_table(yte, p_cal)
    cal_cal.to_csv(reports_dir / "calibration_table.csv", index=False)

    # ---- groups ----
    ct = by_group(test, yte, p_cal, "claim_type")
    test_month = test.assign(month=pd.to_datetime(test["from_dt"]).dt.to_period("M").astype(str))
    months = by_group(test_month, yte, p_cal, "month")
    ct.to_csv(reports_dir / "metrics_by_claim_type.csv", index=False)
    months.to_csv(reports_dir / "metrics_by_month.csv", index=False)

    # ---- importance and SHAP ----
    imp = pd.Series(gbm.booster_.feature_importance("gain"), index=gbm_cols).sort_values(
        ascending=False
    )
    imp.rename("gain").to_csv(reports_dir / "feature_importance_gain.csv")
    sample_idx = np.random.default_rng(seed).choice(
        len(Xte), min(shap_rows, len(Xte)), replace=False
    )
    Xs = Xte.iloc[sample_idx][gbm_cols]
    contrib, _ = shap_contributions(gbm, Xs)
    mean_abs = pd.Series(np.abs(contrib).mean(axis=0), index=gbm_cols).sort_values(ascending=False)
    mean_abs.rename("mean_abs_shap").to_csv(reports_dir / "shap_importance.csv")

    top_idx = np.argsort(-p_cal)[:5]
    drivers = top_drivers(gbm, Xte.iloc[top_idx][gbm_cols], k=5)
    example_rows = []
    for rank, (i, d) in enumerate(zip(top_idx, drivers, strict=True), start=1):
        for item in d:
            example_rows.append(
                {
                    "rank": rank,
                    "claim_id": test.loc[i, "claim_id"],
                    "predicted_probability": float(p_cal[i]),
                    "actual_denied": int(yte[i]),
                    **item,
                }
            )
    pd.DataFrame(example_rows).to_csv(reports_dir / "example_explanations.csv", index=False)

    # ---- figures ----
    plots.roc_pr(
        yte,
        {k: preds["test"][k] for k in ("logistic regression", "LightGBM calibrated")},
        figures / "roc_pr.png",
    )
    plots.calibration(
        {"LightGBM (raw)": cal_raw, "LightGBM (Platt)": cal_cal}, figures / "calibration.png"
    )
    plots.gains(
        {
            "rank by probability": cumulative_gain_curve(yte, ate, p_cal),
            "rank by expected loss": cumulative_gain_curve(yte, ate, p_cal * ate),
        },
        figures / "gains.png",
    )
    plots.shap_bar(mean_abs, figures / "shap_bar.png")
    plots.shap_summary(contrib, Xs, figures / "shap_summary.png")

    # ---- artifacts for the API and app ----
    gbm.booster_.save_model(str(models_dir / "lgbm_denial.txt"))
    joblib.dump(calibrator, models_dir / "calibrator.joblib")
    (models_dir / "feature_spec.json").write_text(
        json.dumps(
            {
                "features": gbm_cols,
                "categories": spec,
                "base_rate": base_rate,
                "best_iteration": best_iter,
            },
            indent=2,
        )
    )

    # ---- run log and report ----
    t = metrics_df[metrics_df["split"] == "test"].set_index("model")
    summary = {
        "test_roc_auc": float(t.loc["LightGBM calibrated", "roc_auc"]),
        "test_pr_auc": float(t.loc["LightGBM calibrated", "pr_auc"]),
        "test_recall_at_10": float(t.loc["LightGBM calibrated", "recall_at_10"]),
        "ece_raw": ece_raw,
        "ece_calibrated": ece_cal,
        "best_iteration": best_iter,
    }
    log_row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "commit": git_commit(),
        "train_rows": len(train),
        "lr_rows": min(lr_rows, len(Xtr)),
        "seed": seed,
        "review_cost": review_cost,
        "fix_rate": fix_rate,
        "dropped": ",".join(drop),
        **summary,
    }
    log_path = reports_dir / "run_log.csv"
    log_df = pd.DataFrame([log_row])
    if log_path.exists():
        log_df = pd.concat([pd.read_csv(log_path), log_df], ignore_index=True)
    log_df.to_csv(log_path, index=False)

    report = [
        "# Model report",
        "",
        f"Generated {log_row['timestamp']} (commit {log_row['commit']}). "
        "Labels are simulated (ADR-001), so scores show how well patterns are recovered, "
        "not how a real payer behaves.",
        "",
        "## Data split (ADR-011)",
        f"- train {len(train):,} claims, valid {len(valid):,}, test {len(test):,}",
        f"- training denial rate {base_rate:.4f}; test denial rate {yte.mean():.4f}",
        "",
        "## Model comparison",
        md_table(metrics_df),
        "",
        "## Review queue on the test period "
        f"(assumptions: review cost ${review_cost:,.2f} per claim, "
        f"{fix_rate:.0%} of caught denials fixed)",
        md_table(topk),
        "",
        "## Calibration (test)",
        f"- expected calibration error: raw {ece_raw:.4f}, Platt {ece_cal:.4f}",
        "",
        "## By claim type (test, calibrated LightGBM)",
        md_table(ct),
        "",
        "## Top features by mean |SHAP|",
        md_table(
            mean_abs.head(12)
            .rename("mean_abs_shap")
            .reset_index()
            .rename(columns={"index": "feature"})
        ),
        "",
        "Figures are in `reports/figures/`.",
    ]
    (reports_dir / "model_report.md").write_text("\n".join(report) + "\n")
    print(md_table(metrics_df[metrics_df["split"] == "test"]))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, default=FEATURES_DEFAULT)
    ap.add_argument("--labels", type=Path, default=LABELS_DEFAULT)
    ap.add_argument("--reports", type=Path, default=Path("reports"))
    ap.add_argument("--models", type=Path, default=Path("models"))
    ap.add_argument("--lr-rows", type=int, default=1_000_000)
    ap.add_argument("--train-rows", type=int, default=None)
    ap.add_argument("--n-estimators", type=int, default=1000)
    ap.add_argument("--shap-rows", type=int, default=20_000)
    ap.add_argument("--review-cost", type=float, default=10.0)
    ap.add_argument("--fix-rate", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--drop", default="", help="comma-separated features to leave out of LightGBM")
    a = ap.parse_args()
    run(
        a.features,
        a.reports,
        a.models,
        a.labels,
        a.lr_rows,
        a.train_rows,
        a.n_estimators,
        a.shap_rows,
        a.review_cost,
        a.fix_rate,
        a.seed,
        drop=tuple(c.strip() for c in a.drop.split(",") if c.strip()),
    )


if __name__ == "__main__":
    main()

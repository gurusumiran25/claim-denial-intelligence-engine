import numpy as np
import pandas as pd
import pytest

from src.training import features as F
from src.training.calibration import PlattCalibrator
from src.training.metrics import (
    basic_metrics,
    calibration_table,
    cumulative_gain_curve,
    dollars_captured,
    net_benefit,
    precision_at_k,
    recall_at_k,
    topk_table,
)
from src.training.train import run


def make_features(n: int = 24000, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = np.minimum(np.round(rng.lognormal(np.log(18), 0.9, n)), 365)
    auth_req = rng.random(n) < 0.15
    auth_on = ~auth_req | (rng.random(n) < 0.85)
    n_lines = rng.integers(1, 8, n)
    unknown = rng.integers(0, 2, n)
    logit = (
        -3.0
        + 3.0 * (days > 90)
        + 2.5 * (auth_req & ~auth_on)
        + 1.5 * (n_lines >= 6)
        + 1.0 * unknown
        + rng.normal(0, 0.3, n)
    )
    denied = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    date = pd.Timestamp("2008-01-01") + pd.to_timedelta(rng.integers(0, 1095, n), unit="D")
    split = np.where(date <= "2009-12-31", "train", np.where(date <= "2010-06-30", "valid", "test"))
    amount = np.round(rng.lognormal(5, 1, n), 0) + 10
    return pd.DataFrame(
        {
            "claim_id": [f"C{i}" for i in range(n)],
            "bene_id": "B1",
            "provider_id": "T:1",
            "from_dt": date.date,
            "claim_year": date.year,
            "day_index": (date - pd.Timestamp("2008-01-01")).days,
            "split": split,
            "claim_type": rng.choice(
                ["inpatient", "outpatient", "carrier"], n, p=[0.05, 0.25, 0.7]
            ),
            "amount": amount,
            "amount_log": np.log(amount),
            "n_lines": n_lines,
            "procedure_unknown": unknown,
            "dx_group": rng.choice([f"D{i}" for i in range(20)], n),
            "drg_code": rng.choice([None, "100", "200"], n),
            "los_days": np.where(rng.random(n) < 0.1, rng.integers(1, 10, n), np.nan),
            "claim_month": date.month,
            "age_at_claim": rng.uniform(65, 95, n),
            "sex": rng.choice(["1", "2"], n),
            "coverage_active": 1,
            "chronic_count_prior_year": rng.integers(0, 6, n).astype(float),
            "member_claims_prior_90d": rng.integers(0, 10, n),
            "days_to_file": days,
            "auth_required": auth_req.astype(int),
            "auth_on_file": auth_on.astype(int),
            "provider_prior_claims": rng.integers(0, 300, n),
            "provider_prior_denied": rng.integers(0, 30, n),
            "provider_claims_prior_30d": rng.integers(0, 100, n),
            "provider_denial_rate_smoothed": rng.uniform(0.05, 0.2, n),
            "is_denied": denied,
        }
    )


def test_fit_categories_caps_rare_levels():
    train = pd.DataFrame(
        {
            "claim_type": ["a"] * 200 + ["b"] * 150,
            "dx_group": ["x"] * 300 + ["rare"] * 5 + [None] * 45,
            "drg_code": ["1"] * 350,
            "sex": ["1"] * 350,
        }
    )
    spec = F.fit_categories(train)
    assert "rare" not in spec["dx_group"] and "x" in spec["dx_group"]


def test_prepare_maps_unseen_and_missing():
    df = make_features(600)
    spec = F.fit_categories(df)
    df.loc[0, "dx_group"] = "never_seen"
    df.loc[1, "dx_group"] = None
    X, y, amount = F.prepare(df, spec)
    assert list(X.columns) == F.FEATURES
    assert X.loc[0, "dx_group"] == F.LEVEL_OTHER
    assert X.loc[1, "dx_group"] == F.LEVEL_MISSING
    assert len(y) == len(amount) == len(df)


def test_ranking_metrics():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.3, 0.2, 0.1, 0.1, 0.1, 0.05, 0.05, 0.01])
    assert recall_at_k(y, p, 0.2) == 1.0
    assert precision_at_k(y, p, 0.2) == 1.0
    assert recall_at_k(y, p, 0.1) == 0.5
    m = basic_metrics(y, p)
    assert m["roc_auc"] == 1.0 and m["lift_at_10"] == pytest.approx(5.0)


def test_dollars_and_net_benefit():
    y = np.array([1, 0, 1, 0])
    amount = np.array([100.0, 500.0, 300.0, 50.0])
    p = np.array([0.9, 0.8, 0.7, 0.1])
    assert dollars_captured(y, amount, p, 0.5) == 100.0
    assert net_benefit(100.0, 2, fix_rate=0.5, review_cost=10.0) == 30.0
    tab = topk_table(y, amount, p, (0.5,), fix_rate=0.5, review_cost=10.0)
    assert tab.loc[0, "claims_reviewed"] == 2
    assert tab.loc[0, "dollars_share_by_expected_loss"] == pytest.approx(0.75)


def test_gain_curve_is_monotone_and_ends_at_one():
    rng = np.random.default_rng(0)
    y = (rng.random(2000) < 0.1).astype(int)
    amount = rng.uniform(10, 500, 2000)
    xs, ys = cumulative_gain_curve(y, amount, rng.random(2000))
    assert xs[0] == 0 and ys[0] == 0 and ys[-1] == pytest.approx(1.0)
    assert np.all(np.diff(ys) >= -1e-12)


def test_platt_calibrator_keeps_ranking_and_fixes_scale():
    rng = np.random.default_rng(1)
    true_p = rng.uniform(0.02, 0.4, 20000)
    y = (rng.random(20000) < true_p).astype(int)
    raw = np.clip(true_p * 0.5, 1e-4, 0.99)  # badly under-confident scores
    cal = PlattCalibrator().fit(raw, y)
    out = cal.predict(raw)
    assert np.all(np.diff(out[np.argsort(raw)]) >= -1e-12)  # same order
    _, ece_before = calibration_table(y, raw)
    _, ece_after = calibration_table(y, out)
    assert ece_after < ece_before


def test_end_to_end_training(tmp_path):
    feats = tmp_path / "features.parquet"
    make_features().to_parquet(feats, index=False)
    summary = run(
        feats,
        tmp_path / "reports",
        tmp_path / "models",
        labels_path=tmp_path / "missing.parquet",
        lr_rows=8000,
        n_estimators=60,
        shap_rows=400,
        drop=("dx_group",),
    )
    assert summary["test_roc_auc"] > 0.68
    for name in ("metrics_table.csv", "topk_table.csv", "model_report.md", "run_log.csv"):
        assert (tmp_path / "reports" / name).exists()
    for name in ("gains.png", "shap_summary.png", "calibration.png", "roc_pr.png", "shap_bar.png"):
        assert (tmp_path / "reports" / "figures" / name).exists()
    for name in ("lgbm_denial.txt", "calibrator.joblib", "feature_spec.json"):
        assert (tmp_path / "models" / name).exists()
    assert (
        "dx_group"
        not in (tmp_path / "models" / "feature_spec.json").read_text().split("categories")[0]
    )

import numpy as np
import pandas as pd

from simulator.label_claims import KEEP_COLS, add_submission_fields, roc_auc, run
from simulator.simulate_denials import simulate


def make_claims(n: int = 20000, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    claim_type = rng.choice(["inpatient", "outpatient", "carrier"], size=n, p=[0.05, 0.25, 0.70])
    mu = pd.Series(claim_type).map({"inpatient": 9.0, "outpatient": 5.0, "carrier": 4.0})
    return pd.DataFrame(
        {
            "claim_id": [f"C{i}" for i in range(n)],
            "bene_id": [f"B{x}" for x in rng.integers(0, 2000, n)],
            "provider_id": [f"F:{x}" for x in rng.integers(0, 300, n)],
            "claim_type": claim_type,
            "from_dt": pd.Timestamp("2008-01-01")
            + pd.to_timedelta(rng.integers(0, 1000, n), unit="D"),
            "procedure_code": rng.choice([f"P{i}" for i in range(40)], size=n),
            "primary_dx": rng.choice([f"D{i}" for i in range(30)], size=n),
            "n_lines": np.minimum(rng.geometric(0.5, size=n), 13).astype("int16"),
            "amount": np.round(rng.lognormal(mu.to_numpy(), 0.8), 2),
            "coverage_active": rng.random(n) > 0.01,
        }
    )


def test_submission_fields_shape_and_rules():
    out = add_submission_fields(make_claims())
    assert out["days_to_file"].between(0, 365).all()
    share_late = (out["days_to_file"] > 90).mean()
    assert 0.02 < share_late < 0.06
    not_required = ~out["auth_required"]
    assert out.loc[not_required, "auth_on_file"].all()
    required = out[out["auth_required"]]
    assert 0.75 < required["auth_on_file"].mean() < 0.95
    inpatient = out[out["claim_type"] == "inpatient"]
    assert inpatient["auth_required"].mean() > 0.8


def test_submission_fields_reproducible():
    df = make_claims(3000)
    a = add_submission_fields(df)
    b = add_submission_fields(df)
    pd.testing.assert_frame_equal(a, b)


def test_target_rate_is_hit():
    df = add_submission_fields(make_claims())
    labeled = simulate(df, target_rate=0.10)
    assert abs(labeled["is_denied"].mean() - 0.10) < 0.008
    assert abs(labeled["p_denial_true"].mean() - 0.10) < 0.002


def test_run_writes_label_table(tmp_path):
    inp = tmp_path / "claims_unified.parquet"
    out = tmp_path / "claim_labels.parquet"
    make_claims(5000).to_parquet(inp, index=False)
    run(inp, out, target_rate=0.10)
    labels = pd.read_parquet(out)
    assert list(labels.columns) == KEEP_COLS
    assert len(labels) == 5000 and labels["claim_id"].is_unique
    assert 0.07 < labels["is_denied"].mean() < 0.13
    assert labels.loc[labels["is_denied"] == 1, "carc_code"].notna().all()


def test_roc_auc_helper():
    y = np.array([0, 0, 0, 1, 1, 1])
    assert roc_auc(y, np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])) == 1.0
    rng = np.random.default_rng(0)
    big = rng.integers(0, 2, 20000)
    assert abs(roc_auc(big, rng.random(20000)) - 0.5) < 0.02

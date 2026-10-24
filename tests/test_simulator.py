import pandas as pd
import pytest

from ingestion.make_toy_claims import make_toy_claims
from simulator.simulate_denials import LEAKAGE_COLUMNS, load_rules, simulate


@pytest.fixture(scope="module")
def labeled():
    return simulate(make_toy_claims(n=8000, seed=1))


def test_rules_file_is_valid():
    cfg = load_rules()
    assert cfg["rules"]
    assert all({"carc", "effect", "observable"} <= set(r) for r in cfg["rules"].values())


def test_overall_denial_rate_is_realistic(labeled):
    rate = labeled["is_denied"].mean()
    assert 0.06 <= rate <= 0.18, f"denial rate {rate:.3f} outside expected band"


def test_reproducible():
    df = make_toy_claims(n=3000, seed=3)
    a = simulate(df)["is_denied"]
    b = simulate(df)["is_denied"]
    pd.testing.assert_series_equal(a, b)


def test_denied_claims_have_reason_codes(labeled):
    denied = labeled[labeled["is_denied"] == 1]
    assert denied["carc_code"].notna().all()
    assert labeled.loc[labeled["is_denied"] == 0, "carc_code"].isna().all()


def test_rule_effects_move_denial_rate(labeled):
    late = labeled[labeled["days_to_file"] > 90]["is_denied"].mean()
    ontime = labeled[labeled["days_to_file"] <= 90]["is_denied"].mean()
    assert late > ontime


def test_missing_columns_raises():
    with pytest.raises(ValueError):
        simulate(make_toy_claims(n=100).drop(columns=["amount"]))


def test_leakage_columns_declared(labeled):
    assert set(LEAKAGE_COLUMNS) <= set(labeled.columns)

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


def _frame(rows):
    base = dict(
        claim_id="x",
        bene_id="B1",
        provider_id="F:1",
        claim_type="outpatient",
        from_dt=pd.Timestamp("2009-01-01"),
        procedure_code="P1",
        primary_dx="D1",
        n_lines=1,
        amount=100.0,
        days_to_file=10,
        auth_required=False,
        auth_on_file=True,
        coverage_active=True,
    )
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["claim_id"] = [f"C{i}" for i in range(len(df))]
    return df


def test_duplicate_rule_ignores_unknown_procedure():
    known = simulate(_frame([{}, {}])).attrs["trigger_counts"]
    unknown = simulate(_frame([{"procedure_code": "UNKNOWN"}] * 2)).attrs["trigger_counts"]
    assert known["duplicate_claim"] == 1
    assert unknown["duplicate_claim"] == 0


def test_new_observable_rules_trigger():
    df = _frame(
        [
            {"procedure_code": "UNKNOWN"},
            {"procedure_code": "UNKNOWN", "claim_type": "inpatient"},
            {"n_lines": 8, "bene_id": "B2"},
        ]
    )
    counts = simulate(df).attrs["trigger_counts"]
    assert counts["missing_procedure_code"] == 1  # inpatient is exempt
    assert counts["many_service_lines"] == 1

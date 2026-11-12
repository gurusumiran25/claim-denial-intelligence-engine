import numpy as np
import pandas as pd
import pytest

from src.analysis import root_cause as rc
from src.rag.knowledge import load_playbook


@pytest.fixture()
def files(tmp_path):
    rng = np.random.default_rng(2)
    n = 20000
    claims = pd.DataFrame(
        {
            "claim_id": [f"C{i}" for i in range(n)],
            "claim_type": rng.choice(
                ["inpatient", "outpatient", "carrier"], n, p=[0.05, 0.25, 0.7]
            ),
            "provider_id": [f"P{x}" for x in rng.integers(0, 100, n)],
            "from_dt": pd.Timestamp("2008-01-01")
            + pd.to_timedelta(rng.integers(0, 700, n), unit="D"),
            "amount": np.round(rng.lognormal(5, 1, n), 2),
        }
    )
    denied = rng.random(n) < 0.1
    codes = np.where(denied, rng.choice(["CO-29", "CO-197", "CO-16"], n, p=[0.5, 0.3, 0.2]), None)
    labels = pd.DataFrame(
        {
            "claim_id": claims["claim_id"],
            "is_denied": denied.astype(int),
            "carc_code": codes,
            "days_to_file": 10,
            "auth_required": False,
            "auth_on_file": True,
        }
    )
    c, lab = tmp_path / "claims.parquet", tmp_path / "labels.parquet"
    claims.to_parquet(c, index=False)
    labels.to_parquet(lab, index=False)
    return c, lab, claims, labels


def test_pareto_is_ranked_and_cumulative(files):
    c, lab, claims, labels = files
    df, _, _ = rc.load_denied(c, lab)
    assert len(df) == int(labels["is_denied"].sum())
    par = rc.pareto(df)
    assert par["denied_dollars"].is_monotonic_decreasing
    assert par["cum_dollars_share"].iloc[-1] == pytest.approx(1.0)
    assert par["dollars_share"].sum() == pytest.approx(1.0)
    by_type = rc.pareto(df, by=["claim_type"])
    assert by_type.groupby("claim_type")["dollars_share"].sum().round(6).eq(1.0).all()


def test_provider_concentration_and_routes(files):
    c, lab, _, _ = files
    df, totals, _ = rc.load_denied(c, lab)
    top, conc = rc.provider_concentration(df, totals, top=5)
    assert len(top) == 5 and (top["denial_rate"] <= 1).all()
    assert (
        conc["top_1pct_providers_dollar_share"]
        <= conc["top_5pct_providers_dollar_share"]
        <= conc["top_10pct_providers_dollar_share"]
        <= 1
    )
    by_reason, by_cat = rc.fixability(rc.pareto(df), load_playbook())
    routes = rc.route_shares(by_reason)
    assert sum(routes.values()) == pytest.approx(1.0)
    assert by_cat["dollars_share"].sum() == pytest.approx(1.0)


def test_run_writes_report_tables_and_figures(files, tmp_path):
    c, lab, _, _ = files
    out = tmp_path / "out"
    summary = rc.run(c, lab, out)
    assert summary["denied_claims"] > 0
    for name in (
        "pareto_overall.csv",
        "root_cause_report.md",
        "root_causes_by_category.csv",
        "top_providers.csv",
    ):
        assert (out / name).exists()
    for name in ("pareto.png", "monthly_mix.png", "provider_concentration.png"):
        assert (out / "figures" / name).exists()
    assert "Root-cause analysis" in (out / "root_cause_report.md").read_text()

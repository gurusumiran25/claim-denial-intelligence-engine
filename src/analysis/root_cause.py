"""Root-cause analysis of denied claims, from local Parquet files (no cloud account needed).

Run from the project root:
    python -m src.analysis.root_cause
Writes tables, figures and a report to reports/root_cause/.

Note: the denial reasons come from the simulator (ADR-001, ADR-009), so the findings show the
method and what the pipeline can surface, not how a real payer behaves.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.compute as pc  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.rag.knowledge import load_playbook  # noqa: E402

CLAIMS_DEFAULT = Path("data/processed/claims_unified.parquet")
LABELS_DEFAULT = Path("data/processed/claim_labels.parquet")
OUT_DEFAULT = Path("reports/root_cause")


def load_denied(
    claims_path: Path, labels_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (denied claims with reasons, claims per provider, claims per claim type)."""
    labels = pq.read_table(
        labels_path,
        columns=[
            "claim_id",
            "is_denied",
            "carc_code",
            "days_to_file",
            "auth_required",
            "auth_on_file",
        ],
    )
    denied_labels = labels.filter(pc.equal(labels["is_denied"], 1))
    claims = pq.read_table(
        claims_path, columns=["claim_id", "claim_type", "provider_id", "from_dt", "amount"]
    )
    provider_totals = claims.group_by("provider_id").aggregate([("claim_id", "count")]).to_pandas()
    provider_totals = provider_totals.rename(columns={"claim_id_count": "claims"})
    type_totals = claims.group_by("claim_type").aggregate([("claim_id", "count")]).to_pandas()
    type_totals = type_totals.rename(columns={"claim_id_count": "claims"})
    denied_claims = claims.filter(pc.is_in(claims["claim_id"], value_set=denied_labels["claim_id"]))
    df = denied_claims.to_pandas().merge(denied_labels.to_pandas(), on="claim_id")
    df["from_dt"] = pd.to_datetime(df["from_dt"])
    return df, provider_totals, type_totals


def pareto(df: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Denial reasons ranked by denied dollars, with claim and dollar shares (and cumulative)."""
    keys = (by or []) + ["carc_code"]
    t = (
        df.groupby(keys)
        .agg(denied_claims=("claim_id", "size"), denied_dollars=("amount", "sum"))
        .reset_index()
    )
    group_keys = by or []

    def shares(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("denied_dollars", ascending=False).copy()
        g["claims_share"] = g["denied_claims"] / g["denied_claims"].sum()
        g["dollars_share"] = g["denied_dollars"] / g["denied_dollars"].sum()
        g["cum_dollars_share"] = g["dollars_share"].cumsum()
        g["rank_by_claims"] = g["denied_claims"].rank(ascending=False, method="min").astype(int)
        return g

    if group_keys:
        return pd.concat([shares(g) for _, g in t.groupby(group_keys)], ignore_index=True)
    return shares(t).reset_index(drop=True)


def monthly_mix(df: pd.DataFrame) -> pd.DataFrame:
    month = df["from_dt"].dt.to_period("M").astype(str)
    return pd.crosstab(month, df["carc_code"]).rename_axis("month").reset_index()


def provider_concentration(
    df: pd.DataFrame, provider_totals: pd.DataFrame, top: int = 20
) -> tuple[pd.DataFrame, dict]:
    g = df.groupby("provider_id").agg(
        denied_claims=("claim_id", "size"), denied_dollars=("amount", "sum")
    )
    g = g.reset_index().merge(provider_totals, on="provider_id", how="left")
    g["denial_rate"] = g["denied_claims"] / g["claims"]
    g = g.sort_values("denied_dollars", ascending=False).reset_index(drop=True)
    cum = g["denied_dollars"].cumsum() / g["denied_dollars"].sum()
    stats = {"providers_with_denials": int(len(g))}
    for share in (0.01, 0.05, 0.10):
        k = max(1, int(np.ceil(share * len(g))))
        stats[f"top_{int(share * 100)}pct_providers_dollar_share"] = float(cum.iloc[k - 1])
    return g.head(top), {**stats, "lorenz": cum.to_numpy()}


def fixability(par: pd.DataFrame, playbook: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join reasons to root-cause categories; return (by reason, by category)."""
    meta = pd.DataFrame(
        [
            {
                "carc_code": code,
                "reason": e["title"],
                "root_cause": e["root_cause"]["category"],
                "owner": e["root_cause"]["owner"],
                "fixability": e["root_cause"]["fixability"],
                "default_action": e["default_action"],
                "prevention": "; ".join(e["root_cause"]["prevention"]),
            }
            for code, e in playbook.items()
        ]
    )
    by_reason = par.merge(meta, on="carc_code", how="left")
    by_cat = (
        by_reason.groupby(["root_cause", "owner", "fixability"])
        .agg(denied_claims=("denied_claims", "sum"), denied_dollars=("denied_dollars", "sum"))
        .reset_index()
        .sort_values("denied_dollars", ascending=False)
    )
    by_cat["dollars_share"] = by_cat["denied_dollars"] / by_cat["denied_dollars"].sum()
    return by_reason, by_cat


def route_shares(by_reason: pd.DataFrame) -> dict[str, float]:
    """Share of denied dollars by the recommended route (appeal, corrected claim, no appeal)."""
    total = by_reason["denied_dollars"].sum()
    return {
        route: float(
            by_reason.loc[by_reason["default_action"] == route, "denied_dollars"].sum() / total
        )
        for route in ("appeal", "corrected_claim", "no_appeal")
    }


def _pareto_chart(par: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(par["carc_code"], par["denied_dollars"] / 1e6, color="#4c72b0")
    ax.set(
        xlabel="Denial reason", ylabel="Denied dollars (millions)", title="Denied dollars by reason"
    )
    ax2 = ax.twinx()
    ax2.plot(par["carc_code"], par["cum_dollars_share"] * 100, color="#dd8452", marker="o")
    ax2.set_ylabel("Cumulative share of denied dollars (%)")
    ax2.set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _mix_chart(mix: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    data = mix.set_index("month")
    ax.stackplot(range(len(data)), data.T.to_numpy(), labels=list(data.columns))
    step = max(1, len(data) // 8)
    ax.set_xticks(range(0, len(data), step))
    ax.set_xticklabels(list(data.index)[::step], rotation=45)
    ax.set(ylabel="Denied claims", title="Denial reasons by month")
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _lorenz_chart(cum: np.ndarray, path: Path) -> None:
    xs = np.arange(1, len(cum) + 1) / len(cum)
    fig, ax = plt.subplots(figsize=(5, 4.5))
    ax.plot(xs, cum, label="providers ranked by denied dollars")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, label="equal share")
    ax.set(
        xlabel="Share of providers (largest first)",
        ylabel="Share of denied dollars",
        title="Concentration of denied dollars",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _md(df: pd.DataFrame, fmt: str = "{:,.4f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append(
            "| " + " | ".join(fmt.format(v) if isinstance(v, float) else str(v) for v in r) + " |"
        )
    return "\n".join(lines)


def run(claims_path: Path, labels_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(exist_ok=True)
    df, provider_totals, type_totals = load_denied(claims_path, labels_path)
    playbook = load_playbook()

    par = pareto(df)
    par_type = pareto(df, by=["claim_type"])
    mix = monthly_mix(df)
    top_providers, conc = provider_concentration(df, provider_totals)
    by_reason, by_cat = fixability(par, playbook)

    par.to_csv(out_dir / "pareto_overall.csv", index=False)
    par_type.to_csv(out_dir / "pareto_by_claim_type.csv", index=False)
    mix.to_csv(out_dir / "monthly_reason_mix.csv", index=False)
    top_providers.to_csv(out_dir / "top_providers.csv", index=False)
    by_reason.to_csv(out_dir / "root_causes_by_reason.csv", index=False)
    by_cat.to_csv(out_dir / "root_causes_by_category.csv", index=False)
    _pareto_chart(par, fig_dir / "pareto.png")
    _mix_chart(mix, fig_dir / "monthly_mix.png")
    _lorenz_chart(conc["lorenz"], fig_dir / "provider_concentration.png")

    total_claims = int(df["claim_id"].count())
    total_dollars = float(df["amount"].sum())
    routes = route_shares(by_reason)
    top_claims = par.sort_values("denied_claims", ascending=False).head(3)
    top_dollars = par.head(3)
    report = [
        "# Root-cause analysis of denied claims",
        "",
        "Reasons come from the simulator (ADR-001, ADR-009), so this shows what the pipeline can "
        "surface, not how a real payer behaves. CO-16 also absorbs the simulator's unexplained "
        "baseline denials.",
        "",
        f"- Denied claims: {total_claims:,}; denied dollars: ${total_dollars:,.0f}",
        "- Top 3 reasons by claim count: "
        + ", ".join(f"{r.carc_code} ({r.claims_share:.1%})" for r in top_claims.itertuples()),
        "- Top 3 reasons by dollars: "
        + ", ".join(f"{r.carc_code} ({r.dollars_share:.1%})" for r in top_dollars.itertuples()),
        "- Recommended route by denied dollars: "
        f"appeal {routes['appeal']:.1%}, corrected claim {routes['corrected_claim']:.1%}, "
        f"no appeal {routes['no_appeal']:.1%}",
        "",
        "## Denial reasons ranked by dollars",
        _md(par),
        "",
        "## Root-cause categories and owners",
        _md(by_cat),
        "",
        "## Provider concentration",
        f"- Providers with at least one denial: {conc['providers_with_denials']:,}",
        f"- Top 1% of providers hold {conc['top_1pct_providers_dollar_share']:.1%} "
        "of denied dollars, "
        f"top 5% hold {conc['top_5pct_providers_dollar_share']:.1%}, "
        f"top 10% hold {conc['top_10pct_providers_dollar_share']:.1%}",
        "",
        "## Top providers by denied dollars",
        _md(top_providers.head(10)),
        "",
        "## Prevention actions by reason",
        _md(by_reason[["carc_code", "reason", "owner", "fixability", "prevention"]]),
        "",
        "Figures are in `reports/root_cause/figures/`.",
    ]
    (out_dir / "root_cause_report.md").write_text("\n".join(report) + "\n")
    return {
        "denied_claims": total_claims,
        "denied_dollars": total_dollars,
        **{f"route_share_{k}": v for k, v in routes.items()},
        "top_dollar_reason": str(par.iloc[0]["carc_code"]),
        **{k: v for k, v in conc.items() if k != "lorenz"},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", type=Path, default=CLAIMS_DEFAULT)
    ap.add_argument("--labels", type=Path, default=LABELS_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    summary = run(args.claims, args.labels, args.out)
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"report written to {args.out / 'root_cause_report.md'}")


if __name__ == "__main__":
    main()

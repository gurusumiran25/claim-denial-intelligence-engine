"""Add synthesized submission fields to claims_unified and simulate denial labels.

Reads  data/processed/claims_unified.parquet  (from ingestion.build_claims_unified)
Writes data/processed/claim_labels.parquet     (one row per claim_id, join back on claim_id)

Synthesized fields (not in the raw data; documented in docs/decisions.md ADR-009):
  days_to_file  lognormal, median 18 days, sigma 0.9, capped at 365 (about 3.7% above 90 days)
  auth_required inpatient: 90%; others: amounts above the claim-type 90th percentile, plus 3%
  auth_on_file  always true when not required; 85% when required

Run from the project root with the venv active:
    python -m simulator.label_claims | Out-File -Encoding utf8 docs\\label_report.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from simulator.simulate_denials import simulate

SEED = 42
IN_DEFAULT = Path("data/processed/claims_unified.parquet")
OUT_DEFAULT = Path("data/processed/claim_labels.parquet")
READ_COLS = [
    "claim_id",
    "bene_id",
    "provider_id",
    "claim_type",
    "from_dt",
    "procedure_code",
    "primary_dx",
    "n_lines",
    "amount",
    "coverage_active",
]
CATEGORY_COLS = ["bene_id", "provider_id", "claim_type", "procedure_code", "primary_dx"]
KEEP_COLS = [
    "claim_id",
    "days_to_file",
    "auth_required",
    "auth_on_file",
    "is_denied",
    "carc_code",
    "denial_rule_id",
    "p_denial_true",
]


def add_submission_fields(df: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(df)
    out = df.copy()
    days = np.minimum(np.round(rng.lognormal(np.log(18), 0.9, n)), 365)
    out["days_to_file"] = days.astype("int16")

    is_inpatient = out["claim_type"].eq("inpatient").to_numpy()
    q90 = out.groupby("claim_type", observed=True)["amount"].transform(lambda s: s.quantile(0.90))
    high_amount = out["amount"].to_numpy() > q90.to_numpy()
    r_required = rng.random(n)
    r_on_file = rng.random(n)
    required = np.where(is_inpatient, r_required < 0.90, high_amount | (r_required < 0.03))
    out["auth_required"] = required
    out["auth_on_file"] = ~required | (r_on_file < 0.85)
    return out


def roc_auc(y: np.ndarray, score: np.ndarray) -> float:
    """Rank-based ROC-AUC (no sklearn needed)."""
    y = np.asarray(y)[np.argsort(score, kind="mergesort")]
    ranks = np.arange(1, len(y) + 1)
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def run(inp: Path, out: Path, target_rate: float) -> pd.DataFrame:
    df = pd.read_parquet(inp, columns=READ_COLS)
    for c in CATEGORY_COLS:
        df[c] = df[c].astype("category")
    df = add_submission_fields(df)
    labeled = simulate(df, target_rate=target_rate)
    labeled[KEEP_COLS].to_parquet(out, index=False)
    return labeled


def print_report(labeled: pd.DataFrame, out: Path) -> None:
    n = len(labeled)
    print("claim_labels report\n")
    print(f"claims labeled: {n:,}")
    print(f"base_logit used: {labeled.attrs['base_logit']:.3f}")
    print(f"overall denial rate: {labeled['is_denied'].mean():.3%}")
    print("\ndenial rate by claim type:")
    by_type = labeled.groupby("claim_type", observed=True)["is_denied"].agg(["mean", "sum", "size"])
    print(by_type.rename(columns={"mean": "rate", "sum": "denied", "size": "claims"}).to_string())
    print("\ndenial reasons (share of denied claims):")
    print(labeled["carc_code"].value_counts(normalize=True).round(4).to_string())
    denied = labeled["is_denied"] == 1
    dollar_share = labeled.loc[denied, "amount"].sum() / labeled["amount"].sum()
    print(f"\ndollars denied / total dollars: {dollar_share:.3%}")
    print(f"days_to_file > 90: {(labeled['days_to_file'] > 90).mean():.2%}")
    print(f"auth required: {labeled['auth_required'].mean():.2%}")
    missing_auth = (labeled["auth_required"] & ~labeled["auth_on_file"]).mean()
    print(f"authorization missing: {missing_auth:.2%}")
    print(f"coverage inactive: {(~labeled['coverage_active']).mean():.2%}")
    print("\nclaims triggering each rule (share of all claims):")
    for name, count in labeled.attrs["trigger_counts"].items():
        print(f"  {name:<26}{count:>10,}  {count / n:>8.2%}")
    y = labeled["is_denied"].to_numpy()
    p = labeled["p_denial_true"].to_numpy()
    k = int(n * 0.10)
    top = np.argsort(-p)[:k]
    print(f"\noracle ROC-AUC (true probability vs label): {roc_auc(y, p):.3f}")
    print("  upper bound for any model; hidden rules, provider effects and noise sit inside it")
    print(f"oracle top 10%: precision {y[top].mean():.3f}, recall {y[top].sum() / y.sum():.3f}")
    print(f"\nwrote labels to {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=IN_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--target-rate", type=float, default=0.10)
    args = ap.parse_args()
    labeled = run(args.inp, args.out, args.target_rate)
    print_report(labeled, args.out)


if __name__ == "__main__":
    main()

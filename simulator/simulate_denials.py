"""Apply versioned denial rules to a claims table and produce simulated labels.

Required input columns:
    claim_id, bene_id, provider_id, claim_type, from_dt, procedure_code, primary_dx,
    n_lines, amount, days_to_file, auth_required, auth_on_file, coverage_active

Output adds:
    is_denied, carc_code, denial_rule_id, p_denial_true

Note: p_denial_true and denial_rule_id are LEAKAGE columns. Never feed them to a model.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

DEFAULT_RULES = Path(__file__).with_name("denial_rules.yaml")
LEAKAGE_COLUMNS = ["p_denial_true", "denial_rule_id"]
REQUIRED_COLUMNS = [
    "claim_id",
    "bene_id",
    "provider_id",
    "claim_type",
    "from_dt",
    "procedure_code",
    "primary_dx",
    "n_lines",
    "amount",
    "days_to_file",
    "auth_required",
    "auth_on_file",
    "coverage_active",
]


def load_rules(path: Path = DEFAULT_RULES) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    for name, rule in cfg["rules"].items():
        for key in ("carc", "effect", "observable"):
            if key not in rule:
                raise ValueError(f"rule '{name}' is missing '{key}'")
    return cfg


def _trigger_matrix(df: pd.DataFrame, cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    rules = cfg["rules"]
    t = pd.DataFrame(index=df.index)

    p = rules["timely_filing"]["params"]
    t["timely_filing"] = df["days_to_file"] > p["max_days_to_file"]

    t["missing_authorization"] = df["auth_required"].astype(bool) & ~df["auth_on_file"].astype(bool)

    dup_key = ["bene_id", "provider_id", "from_dt", "procedure_code", "primary_dx"]
    known_procedure = df["procedure_code"].astype(str) != "UNKNOWN"
    t["duplicate_claim"] = df.duplicated(subset=dup_key, keep="first") & known_procedure.to_numpy()

    t["coverage_inactive"] = ~df["coverage_active"].astype(bool)

    q = rules["high_amount_review"]["params"]["amount_quantile"]
    cutoff = df.groupby("claim_type", observed=True)["amount"].transform(lambda s: s.quantile(q))
    t["high_amount_review"] = df["amount"] > cutoff

    unknown = df["procedure_code"].astype(str) == "UNKNOWN"
    t["missing_procedure_code"] = unknown & df["claim_type"].astype(str).ne("inpatient")
    t["many_service_lines"] = df["n_lines"] >= rules["many_service_lines"]["params"]["min_lines"]

    t["dx_procedure_mismatch"] = (
        rng.random(len(df)) < rules["dx_procedure_mismatch"]["params"]["rate"]
    )
    t["missing_information"] = rng.random(len(df)) < rules["missing_information"]["params"]["rate"]
    return t[list(rules.keys())]


def solve_base_logit(logit_without_base: np.ndarray, target_rate: float) -> float:
    """Find the base logit that makes the mean denial probability equal target_rate."""
    lo, hi = -25.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        rate = (1.0 / (1.0 + np.exp(-(logit_without_base + mid)))).mean()
        if rate < target_rate:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def simulate(
    df: pd.DataFrame, cfg: dict | None = None, target_rate: float | None = None
) -> pd.DataFrame:
    """Simulate denial labels. If target_rate is given, base_logit is calibrated to hit it."""
    cfg = cfg or load_rules()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    rng = np.random.default_rng(cfg["seed"])
    out = df.copy()
    triggers = _trigger_matrix(out, cfg, rng)

    names = list(cfg["rules"].keys())
    effects = np.array([cfg["rules"][n]["effect"] for n in names])
    logit0 = triggers.to_numpy().astype(float) @ effects

    codes, uniques = pd.factorize(out["provider_id"])
    draws = rng.normal(0, cfg["provider_effect_sd"], len(uniques))
    logit0 = logit0 + np.where(codes >= 0, draws[np.maximum(codes, 0)], 0.0)
    logit0 = logit0 + rng.normal(0, cfg["noise_sd"], len(out))

    base = solve_base_logit(logit0, target_rate) if target_rate else cfg["base_logit"]
    p = 1.0 / (1.0 + np.exp(-(logit0 + base)))
    denied = rng.random(len(out)) < p

    weighted = triggers.to_numpy() * effects
    top = weighted.argmax(axis=1)
    any_trigger = triggers.to_numpy().any(axis=1)
    rule_ids = np.where(any_trigger, np.array(names)[top], "random_other")
    carc_lookup = {n: cfg["rules"][n]["carc"] for n in names}
    carc_lookup["random_other"] = "CO-16"

    rule_col = np.full(len(out), None, dtype=object)
    rule_col[denied] = rule_ids[denied]
    out["p_denial_true"] = p
    out["is_denied"] = denied.astype(int)
    out["denial_rule_id"] = rule_col
    out["carc_code"] = out["denial_rule_id"].map(carc_lookup)
    out.attrs["base_logit"] = float(base)
    out.attrs["trigger_counts"] = {n: int(c) for n, c in triggers.sum().items()}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rules", default=str(DEFAULT_RULES))
    args = ap.parse_args()

    df = pd.read_parquet(args.inp)
    labeled = simulate(df, load_rules(Path(args.rules)))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(args.out, index=False)
    print(f"rows={len(labeled):,} denial_rate={labeled['is_denied'].mean():.3f}")
    print(labeled["carc_code"].value_counts(dropna=True).to_string())


if __name__ == "__main__":
    main()

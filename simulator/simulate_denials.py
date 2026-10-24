"""Apply versioned denial rules to a claims table and produce simulated labels.

Required input columns:
    claim_id, bene_id, provider_id, claim_type, from_dt, procedure_code,
    amount, days_to_file, auth_required, auth_on_file, coverage_active

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

    dup_key = ["bene_id", "provider_id", "from_dt", "procedure_code"]
    t["duplicate_claim"] = df.duplicated(subset=dup_key, keep="first")

    t["coverage_inactive"] = ~df["coverage_active"].astype(bool)

    q = rules["high_amount_review"]["params"]["amount_quantile"]
    cutoff = df.groupby("claim_type")["amount"].transform(lambda s: s.quantile(q))
    t["high_amount_review"] = df["amount"] > cutoff

    t["dx_procedure_mismatch"] = (
        rng.random(len(df)) < rules["dx_procedure_mismatch"]["params"]["rate"]
    )
    t["missing_information"] = rng.random(len(df)) < rules["missing_information"]["params"]["rate"]
    return t[list(rules.keys())]


def simulate(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_rules()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    rng = np.random.default_rng(cfg["seed"])
    out = df.copy()
    triggers = _trigger_matrix(out, cfg, rng)

    names = list(cfg["rules"].keys())
    effects = np.array([cfg["rules"][n]["effect"] for n in names])
    logit = cfg["base_logit"] + triggers.to_numpy().astype(float) @ effects

    providers = out["provider_id"].astype(str).unique()
    draws = rng.normal(0, cfg["provider_effect_sd"], len(providers))
    prov_effect = dict(zip(providers, draws, strict=True))
    logit = logit + out["provider_id"].astype(str).map(prov_effect).to_numpy()
    logit = logit + rng.normal(0, cfg["noise_sd"], len(out))

    p = 1.0 / (1.0 + np.exp(-logit))
    denied = rng.random(len(out)) < p

    weighted = triggers.to_numpy() * effects
    top = weighted.argmax(axis=1)
    any_trigger = triggers.to_numpy().any(axis=1)
    rule_ids = np.where(any_trigger, np.array(names)[top], "random_other")
    carc_lookup = {n: cfg["rules"][n]["carc"] for n in names}
    carc_lookup["random_other"] = "CO-16"

    out["p_denial_true"] = p
    out["is_denied"] = denied.astype(int)
    out["denial_rule_id"] = np.where(denied, rule_ids, None)
    out["carc_code"] = out["denial_rule_id"].map(carc_lookup)
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

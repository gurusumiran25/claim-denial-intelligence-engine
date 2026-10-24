"""Generate a small FAKE claims table with the same columns the simulator expects.

Purpose: let you build the simulator, EDA and tests in Week 1 before real DE-SynPUF /
Synthea data is loaded. Not a substitute for real data. Never use toy output in results.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

CLAIM_TYPES = ["inpatient", "outpatient", "carrier"]
TYPE_P = [0.08, 0.37, 0.55]
TYPE_AMOUNT_MU = {"inpatient": 9.0, "outpatient": 6.2, "carrier": 4.8}  # lognormal means


def make_toy_claims(n: int = 20000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    claim_type = rng.choice(CLAIM_TYPES, size=n, p=TYPE_P)
    mu = pd.Series(claim_type).map(TYPE_AMOUNT_MU).to_numpy()
    amount = np.round(rng.lognormal(mu, 0.8), 2)

    start = pd.Timestamp("2008-01-01")
    from_dt = start + pd.to_timedelta(rng.integers(0, 3 * 365, size=n), unit="D")

    n_prov, n_bene = 300, 3000
    procs = np.array([f"HCPCS_{i:03d}" for i in range(40)])

    auth_required = (claim_type == "inpatient") | (amount > np.quantile(amount, 0.9))
    auth_required = auth_required | (rng.random(n) < 0.05)
    auth_on_file = np.where(auth_required, rng.random(n) < 0.85, True)

    df = pd.DataFrame(
        {
            "claim_id": [f"CLM{i:07d}" for i in range(n)],
            "bene_id": [f"B{b:05d}" for b in rng.integers(0, n_bene, size=n)],
            "provider_id": [f"P{p:04d}" for p in rng.integers(0, n_prov, size=n)],
            "claim_type": claim_type,
            "from_dt": from_dt,
            "procedure_code": rng.choice(procs, size=n),
            "amount": amount,
            "days_to_file": np.minimum(rng.exponential(25, size=n).round().astype(int), 365),
            "auth_required": auth_required,
            "auth_on_file": auth_on_file,
            "coverage_active": rng.random(n) > 0.02,
        }
    )
    # inject some true duplicates (about 1 percent)
    dups = df.sample(frac=0.01, random_state=seed).copy()
    dups["claim_id"] = [f"DUP{i:06d}" for i in range(len(dups))]
    return pd.concat([df, dups], ignore_index=True).sort_values("from_dt").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    df = make_toy_claims(args.n)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"wrote {len(df):,} toy claims to {args.out}")


if __name__ == "__main__":
    main()

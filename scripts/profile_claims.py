"""Profile the raw DE-SynPUF claim files. Reads only the columns it needs.

Run from the project root with the venv active:
    python scripts\\profile_claims.py | Out-File -Encoding utf8 docs\\raw_profile.txt

The report has counts, key checks and distributions only (no patient-level rows).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/desynpuf")
CHUNK = 250_000
SLOTS = range(1, 14)
PCTS = [0, 25, 50, 75, 90, 95, 99, 100]


def hashes(s: pd.Series) -> np.ndarray:
    return pd.util.hash_pandas_object(s.astype(str), index=False).to_numpy()


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def show_amounts(label: str, amount: np.ndarray) -> None:
    q = np.percentile(amount, PCTS)
    print(f"  {label} percentiles {PCTS}: {[round(float(x), 2) for x in q]}")
    print(f"  {label} share equal to 0: {(amount == 0).mean():.3f}   total: {amount.sum():,.0f}")


def profile_facility(name: str, path: Path, extra: list[str]) -> np.ndarray:
    cols = [
        "DESYNPUF_ID",
        "CLM_ID",
        "CLM_FROM_DT",
        "CLM_THRU_DT",
        "PRVDR_NUM",
        "CLM_PMT_AMT",
        "AT_PHYSN_NPI",
        "ICD9_DGNS_CD_1",
        "ICD9_PRCDR_CD_1",
        "HCPCS_CD_1",
    ] + extra
    df = pd.read_csv(path, usecols=cols, dtype=str)
    ids = hashes(df["CLM_ID"])
    print(f"\n=== {name} ({path.name}) ===")
    print(f"  rows: {len(df):,}   unique CLM_ID: {len(np.unique(ids)):,}")
    print(f"  duplicate CLM_ID rows: {len(df) - len(np.unique(ids)):,}")
    if "SEGMENT" in df:
        print(f"  SEGMENT values: {df['SEGMENT'].value_counts(dropna=False).to_dict()}")
        key = hashes(df["CLM_ID"] + "|" + df["SEGMENT"].fillna(""))
        print(f"  unique (CLM_ID, SEGMENT): {len(np.unique(key)):,}")
    print(f"  unique members: {df['DESYNPUF_ID'].nunique():,}")
    print(f"  unique PRVDR_NUM: {df['PRVDR_NUM'].nunique():,}")
    dates = num(df["CLM_FROM_DT"])
    print(f"  CLM_FROM_DT min/max: {dates.min():.0f} / {dates.max():.0f}")
    print("  null rate by column (%):")
    for c in cols:
        print(f"    {c}: {df[c].isna().mean() * 100:.1f}")
    show_amounts("CLM_PMT_AMT", num(df["CLM_PMT_AMT"]).fillna(0).to_numpy())
    return np.unique(ids)


def profile_carrier(paths: list[Path]) -> np.ndarray:
    amt_cols = [f"LINE_NCH_PMT_AMT_{i}" for i in SLOTS]
    hcpcs_cols = [f"HCPCS_CD_{i}" for i in SLOTS]
    cols = (
        [
            "DESYNPUF_ID",
            "CLM_ID",
            "CLM_FROM_DT",
            "CLM_THRU_DT",
            "ICD9_DGNS_CD_1",
            "TAX_NUM_1",
            "PRF_PHYSN_NPI_1",
        ]
        + hcpcs_cols
        + amt_cols
    )
    id_parts: list[np.ndarray] = []
    amounts: list[np.ndarray] = []
    n_lines: list[np.ndarray] = []
    benes: set[str] = set()
    tax: set[str] = set()
    npi: set[str] = set()
    nulls = dict.fromkeys(cols[:7], 0)
    rows = 0
    dmin, dmax = np.inf, -np.inf
    for path in paths:
        for chunk in pd.read_csv(path, usecols=cols, dtype=str, chunksize=CHUNK):
            rows += len(chunk)
            id_parts.append(hashes(chunk["CLM_ID"]))
            amt = chunk[amt_cols].apply(num).fillna(0).sum(axis=1)
            amounts.append(amt.to_numpy(dtype="float32"))
            n_lines.append(chunk[hcpcs_cols].notna().sum(axis=1).to_numpy(dtype="int8"))
            benes.update(chunk["DESYNPUF_ID"].dropna().unique())
            tax.update(chunk["TAX_NUM_1"].dropna().unique())
            npi.update(chunk["PRF_PHYSN_NPI_1"].dropna().unique())
            for c in nulls:
                nulls[c] += int(chunk[c].isna().sum())
            d = num(chunk["CLM_FROM_DT"])
            dmin, dmax = min(dmin, d.min()), max(dmax, d.max())
    ids = np.concatenate(id_parts)
    uniq = np.unique(ids)
    amount = np.concatenate(amounts)
    lines = np.concatenate(n_lines)
    print(f"\n=== carrier ({', '.join(p.name for p in paths)}) ===")
    print(f"  rows: {rows:,}   unique CLM_ID: {len(uniq):,}   duplicates: {rows - len(uniq):,}")
    print(f"  unique members: {len(benes):,}")
    print(f"  unique TAX_NUM_1: {len(tax):,}   unique PRF_PHYSN_NPI_1: {len(npi):,}")
    print(f"  CLM_FROM_DT min/max: {dmin:.0f} / {dmax:.0f}")
    print("  null rate by column (%):")
    for c, n in nulls.items():
        print(f"    {c}: {n / rows * 100:.1f}")
    counts = pd.Series(lines).value_counts().sort_index()
    print(f"  service lines used per claim (count of claims): {counts.to_dict()}")
    print(f"  mean lines per claim: {lines.mean():.2f}")
    show_amounts("sum(LINE_NCH_PMT_AMT_1..13)", amount.astype("float64"))
    return uniq


def main() -> None:
    inpatient = RAW / "DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv"
    outpatient = RAW / "DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv"
    carrier = [
        RAW / "DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.csv",
        RAW / "DE1_0_2008_to_2010_Carrier_Claims_Sample_1B.csv",
    ]
    ip = profile_facility("inpatient", inpatient, ["SEGMENT", "CLM_DRG_CD", "CLM_UTLZTN_DAY_CNT"])
    op = profile_facility("outpatient", outpatient, ["SEGMENT"])
    car = profile_carrier(carrier)
    print("\n=== CLM_ID overlap across claim types (should be 0) ===")
    print(f"  inpatient & outpatient: {len(np.intersect1d(ip, op)):,}")
    print(f"  inpatient & carrier:    {len(np.intersect1d(ip, car)):,}")
    print(f"  outpatient & carrier:   {len(np.intersect1d(op, car)):,}")
    total = len(ip) + len(op) + len(car)
    print(f"\nTotal unique claims across types: {total:,}")


if __name__ == "__main__":
    main()

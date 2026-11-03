"""Check what SEGMENT 2 rows are in the inpatient and outpatient claim files.

Run from the project root with the venv active:
    python scripts\\check_segments.py | Out-File -Encoding utf8 docs\\segment_check.txt

Output is counts and summaries only (no patient-level rows).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW = Path("data/raw/desynpuf")
FILES = {
    "inpatient": "DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv",
    "outpatient": "DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv",
}
COLS = [
    "DESYNPUF_ID",
    "CLM_ID",
    "SEGMENT",
    "CLM_FROM_DT",
    "CLM_THRU_DT",
    "PRVDR_NUM",
    "CLM_PMT_AMT",
    "ICD9_DGNS_CD_1",
]
SAME_AS_PARTNER = ["DESYNPUF_ID", "PRVDR_NUM", "CLM_FROM_DT", "ICD9_DGNS_CD_1"]


def main() -> None:
    for name, fname in FILES.items():
        df = pd.read_csv(RAW / fname, usecols=COLS, dtype=str)
        df["amt"] = pd.to_numeric(df["CLM_PMT_AMT"], errors="coerce")
        df["null_from_dt"] = df["CLM_FROM_DT"].isna()
        s1 = df[df["SEGMENT"] == "1"]
        s2 = df[df["SEGMENT"] == "2"]
        print(f"\n=== {name} ===")
        print("rows by SEGMENT x (CLM_FROM_DT is null):")
        print(pd.crosstab(df["SEGMENT"], df["null_from_dt"]).to_string())
        has_partner = s2["CLM_ID"].isin(s1["CLM_ID"])
        print(f"segment 2 rows: {len(s2):,}; with a segment 1 partner: {has_partner.sum():,}")
        pairs = s2.merge(s1, on="CLM_ID", suffixes=("_2", "_1"))
        print(f"matched pairs: {len(pairs):,}")
        for c in SAME_AS_PARTNER:
            if len(pairs):
                same = (pairs[f"{c}_2"] == pairs[f"{c}_1"]).mean()
                print(f"  share of pairs with identical {c}: {same:.3f}")
        for label, part in (("segment 1", s1), ("segment 2", s2)):
            a = part["amt"]
            print(f"  {label} CLM_PMT_AMT: mean {a.mean():.1f}, median {a.median():.1f}")
            print(f"    share zero {(a == 0).mean():.3f}, share negative {(a < 0).mean():.3f}")
        print("  segment 2 null rate by column (%):")
        for c in COLS:
            if len(s2):
                print(f"    {c}: {s2[c].isna().mean() * 100:.1f}")


if __name__ == "__main__":
    main()

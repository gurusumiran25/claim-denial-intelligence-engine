"""Build the modeling table `claims_unified` from the 7 raw DE-SynPUF Sample 1 files.

Rules (see docs/decisions.md ADR-006 to ADR-008 and docs/data_dictionary.md):
  - inpatient and outpatient: keep SEGMENT 1 only
  - keep claims with from_dt between 2008-01-01 and 2010-12-31
  - keep claims with amount > 0
  - claim_id = CLM_ID, provider_id = "F:" + PRVDR_NUM (facility) or "T:" + TAX_NUM_1 (carrier)
  - coverage_active is derived from the beneficiary files (Part A months for inpatient,
    Part B months for outpatient and carrier, and not after the death date)

Run from the project root with the venv active:
    python -m ingestion.build_claims_unified | Out-File -Encoding utf8 docs\\build_report.txt

Quick test on a small slice of the carrier files:
    python -m ingestion.build_claims_unified --max-chunks 1
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

RAW_DEFAULT = Path("data/raw/desynpuf")
OUT_DEFAULT = Path("data/processed/claims_unified.parquet")
CHUNK = 250_000
WINDOW_START = pd.Timestamp("2008-01-01")
WINDOW_END = pd.Timestamp("2010-12-31")
YEARS = (2008, 2009, 2010)
SLOTS = range(1, 14)

SCHEMA = pa.schema(
    [
        ("claim_id", pa.string()),
        ("claim_type", pa.string()),
        ("bene_id", pa.string()),
        ("provider_id", pa.string()),
        ("rendering_npi", pa.string()),
        ("from_dt", pa.timestamp("ns")),
        ("thru_dt", pa.timestamp("ns")),
        ("primary_dx", pa.string()),
        ("procedure_code", pa.string()),
        ("drg_code", pa.string()),
        ("los_days", pa.float64()),
        ("n_lines", pa.int16()),
        ("amount", pa.float64()),
        ("age_at_claim", pa.float64()),
        ("sex", pa.string()),
        ("coverage_active", pa.bool_()),
    ]
)

COUNT_KEYS = [
    "raw_rows",
    "dropped_segment2",
    "dropped_bad_date",
    "dropped_outside_window",
    "dropped_amount_missing",
    "dropped_amount_negative",
    "dropped_amount_zero",
    "kept",
    "not_in_beneficiary_file",
    "coverage_inactive",
    "duplicate_claim_ids",
]


def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%Y%m%d", errors="coerce")


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def new_counts() -> dict[str, int]:
    return dict.fromkeys(COUNT_KEYS, 0)


def load_beneficiaries(raw: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = [
        "DESYNPUF_ID",
        "BENE_BIRTH_DT",
        "BENE_DEATH_DT",
        "BENE_SEX_IDENT_CD",
        "BENE_HI_CVRAGE_TOT_MONS",
        "BENE_SMI_CVRAGE_TOT_MONS",
    ]
    parts = []
    for year in YEARS:
        path = raw / f"DE1_0_{year}_Beneficiary_Summary_File_Sample_1.csv"
        df = pd.read_csv(path, usecols=cols, dtype=str)
        df["year"] = year
        parts.append(df)
    allb = pd.concat(parts, ignore_index=True).rename(columns={"DESYNPUF_ID": "bene_id"})
    allb["hi_mons"] = num(allb["BENE_HI_CVRAGE_TOT_MONS"])
    allb["smi_mons"] = num(allb["BENE_SMI_CVRAGE_TOT_MONS"])
    allb["birth_dt"] = to_date(allb["BENE_BIRTH_DT"])
    allb["death_dt"] = to_date(allb["BENE_DEATH_DT"])
    bene_year = allb[["bene_id", "year", "hi_mons", "smi_mons"]].drop_duplicates(
        ["bene_id", "year"]
    )
    static = (
        allb.groupby("bene_id")
        .agg(
            birth_dt=("birth_dt", "min"),
            death_dt=("death_dt", "min"),
            sex=("BENE_SEX_IDENT_CD", "first"),
        )
        .reset_index()
    )
    return bene_year, static


def standardize_facility(df: pd.DataFrame, claim_type: str) -> pd.DataFrame:
    inpatient = claim_type == "inpatient"
    if inpatient:
        procedure = df["ICD9_PRCDR_CD_1"]
        n_lines = pd.Series(1, index=df.index)
        drg = df["CLM_DRG_CD"]
        los = num(df["CLM_UTLZTN_DAY_CNT"])
    else:
        procedure = df["HCPCS_CD_1"]
        hcpcs = [f"HCPCS_CD_{i}" for i in range(1, 46)]
        n_lines = df[hcpcs].notna().sum(axis=1)
        drg = pd.Series(None, index=df.index, dtype="object")
        los = pd.Series(np.nan, index=df.index)
    prefix = df["PRVDR_NUM"].map(lambda v: None if pd.isna(v) else f"F:{v}")
    return pd.DataFrame(
        {
            "claim_id": df["CLM_ID"],
            "claim_type": claim_type,
            "bene_id": df["DESYNPUF_ID"],
            "provider_id": prefix,
            "rendering_npi": df["AT_PHYSN_NPI"],
            "from_dt": to_date(df["CLM_FROM_DT"]),
            "thru_dt": to_date(df["CLM_THRU_DT"]),
            "primary_dx": df["ICD9_DGNS_CD_1"],
            "procedure_code": procedure.fillna("UNKNOWN"),
            "drg_code": drg,
            "los_days": los,
            "n_lines": n_lines.astype("int16"),
            "amount": num(df["CLM_PMT_AMT"]),
        }
    )


def standardize_carrier(df: pd.DataFrame) -> pd.DataFrame:
    amt_cols = [f"LINE_NCH_PMT_AMT_{i}" for i in SLOTS]
    hcpcs_cols = [f"HCPCS_CD_{i}" for i in SLOTS]
    amount = df[amt_cols].apply(num).fillna(0).sum(axis=1)
    prefix = df["TAX_NUM_1"].map(lambda v: None if pd.isna(v) else f"T:{v}")
    return pd.DataFrame(
        {
            "claim_id": df["CLM_ID"],
            "claim_type": "carrier",
            "bene_id": df["DESYNPUF_ID"],
            "provider_id": prefix,
            "rendering_npi": df["PRF_PHYSN_NPI_1"],
            "from_dt": to_date(df["CLM_FROM_DT"]),
            "thru_dt": to_date(df["CLM_THRU_DT"]),
            "primary_dx": df["ICD9_DGNS_CD_1"],
            "procedure_code": df["HCPCS_CD_1"].fillna("UNKNOWN"),
            "drg_code": pd.Series(None, index=df.index, dtype="object"),
            "los_days": pd.Series(np.nan, index=df.index),
            "n_lines": df[hcpcs_cols].notna().sum(axis=1).astype("int16"),
            "amount": amount,
        }
    )


def apply_filters(df: pd.DataFrame, counts: dict[str, int]) -> pd.DataFrame:
    bad = df["from_dt"].isna()
    counts["dropped_bad_date"] += int(bad.sum())
    df = df[~bad]
    outside = (df["from_dt"] < WINDOW_START) | (df["from_dt"] > WINDOW_END)
    counts["dropped_outside_window"] += int(outside.sum())
    df = df[~outside]
    missing = df["amount"].isna()
    counts["dropped_amount_missing"] += int(missing.sum())
    df = df[~missing]
    negative = df["amount"] < 0
    counts["dropped_amount_negative"] += int(negative.sum())
    df = df[~negative]
    zero = df["amount"] == 0
    counts["dropped_amount_zero"] += int(zero.sum())
    df = df[~zero]
    counts["kept"] += len(df)
    return df


def add_member_fields(
    df: pd.DataFrame, bene_year: pd.DataFrame, static: pd.DataFrame, counts: dict[str, int]
) -> pd.DataFrame:
    df = df.copy()
    df["year"] = df["from_dt"].dt.year
    df = df.merge(bene_year, on=["bene_id", "year"], how="left", indicator=True)
    df = df.merge(static, on="bene_id", how="left")
    in_file = df["_merge"] == "both"
    months = np.where(df["claim_type"].eq("inpatient"), df["hi_mons"], df["smi_mons"])
    alive = df["death_dt"].isna() | (df["death_dt"] >= df["from_dt"])
    df["coverage_active"] = (in_file & (months > 0) & alive).to_numpy()
    df["age_at_claim"] = (df["from_dt"] - df["birth_dt"]).dt.days / 365.25
    counts["not_in_beneficiary_file"] += int((~in_file).sum())
    counts["coverage_inactive"] += int((~df["coverage_active"]).sum())
    return df[SCHEMA.names]


def write_batch(writer: pq.ParquetWriter, df: pd.DataFrame) -> None:
    writer.write_table(pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False))


def read_facility(raw: Path, claim_type: str) -> tuple[pd.DataFrame, dict[str, int]]:
    counts = new_counts()
    fname = f"DE1_0_2008_to_2010_{claim_type.capitalize()}_Claims_Sample_1.csv"
    cols = [
        "DESYNPUF_ID",
        "CLM_ID",
        "SEGMENT",
        "CLM_FROM_DT",
        "CLM_THRU_DT",
        "PRVDR_NUM",
        "CLM_PMT_AMT",
        "AT_PHYSN_NPI",
        "ICD9_DGNS_CD_1",
        "ICD9_PRCDR_CD_1",
    ]
    if claim_type == "inpatient":
        cols += ["CLM_DRG_CD", "CLM_UTLZTN_DAY_CNT"]
    else:
        cols += [f"HCPCS_CD_{i}" for i in range(1, 46)]
    df = pd.read_csv(raw / fname, usecols=cols, dtype=str)
    counts["raw_rows"] = len(df)
    seg2 = df["SEGMENT"] != "1"
    counts["dropped_segment2"] = int(seg2.sum())
    df = df[~seg2]
    counts["duplicate_claim_ids"] = int(df["CLM_ID"].duplicated().sum())
    return standardize_facility(df, claim_type), counts


def build(raw: Path, out: Path, max_chunks: int | None = None) -> dict[str, dict[str, int]]:
    bene_year, static = load_beneficiaries(raw)
    out.parent.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, int]] = {}
    with pq.ParquetWriter(out, SCHEMA) as writer:
        for claim_type in ("inpatient", "outpatient"):
            std, counts = read_facility(raw, claim_type)
            kept = apply_filters(std, counts)
            write_batch(writer, add_member_fields(kept, bene_year, static, counts))
            results[claim_type] = counts

        counts = new_counts()
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
            + [f"HCPCS_CD_{i}" for i in SLOTS]
            + [f"LINE_NCH_PMT_AMT_{i}" for i in SLOTS]
        )
        for part in ("A", "B"):
            path = raw / f"DE1_0_2008_to_2010_Carrier_Claims_Sample_1{part}.csv"
            reader = pd.read_csv(path, usecols=cols, dtype=str, chunksize=CHUNK)
            for i, chunk in enumerate(reader):
                if max_chunks is not None and i >= max_chunks:
                    break
                counts["raw_rows"] += len(chunk)
                kept = apply_filters(standardize_carrier(chunk), counts)
                write_batch(writer, add_member_fields(kept, bene_year, static, counts))
        results["carrier"] = counts
    return results


def print_report(results: dict[str, dict[str, int]], out: Path) -> None:
    print("claims_unified build report\n")
    print(f"{'step':<28}" + "".join(f"{k:>14}" for k in results) + f"{'total':>14}")
    for key in COUNT_KEYS:
        vals = [results[k][key] for k in results]
        print(f"{key:<28}" + "".join(f"{v:>14,}" for v in vals) + f"{sum(vals):>14,}")
    kept = sum(r["kept"] for r in results.values())
    inactive = sum(r["coverage_inactive"] for r in results.values())
    missing = sum(r["not_in_beneficiary_file"] for r in results.values())
    print(f"\nwrote {kept:,} claims to {out}")
    if kept:
        print(f"coverage_active = False for {inactive / kept:.1%} of kept claims")
        print(f"member not in that year's beneficiary file: {missing / kept:.1%} of kept claims")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=RAW_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--max-chunks", type=int, default=None, help="limit carrier chunks (testing)")
    args = ap.parse_args()
    print_report(build(args.raw, args.out, args.max_chunks), args.out)


if __name__ == "__main__":
    main()

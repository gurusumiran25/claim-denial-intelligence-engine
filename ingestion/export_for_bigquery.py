"""Write BigQuery-ready Parquet files into data/bigquery/.

  claims_unified.parquet  from data/processed/claims_unified.parquet (dates become DATE)
  claim_labels.parquet    from data/processed/claim_labels.parquet
  bene_year.parquet       member-year table built from the 3 beneficiary CSVs

Run from the project root with the venv active:
    python -m ingestion.export_for_bigquery
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

PROCESSED = Path("data/processed")
RAW = Path("data/raw/desynpuf")
OUT = Path("data/bigquery")
YEARS = (2008, 2009, 2010)

BENE_RENAME = {
    "DESYNPUF_ID": "bene_id",
    "BENE_BIRTH_DT": "birth_dt",
    "BENE_DEATH_DT": "death_dt",
    "BENE_SEX_IDENT_CD": "sex",
    "BENE_RACE_CD": "race",
    "BENE_ESRD_IND": "esrd_ind",
    "SP_STATE_CODE": "state_code",
    "BENE_COUNTY_CD": "county_cd",
    "BENE_HI_CVRAGE_TOT_MONS": "hi_mons",
    "BENE_SMI_CVRAGE_TOT_MONS": "smi_mons",
    "BENE_HMO_CVRAGE_TOT_MONS": "hmo_mons",
    "PLAN_CVRG_MOS_NUM": "plan_mons",
    "SP_ALZHDMTA": "sp_alzheimer",
    "SP_CHF": "sp_chf",
    "SP_CHRNKIDN": "sp_kidney",
    "SP_CNCR": "sp_cancer",
    "SP_COPD": "sp_copd",
    "SP_DEPRESSN": "sp_depression",
    "SP_DIABETES": "sp_diabetes",
    "SP_ISCHMCHT": "sp_ischemic_heart",
    "SP_OSTEOPRS": "sp_osteoporosis",
    "SP_RA_OA": "sp_ra_oa",
    "SP_STRKETIA": "sp_stroke",
}
DATE_COLS = ["birth_dt", "death_dt"]
STRING_COLS = ["bene_id", "sex", "race", "esrd_ind", "state_code", "county_cd"]
INT_COLS = [c for c in BENE_RENAME.values() if c not in DATE_COLS + STRING_COLS]


def cast_dates(table: pa.Table, cols: list[str]) -> pa.Table:
    for name in cols:
        idx = table.schema.get_field_index(name)
        table = table.set_column(idx, name, pc.cast(table[name], pa.date32()))
    return table


def export_claims(out: Path) -> int:
    table = cast_dates(pq.read_table(PROCESSED / "claims_unified.parquet"), ["from_dt", "thru_dt"])
    pq.write_table(table, out / "claims_unified.parquet", compression="snappy")
    return table.num_rows


def export_labels(out: Path) -> int:
    table = pq.read_table(PROCESSED / "claim_labels.parquet")
    pq.write_table(table, out / "claim_labels.parquet", compression="snappy")
    return table.num_rows


def build_bene_year(raw: Path) -> pd.DataFrame:
    parts = []
    for year in YEARS:
        path = raw / f"DE1_0_{year}_Beneficiary_Summary_File_Sample_1.csv"
        df = pd.read_csv(path, usecols=list(BENE_RENAME), dtype=str).rename(columns=BENE_RENAME)
        df.insert(1, "year", year)
        parts.append(df)
    df = pd.concat(parts, ignore_index=True)
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], format="%Y%m%d", errors="coerce")
    for c in INT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int16")
    df["year"] = df["year"].astype("Int16")
    return df


def export_bene_year(out: Path, raw: Path = RAW) -> int:
    table = pa.Table.from_pandas(build_bene_year(raw), preserve_index=False)
    table = cast_dates(table, DATE_COLS)
    pq.write_table(table, out / "bene_year.parquet", compression="snappy")
    return table.num_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = {
        "claims_unified": export_claims,
        "claim_labels": export_labels,
        "bene_year": export_bene_year,
    }
    for name, fn in jobs.items():
        rows = fn(args.out)
        size = (args.out / f"{name}.parquet").stat().st_size / 1e6
        print(f"{name}: {rows:,} rows, {size:,.1f} MB")


if __name__ == "__main__":
    main()

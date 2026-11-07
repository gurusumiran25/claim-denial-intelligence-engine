"""Download the dbt feature table from BigQuery into a local Parquet file.

Run from the project root (venv active, gcloud application-default login done):
    python -m src.training.export_features
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.parquet as pq

OUT_DEFAULT = Path("data/processed/features.parquet")


def export(dataset: str, table: str, project: str | None, out: Path) -> int:
    from google.cloud import bigquery  # imported here so tests do not need Google libraries

    client = bigquery.Client(project=project)
    sql = f"SELECT * FROM `{client.project}.{dataset}.{table}`"
    job = client.query(sql)
    try:
        arrow = job.to_arrow(create_bqstorage_client=True)
    except Exception as exc:  # the Storage Read API may be unavailable in the sandbox
        print(f"Storage API not available ({type(exc).__name__}); using the slower REST download")
        arrow = job.to_arrow(create_bqstorage_client=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(arrow, out, compression="snappy")
    return arrow.num_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="claims_analytics")
    ap.add_argument("--table", default="fct_claim_features")
    ap.add_argument("--project", default=None)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    rows = export(args.dataset, args.table, args.project, args.out)
    size = args.out.stat().st_size / 1e6
    print(f"wrote {rows:,} rows to {args.out} ({size:,.1f} MB)")


if __name__ == "__main__":
    main()

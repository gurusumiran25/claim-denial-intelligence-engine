from pathlib import Path

import pandas as pd

RAW = Path("data/raw/desynpuf")
for f in sorted(RAW.glob("*.csv")):
    with open(f, encoding="utf-8", errors="replace") as fh:
        rows = sum(1 for _ in fh) - 1
    cols = pd.read_csv(f, nrows=0).columns.tolist()
    print(f"\n{f.name}\n  rows: {rows:,}\n  columns ({len(cols)}): {cols}")

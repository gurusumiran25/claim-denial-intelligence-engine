"""Write one example draft per denial reason, from real (simulated-denial) claims in the local data.

Run from the project root:
    python -m src.rag.demo
    python -m src.rag.demo --assume-evidence      # demo only: pretends the supporting records exist

Output goes to reports/appeal_examples/. With --assume-evidence the human-supplied flags
(documentation, exception, modifier, eligibility) are set to true so the letters can be shown; every
file then says so at the top. Real use must set these flags only when the evidence really exists.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.rag.appeal import draft
from src.rag.conditions import HUMAN_FLAGS
from src.rag.knowledge import load_notes, load_playbook
from src.rag.retriever import PolicyRetriever

CLAIMS_DEFAULT = Path("data/processed/claims_unified.parquet")
LABELS_DEFAULT = Path("data/processed/claim_labels.parquet")
OUT_DEFAULT = Path("reports/appeal_examples")
LETTER_DATE = "2026-11-09"


def pick_examples(claims_path: Path, labels_path: Path) -> pd.DataFrame:
    """The lowest claim id for each denial reason, with the fields the copilot needs."""
    cols = ["claim_id", "carc_code", "days_to_file", "auth_required", "auth_on_file"]
    labels = pq.read_table(labels_path, columns=["is_denied", *cols])
    denied = labels.filter(pc.equal(labels["is_denied"], 1)).to_pandas().drop(columns="is_denied")
    picked = denied.sort_values("claim_id").groupby("carc_code").head(1)
    claims = pq.read_table(
        claims_path,
        columns=[
            "claim_id",
            "claim_type",
            "from_dt",
            "amount",
            "coverage_active",
            "n_lines",
            "procedure_code",
        ],
        filters=[("claim_id", "in", picked["claim_id"].tolist())],
    ).to_pandas()
    return picked.merge(claims, on="claim_id")


def run(claims_path: Path, labels_path: Path, out_dir: Path, assume_evidence: bool = False) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    notes, playbook = load_notes(), load_playbook()
    retriever = PolicyRetriever(notes)
    index = ["# Example drafts", ""]
    count = 0
    for row in pick_examples(claims_path, labels_path).itertuples():
        if row.carc_code not in playbook:
            continue
        facts = {
            "claim_id": row.claim_id,
            "claim_type": row.claim_type,
            "from_dt": str(row.from_dt)[:10],
            "amount": float(row.amount),
            "days_to_file": int(row.days_to_file),
            "auth_required": bool(row.auth_required),
            "auth_on_file": bool(row.auth_on_file),
            "coverage_active": bool(row.coverage_active),
            "n_lines": int(row.n_lines),
            "procedure_unknown": row.procedure_code == "UNKNOWN",
        }
        if assume_evidence:
            facts.update(dict.fromkeys(HUMAN_FLAGS, True))
        result = draft(facts, row.carc_code, retriever, playbook, letter_date=LETTER_DATE)
        banner = (
            "DEMO ONLY: the supporting evidence flags were set to true to show a complete "
            "letter.\n\n"
            if assume_evidence
            else ""
        )
        path = out_dir / f"{row.carc_code}_{row.claim_id}.md"
        path.write_text(banner + result.document + "\n")
        index.append(f"- {row.carc_code}, claim {row.claim_id}: {result.action_type} ({path.name})")
        count += 1
    (out_dir / "index.md").write_text("\n".join(index) + "\n")
    return count


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", type=Path, default=CLAIMS_DEFAULT)
    ap.add_argument("--labels", type=Path, default=LABELS_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--assume-evidence", action="store_true")
    args = ap.parse_args()
    n = run(args.claims, args.labels, args.out, args.assume_evidence)
    print(f"wrote {n} example drafts to {args.out}")


if __name__ == "__main__":
    main()

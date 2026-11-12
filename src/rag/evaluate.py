"""Evaluate the appeal copilot on the hand-written cases in `knowledge/eval_cases.yaml`.

Run from the project root:
    python -m src.rag.evaluate
Writes reports/rag_eval.md and reports/rag_eval_cases.csv.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.rag.appeal import check_letter, draft
from src.rag.knowledge import KNOWLEDGE_DIR, load_notes, load_playbook, validate
from src.rag.retriever import PolicyRetriever

LETTER_DATE = "2026-11-09"
SECTIONS = (
    "Why the claim was denied",
    "Basis for this request",
    "Requested action",
    "Enclosures",
    "References",
)


def load_cases(path: Path | None = None) -> list[dict]:
    with open(path or KNOWLEDGE_DIR / "eval_cases.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate_cases(cases: list[dict], notes: list[dict], playbook: dict) -> pd.DataFrame:
    retriever = PolicyRetriever(notes)
    known_ids = {n["id"] for n in notes}
    rows = []
    for case in cases:
        facts = {**case["facts"]}
        res = draft(facts, case["reason"], retriever, playbook, letter_date=LETTER_DATE)
        gold = set(case.get("gold_notes", []))
        acceptable = gold | set(case.get("acceptable_notes", []))
        top3 = {nid for t in res.retrieval for nid in t["top3"]}
        hit = bool(gold & top3) if gold else None
        first_top1 = res.retrieval[0]["top3"][0] if res.retrieval else None
        top1_hit = (first_top1 in acceptable) if (gold and first_top1) else None
        cited = {c["id"] for c in res.citations}
        precision = (len(cited & acceptable) / len(cited)) if (gold and cited) else None
        is_letter = res.document_type == "letter"
        grounding = (
            check_letter(res, facts, LETTER_DATE, notes, playbook)
            if is_letter
            else {"missing_facts": [], "stray_numbers": []}
        )
        expect_args = set(case.get("expect_arguments", []))
        forbidden = [
            p for p in case.get("must_not_contain", []) if p.lower() in res.document.lower()
        ]
        rows.append(
            {
                "case": case["id"],
                "reason": case["reason"],
                "expected_action": case["expect_action"],
                "action": res.action_type,
                "action_ok": res.action_type == case["expect_action"],
                "arguments_ok": (set(res.arguments_used) == expect_args)
                if case["expect_action"] == "appeal"
                else None,
                "retrieval_hit_at_3": hit,
                "retrieval_top1_hit": top1_hit,
                "citation_precision": precision,
                "citations_valid": all(c["id"] in known_ids for c in res.citations),
                "has_citation": bool(res.citations),
                "sections_ok": all(s in res.document for s in SECTIONS) if is_letter else None,
                "letter_matches_action": is_letter == (res.action_type == "appeal"),
                "missing_facts": len(grounding["missing_facts"]),
                "stray_numbers": len(grounding["stray_numbers"]),
                "forbidden_phrases": len(forbidden),
            }
        )
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    def rate(col: str) -> float:
        s = df[col].dropna()
        return float(s.mean()) if len(s) else float("nan")

    letters = df["sections_ok"].notna()
    rows = [
        ("Cases", float(len(df))),
        ("Recommended action correct", rate("action_ok")),
        ("Arguments used exactly as expected (appeal cases)", rate("arguments_ok")),
        ("Gold policy note in top 3 retrieved", rate("retrieval_hit_at_3")),
        ("Top-ranked note for the first query is an acceptable note", rate("retrieval_top1_hit")),
        (
            "Share of cited notes that are acceptable notes (citation precision)",
            rate("citation_precision"),
        ),
        ("Every cited note exists in the knowledge base", rate("citations_valid")),
        ("Every draft cites at least one note", rate("has_citation")),
        ("Letters have all required sections", rate("sections_ok")),
        ("Letter produced exactly when action is appeal", rate("letter_matches_action")),
        (
            "Letters with all claim facts present",
            float((df.loc[letters, "missing_facts"] == 0).mean()),
        ),
        ("Letters with no stray numbers", float((df.loc[letters, "stray_numbers"] == 0).mean())),
        (
            "Cases with no forbidden (unsupported) phrase",
            float((df["forbidden_phrases"] == 0).mean()),
        ),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", type=Path, default=Path("reports"))
    args = ap.parse_args()
    notes, playbook = load_notes(), load_playbook()
    problems = validate(notes, playbook)
    if problems:
        raise SystemExit("knowledge files have problems:\n" + "\n".join(problems))
    df = evaluate_cases(load_cases(), notes, playbook)
    summary = summarize(df)
    args.reports.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.reports / "rag_eval_cases.csv", index=False)
    lines = ["# Appeal copilot evaluation", "", "| metric | value |", "|---|---|"]
    for _, r in summary.iterrows():
        v = int(r["value"]) if r["metric"] == "Cases" else f"{r['value']:.1%}"
        lines.append(f"| {r['metric']} | {v} |")
    failed = df[~df["action_ok"]]
    lines += ["", "## Cases where the recommended action was not the expected one"]
    lines += [
        f"- {r.case} ({r.reason}): expected {r.expected_action}, got {r.action}"
        for r in failed.itertuples()
    ] or ["- none"]
    lines += [
        "",
        "Cases are hand-written in `knowledge/eval_cases.yaml`; retrieval is offline TF-IDF over "
        "20 policy notes.",
        "Limits: the cases and the playbook were written by the same author, so this checks the "
        "system against its own design, not against an independent benchmark. 'Acceptable' notes "
        "were assigned after inspecting the "
        "retrieval output. Real denials would need a larger, independently labelled set.",
    ]
    (args.reports / "rag_eval.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

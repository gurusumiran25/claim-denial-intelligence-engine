"""Draft an appeal letter, or a corrected-claim / no-appeal memo, for a denied claim.

Works fully offline: the playbook decides which arguments the claim's facts support, the
retriever finds policy notes for each argument, and an argument without a supporting note is
dropped (cite or abstain). Nothing is invented: every sentence in the letter comes from the
playbook or from the claim's own facts.

Example:
    python -m src.rag.appeal --claim-id C123 --reason CO-29
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import date

from src.rag.conditions import evaluate, normalize_facts
from src.rag.knowledge import load_notes, load_playbook
from src.rag.retriever import MIN_SCORE, PolicyRetriever

DISCLAIMER = (
    "Draft prepared from public Medicare guidance summaries for a synthetic demonstration. "
    "Check every statement against the payer's own contract and policies before sending."
)


@dataclass
class AppealResult:
    claim_id: str
    carc_code: str
    title: str
    action_type: str
    recommendation: str
    document_type: str  # "letter" or "memo"
    document: str
    arguments_used: list[str] = field(default_factory=list)
    arguments_skipped: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    root_cause: dict = field(default_factory=dict)
    retrieval: list[dict] = field(default_factory=list)


class _Refs:
    """Numbers the cited notes in order of first use."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.notes: dict[str, dict] = {}
        self.scores: dict[str, float] = {}

    def mark(self, hits: list[tuple[dict, float]]) -> str:
        marks = []
        for note, score in hits:
            if note["id"] not in self.notes:
                self.order.append(note["id"])
                self.notes[note["id"]] = note
                self.scores[note["id"]] = score
            marks.append(f"[{self.order.index(note['id']) + 1}]")
        return "".join(marks)

    def render(self) -> str:
        lines = []
        for i, nid in enumerate(self.order, start=1):
            note = self.notes[nid]
            sources = "; ".join(f"{s['title']} ({s['url']})" for s in note["sources"])
            lines.append(
                f"[{i}] {note['title']} ({nid}). Sources: {sources}. Accessed {note['accessed']}."
            )
        return "\n".join(lines)

    def as_list(self) -> list[dict]:
        return [
            {
                "id": nid,
                "title": self.notes[nid]["title"],
                "score": round(self.scores[nid], 3),
                "urls": [s["url"] for s in self.notes[nid]["sources"]],
            }
            for nid in self.order
        ]


def _auth_text(f: dict) -> str:
    if not f["auth_required"]:
        return "Not required"
    return "Required, on file" if f["auth_on_file"] else "Required, not on file"


def _claim_table(f: dict) -> str:
    rows = [
        ("Claim ID", f["claim_id"]),
        ("Claim type", f["claim_type"]),
        ("Date of service", f["from_dt"]),
        ("Claim amount", f"${f['amount']:,.2f}"),
        ("Days from service to filing", str(f["days_to_file"])),
        ("Authorization", _auth_text(f)),
        ("Coverage on date of service", "Active" if f["coverage_active"] else "Not active"),
    ]
    return "\n".join(["| Item | Detail |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows])


def _guidance_lines(
    entry: dict, retriever: PolicyRetriever, refs: _Refs, trace: list[dict]
) -> list[str]:
    lines = []
    for step in entry["guidance"]:
        hits = retriever.search(step["query"], k=3)
        trace.append({"query": step["query"], "top3": [n["id"] for n, _ in hits]})
        strong = [(n, s) for n, s in hits[:1] if s >= MIN_SCORE]
        marks = refs.mark(strong)
        lines.append(f"- {step['text']} {marks}".rstrip())
    return lines


def draft(
    raw_facts: dict,
    carc_code: str,
    retriever: PolicyRetriever | None = None,
    playbook: dict | None = None,
    letter_date: str | None = None,
    max_refs: int = 6,
) -> AppealResult:
    facts = normalize_facts(raw_facts)
    playbook = playbook or load_playbook()
    retriever = retriever or PolicyRetriever(load_notes())
    letter_date = letter_date or date.today().isoformat()

    entry = playbook.get(carc_code)
    if entry is None:
        return AppealResult(
            claim_id=facts["claim_id"],
            carc_code=carc_code,
            title="Unknown reason code",
            action_type="no_appeal",
            document_type="memo",
            recommendation="No playbook entry exists for this reason code, so no draft was made.",
            document="No playbook entry for this reason code.",
            warnings=["Unknown reason code"],
        )

    action = entry["default_action"]
    action_reason = ""
    for rule in entry.get("action_rules", []):
        if evaluate(rule["when"], facts):
            action, action_reason = rule["action"], rule["reason"]
            break
    warnings = [w["text"] for w in entry.get("warnings", []) if evaluate(w["when"], facts)]

    refs = _Refs()
    trace: list[dict] = []
    used: list[dict] = []
    used_marks: list[str] = []
    skipped: list[dict] = []

    if action == "appeal":
        for arg in entry["arguments"]:
            if not evaluate(arg["when"], facts):
                skipped.append(
                    {"id": arg["id"], "reason": "the claim facts do not meet the condition"}
                )
                continue
            hits = retriever.search(arg["query"], k=3)
            trace.append({"query": arg["query"], "top3": [n["id"] for n, _ in hits]})
            strong = [(n, s) for n, s in hits[:2] if s >= MIN_SCORE]
            if len(strong) == 2 and strong[1][1] < 0.75 * strong[0][1]:
                strong = strong[:1]  # cite a second note only when it is nearly as relevant
            if not strong:
                skipped.append(
                    {"id": arg["id"], "reason": "no supporting policy note found (cite or abstain)"}
                )
                continue
            used.append(arg)
            used_marks.append(refs.mark(strong))
        if not used:
            action = "no_appeal"
            action_reason = "No argument is supported by the available facts and policy notes."

    checklist = list(entry.get("checklist", []))
    if used:
        checklist.append("Attach every item listed under Enclosures.")
    checklist.append(
        "Confirm the payer's own rules; replace general Medicare statements where they differ."
    )
    checklist += warnings

    if action == "appeal":
        body = []
        for i, (arg, marks) in enumerate(zip(used, used_marks, strict=True), start=1):
            statement = " ".join(arg["statement"].split()).format_map(facts)
            body.append(f"{i}. {statement} {marks}")
        enclosures = [f"- {e}" for arg in used for e in arg["evidence"]]
        letter = "\n".join(
            [
                letter_date,
                "",
                "To: Appeals Department",
                f"Re: Request for review of denied claim {facts['claim_id']}",
                f"Denial reason: {carc_code} ({entry['title']})",
                "",
                "Dear Appeals Reviewer,",
                "",
                "We request review of the claim below.",
                "",
                _claim_table(facts),
                "",
                "Why the claim was denied",
                entry["meaning"],
                "",
                "Basis for this request",
                *body,
                "",
                "Requested action",
                "We ask that the denial be reversed and the claim reprocessed for payment.",
                "",
                "Enclosures",
                *enclosures,
                "",
                "References",
                refs.render(),
                "",
                "Note to staff before sending (remove this section)",
                *[f"- {c}" for c in checklist],
                f"- {DISCLAIMER}",
            ]
        )
        recommendation = "Send the appeal letter after completing the staff checklist."
        document_type, document = "letter", letter
    else:
        steps = _guidance_lines(entry, retriever, refs, trace)
        if action == "corrected_claim":
            headline = "Submit a corrected claim (do not file an appeal)."
        else:
            headline = "Do not appeal yet."
        recommendation = headline
        reason_line = action_reason or entry["meaning"]
        document = "\n".join(
            [
                f"Claim {facts['claim_id']}: {carc_code} ({entry['title']})",
                "",
                f"Recommendation: {headline}",
                f"Why: {reason_line}",
                "",
                "Next steps",
                *steps,
                "",
                "Staff checklist",
                *[f"- {c}" for c in checklist],
                "",
                "References",
                refs.render() or "None cited.",
                "",
                DISCLAIMER,
            ]
        )
        document_type = "memo"

    if len(refs.order) > max_refs:
        warnings.append("More references than expected; review the draft for relevance.")

    return AppealResult(
        claim_id=facts["claim_id"],
        carc_code=carc_code,
        title=entry["title"],
        action_type=action,
        recommendation=recommendation,
        document_type=document_type,
        document=document,
        arguments_used=[a["id"] for a in used],
        arguments_skipped=skipped,
        citations=refs.as_list(),
        checklist=checklist,
        warnings=warnings,
        root_cause=entry["root_cause"],
        retrieval=trace,
    )


NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER.findall(text)}


def check_letter(
    result: AppealResult, raw_facts: dict, letter_date: str, notes: list[dict], playbook: dict
) -> dict:
    """Grounding checks: facts appear in the letter, and no stray numbers appear."""
    facts = normalize_facts(raw_facts)
    entry = playbook[result.carc_code]
    required = {
        facts["claim_id"],
        f"{facts['amount']:,.2f}",
        str(facts["days_to_file"]),
        facts["from_dt"],
    }
    missing = [r for r in required if r.replace(",", "") not in result.document.replace(",", "")]
    allowed = _numbers(" ".join(str(v) for v in facts.values()))
    allowed |= _numbers(f"{facts['amount']:,.2f} {facts['amount']:.2f} {facts['amount']:,.0f}")
    allowed |= _numbers(letter_date)
    allowed |= _numbers(result.carc_code)
    allowed |= _numbers(str(entry))
    by_id = {n["id"]: n for n in notes}
    for c in result.citations:
        note = by_id[c["id"]]
        allowed |= _numbers(str(note))
    allowed |= {str(i) for i in range(1, 21)}  # list numbers and [n] markers
    stray = sorted(_numbers(result.document) - allowed)
    return {"missing_facts": missing, "stray_numbers": stray}


def main() -> None:
    import pandas as pd

    ap = argparse.ArgumentParser(description="Draft an appeal from local claim data")
    ap.add_argument("--claim-id", required=True)
    ap.add_argument("--reason", help="reason code; defaults to the simulated denial reason")
    ap.add_argument("--claims", default="data/processed/claims_unified.parquet")
    ap.add_argument("--labels", default="data/processed/claim_labels.parquet")
    args = ap.parse_args()
    claims = pd.read_parquet(args.claims, filters=[("claim_id", "==", args.claim_id)])
    labels = pd.read_parquet(args.labels, filters=[("claim_id", "==", args.claim_id)])
    if claims.empty or labels.empty:
        raise SystemExit(f"claim {args.claim_id} not found")
    c, lab = claims.iloc[0], labels.iloc[0]
    facts = {
        "claim_id": c["claim_id"],
        "claim_type": c["claim_type"],
        "from_dt": str(c["from_dt"])[:10],
        "amount": c["amount"],
        "days_to_file": lab["days_to_file"],
        "auth_required": lab["auth_required"],
        "auth_on_file": lab["auth_on_file"],
        "coverage_active": c["coverage_active"],
        "n_lines": c["n_lines"],
        "procedure_unknown": c["procedure_code"] == "UNKNOWN",
    }
    result = draft(facts, args.reason or lab["carc_code"])
    print(result.document)


if __name__ == "__main__":
    main()

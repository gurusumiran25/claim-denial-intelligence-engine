"""Load and check the policy notes and the appeal playbook (plain YAML files in `knowledge/`)."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.rag.conditions import CONDITIONS

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
ACTIONS = {"appeal", "corrected_claim", "no_appeal"}
NOTE_FIELDS = ("id", "title", "keywords", "text", "sources", "accessed")
ENTRY_FIELDS = ("title", "meaning", "default_action", "root_cause", "guidance")


def load_notes(path: Path | None = None) -> list[dict]:
    with open(path or KNOWLEDGE_DIR / "policy_notes.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_playbook(path: Path | None = None) -> dict:
    with open(path or KNOWLEDGE_DIR / "appeal_playbook.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _condition_names(cond) -> list[str]:
    if cond is None:
        return []
    if isinstance(cond, list):
        return [n for c in cond for n in _condition_names(c)]
    return [cond[4:] if cond.startswith("not:") else cond]


def validate(notes: list[dict], playbook: dict) -> list[str]:
    """Return a list of problems (empty when the knowledge files are consistent)."""
    problems: list[str] = []
    ids = [n.get("id") for n in notes]
    if len(ids) != len(set(ids)):
        problems.append("duplicate note ids")
    for n in notes:
        for field in NOTE_FIELDS:
            if not n.get(field):
                problems.append(f"note {n.get('id')} is missing '{field}'")
        for s in n.get("sources", []):
            if not str(s.get("url", "")).startswith("https://"):
                problems.append(f"note {n.get('id')} has a source without an https url")
    for code, entry in playbook.items():
        for field in ENTRY_FIELDS:
            if field not in entry:
                problems.append(f"{code} is missing '{field}'")
        if entry.get("default_action") not in ACTIONS:
            problems.append(f"{code} has an unknown default_action")
        conds = [r.get("when") for r in entry.get("action_rules", [])]
        conds += [a.get("when") for a in entry.get("arguments", [])]
        conds += [w.get("when") for w in entry.get("warnings", [])]
        for cond in conds:
            for name in _condition_names(cond):
                if name not in CONDITIONS:
                    problems.append(f"{code} uses unknown condition '{name}'")
        for rule in entry.get("action_rules", []):
            if rule.get("action") not in ACTIONS:
                problems.append(f"{code} has a rule with an unknown action")
        for arg in entry.get("arguments", []):
            for field in ("id", "statement", "query", "evidence"):
                if not arg.get(field):
                    problems.append(f"{code} argument {arg.get('id')} is missing '{field}'")
    return problems

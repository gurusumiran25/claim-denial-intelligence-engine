"""Facts about a claim and the named conditions the playbook can test against them."""

from __future__ import annotations

MEDICARE_LIMIT_DAYS = 365
HUMAN_FLAGS = (
    "documentation_available",
    "exception_documented",
    "modifier_documented",
    "eligibility_confirmed_active",
)


def normalize_facts(raw: dict) -> dict:
    """Fill defaults and fix types. Human-supplied flags default to False (never assumed)."""
    facts = {
        "claim_id": str(raw["claim_id"]),
        "claim_type": str(raw.get("claim_type", "unknown")),
        "from_dt": str(raw.get("from_dt", ""))[:10],
        "amount": float(raw.get("amount", 0.0)),
        "days_to_file": int(raw.get("days_to_file", 0)),
        "auth_required": bool(raw.get("auth_required", False)),
        "auth_on_file": bool(raw.get("auth_on_file", False)),
        "coverage_active": bool(raw.get("coverage_active", True)),
        "n_lines": int(raw.get("n_lines", 1)),
        "procedure_unknown": bool(raw.get("procedure_unknown", False)),
    }
    for flag in HUMAN_FLAGS:
        facts[flag] = bool(raw.get(flag, False))
    return facts


CONDITIONS = {
    "always": lambda f: True,
    "filed_within_medicare_limit": lambda f: f["days_to_file"] <= MEDICARE_LIMIT_DAYS,
    "filed_after_medicare_limit_without_exception": lambda f: (
        f["days_to_file"] > MEDICARE_LIMIT_DAYS and not f["exception_documented"]
    ),
    "exception_documented": lambda f: f["exception_documented"],
    "authorization_on_file": lambda f: f["auth_required"] and f["auth_on_file"],
    "authorization_missing": lambda f: f["auth_required"] and not f["auth_on_file"],
    "authorization_not_required": lambda f: not f["auth_required"],
    "documentation_available": lambda f: f["documentation_available"],
    "modifier_documented": lambda f: f["modifier_documented"],
    "eligibility_confirmed_active": lambda f: f["eligibility_confirmed_active"],
    "coverage_active": lambda f: f["coverage_active"],
    "coverage_inactive": lambda f: not f["coverage_active"],
}


def evaluate(cond, facts: dict) -> bool:
    """A condition is a name, "not:name", or a list of conditions that must all hold."""
    if cond is None:
        return True
    if isinstance(cond, list):
        return all(evaluate(c, facts) for c in cond)
    if cond.startswith("not:"):
        return not evaluate(cond[4:], facts)
    return bool(CONDITIONS[cond](facts))

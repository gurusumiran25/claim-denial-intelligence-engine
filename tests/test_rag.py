import pytest

from src.rag import evaluate as ev
from src.rag.appeal import check_letter, draft
from src.rag.conditions import evaluate, normalize_facts
from src.rag.knowledge import load_notes, load_playbook, validate
from src.rag.llm import polish_letter
from src.rag.retriever import PolicyRetriever

DATE = "2026-11-09"


@pytest.fixture(scope="module")
def kb():
    notes, playbook = load_notes(), load_playbook()
    return notes, playbook, PolicyRetriever(notes)


def facts(**kw):
    base = {
        "claim_id": "777",
        "claim_type": "outpatient",
        "from_dt": "2010-02-03",
        "amount": 250.0,
        "days_to_file": 40,
        "auth_required": False,
        "auth_on_file": True,
        "coverage_active": True,
    }
    return {**base, **kw}


def test_knowledge_files_are_consistent(kb):
    notes, playbook, _ = kb
    assert validate(notes, playbook) == []
    assert len(notes) >= 20 and len(playbook) == 9


def test_every_note_has_a_checkable_source(kb):
    notes, _, _ = kb
    for n in notes:
        assert n["sources"] and all(s["url"].startswith("https://") for s in n["sources"])
        assert n["accessed"] == "2026-11-09"


def test_conditions():
    f = normalize_facts(facts(auth_required=True, auth_on_file=False, days_to_file=400))
    assert evaluate("authorization_missing", f) and not evaluate("authorization_on_file", f)
    assert evaluate("not:modifier_documented", f)
    assert evaluate(["authorization_missing", "not:documentation_available"], f)
    assert evaluate("filed_after_medicare_limit_without_exception", f)


def test_human_flags_default_to_false():
    f = normalize_facts(facts())
    assert not any(
        f[k]
        for k in (
            "documentation_available",
            "exception_documented",
            "modifier_documented",
            "eligibility_confirmed_active",
        )
    )


def test_retriever_finds_the_right_note(kb):
    _, _, rt = kb
    top = rt.search("timely filing limit 12 months after date of service", k=1)[0][0]["id"]
    assert top == "PN-TIMELY-01"
    assert rt.search("zebra spaceship banana", k=3, min_score=0.12) == []


def test_late_claim_inside_medicare_limit_gets_a_letter(kb):
    notes, playbook, rt = kb
    r = draft(facts(days_to_file=120), "CO-29", rt, playbook, letter_date=DATE)
    assert r.action_type == "appeal" and r.document_type == "letter"
    assert r.arguments_used == ["ARG-TIMELY-WITHIN-LIMIT"]
    assert "120 days" in r.document and "[1]" in r.document and "References" in r.document
    chk = check_letter(r, facts(days_to_file=120), DATE, notes, playbook)
    assert chk == {"missing_facts": [], "stray_numbers": []}


def test_claim_past_12_months_without_exception_is_not_appealed(kb):
    _, playbook, rt = kb
    r = draft(facts(days_to_file=400), "CO-29", rt, playbook, letter_date=DATE)
    assert r.action_type == "no_appeal" and r.document_type == "memo"


def test_never_claims_authorization_that_is_not_on_file(kb):
    _, playbook, rt = kb
    r = draft(
        facts(auth_required=True, auth_on_file=False), "CO-197", rt, playbook, letter_date=DATE
    )
    assert r.action_type == "no_appeal"  # no documentation supplied, so nothing can be argued
    assert "was on file" not in r.document
    r2 = draft(
        facts(auth_required=True, auth_on_file=False, documentation_available=True),
        "CO-197",
        rt,
        playbook,
        letter_date=DATE,
    )
    assert r2.action_type == "appeal" and "No authorization was on file" in r2.document


def test_unprocessable_claim_gets_corrected_claim_memo(kb):
    _, playbook, rt = kb
    r = draft(facts(), "CO-16", rt, playbook, letter_date=DATE)
    assert r.action_type == "corrected_claim" and "do not file an appeal" in r.document.lower()
    assert any(c["id"] == "PN-UNPROC-01" for c in r.citations)


def test_cite_or_abstain_when_no_policy_note_matches(kb):
    _, playbook, _ = kb
    empty = PolicyRetriever(
        [
            {
                "id": "PN-X",
                "title": "Unrelated gardening tips",
                "keywords": ["roses"],
                "text": "Water roses in the morning.",
                "sources": [{"title": "t", "url": "https://example.org"}],
                "accessed": "2026-11-09",
            }
        ]
    )
    r = draft(facts(days_to_file=50), "CO-29", empty, playbook, letter_date=DATE)
    assert r.action_type == "no_appeal"
    assert r.arguments_skipped and "cite or abstain" in r.arguments_skipped[0]["reason"]


def test_coverage_conflict_is_flagged(kb):
    _, playbook, rt = kb
    r = draft(facts(coverage_active=True), "CO-27", rt, playbook, letter_date=DATE)
    assert r.action_type == "no_appeal" and r.warnings


def test_unknown_reason_code(kb):
    _, playbook, rt = kb
    r = draft(facts(), "CO-999", rt, playbook, letter_date=DATE)
    assert r.action_type == "no_appeal" and r.warnings


def test_shipped_evaluation_cases_pass(kb):
    notes, playbook, _ = kb
    df = ev.evaluate_cases(ev.load_cases(), notes, playbook)
    s = dict(ev.summarize(df).values)
    assert s["Cases"] >= 30
    assert s["Recommended action correct"] == 1.0
    assert s["Letters with no stray numbers"] == 1.0
    assert s["Cases with no forbidden (unsupported) phrase"] == 1.0
    assert s["Gold policy note in top 3 retrieved"] >= 0.9


class FakeClient:
    def __init__(self, text):
        self.messages = self
        self._text = text

    def create(self, **kw):
        class Block:
            pass

        b = Block()
        b.text = self._text
        r = Block()
        r.content = [b]
        return r


def test_llm_polish_is_off_by_default_and_guarded():
    text = "The claim 777 was filed 120 days after service [1]."
    assert polish_letter(text) == text
    good = "Claim 777 was submitted 120 days after the service date [1]."
    assert polish_letter(text, "anthropic", FakeClient(good)) == good
    dropped_citation = "Claim 777 was submitted 120 days after the service date."
    assert polish_letter(text, "anthropic", FakeClient(dropped_citation)) == text
    changed_number = "Claim 777 was submitted 12 days after the service date [1]."
    assert polish_letter(text, "anthropic", FakeClient(changed_number)) == text


def test_demo_writes_one_draft_per_reason(tmp_path):
    import numpy as np
    import pandas as pd

    from src.rag import demo

    rng = np.random.default_rng(4)
    n = 3000
    claims = pd.DataFrame(
        {
            "claim_id": [f"C{i:05d}" for i in range(n)],
            "claim_type": "outpatient",
            "from_dt": pd.Timestamp("2009-01-01")
            + pd.to_timedelta(rng.integers(0, 300, n), unit="D"),
            "amount": rng.uniform(20, 900, n).round(2),
            "coverage_active": True,
            "n_lines": 2,
            "procedure_code": "99213",
        }
    )
    denied = rng.random(n) < 0.3
    labels = pd.DataFrame(
        {
            "claim_id": claims["claim_id"],
            "is_denied": denied.astype(int),
            "carc_code": np.where(denied, rng.choice(["CO-29", "CO-16", "CO-197"], n), None),
            "days_to_file": 30,
            "auth_required": True,
            "auth_on_file": False,
        }
    )
    claims.to_parquet(tmp_path / "c.parquet", index=False)
    labels.to_parquet(tmp_path / "l.parquet", index=False)
    out = tmp_path / "out"
    assert demo.run(tmp_path / "c.parquet", tmp_path / "l.parquet", out, assume_evidence=True) == 3
    assert (out / "index.md").exists()
    texts = [p.read_text() for p in out.glob("CO-*.md")]
    assert all(t.startswith("DEMO ONLY") for t in texts)

# Knowledge base for the appeal copilot

- `policy_notes.yaml`: 20 short paraphrased summaries of public Medicare Fee-for-Service guidance, each with source links and the date accessed. They are summaries, not legal text.
- `appeal_playbook.yaml`: for each denial reason, the recommended route (appeal, corrected claim, no appeal), the arguments the claim's facts can support, next steps, root-cause category and prevention actions.
- `eval_cases.yaml`: 30 hand-written test cases used by `python -m src.rag.evaluate`.

## How the copilot decides
1. Facts about the claim come from the data. Facts nobody can know from data (records attached, an exception documented, a modifier documented, eligibility confirmed) are supplied by a person and default to false.
2. The playbook picks the route and the arguments the facts support.
3. For each argument, offline retrieval finds the matching policy notes. An argument with no supporting note is dropped (cite or abstain).
4. The letter is assembled from playbook sentences and the claim's own facts, with numbered references.

## Keeping it honest
- Medicare rules change. Re-check each note's sources at least once a year and update `accessed`.
- The notes describe Medicare Fee-for-Service. A commercial payer's contract can differ, for example a shorter filing limit; every draft tells staff to check.
- The reason-code names follow the simulator (ADR-009). Real code definitions differ slightly: for example reason 4 is about modifiers, while a missing procedure code is usually reason 16 with remark M51.
- To add a note, copy an existing entry, give it a new id, keywords, a paraphrased text and real source URLs, then run `python -m pytest -q` and `python -m src.rag.evaluate`.

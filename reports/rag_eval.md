# Appeal copilot evaluation

| metric | value |
|---|---|
| Cases | 30 |
| Recommended action correct | 100.0% |
| Arguments used exactly as expected (appeal cases) | 100.0% |
| Gold policy note in top 3 retrieved | 100.0% |
| Top-ranked note for the first query is an acceptable note | 100.0% |
| Share of cited notes that are acceptable notes (citation precision) | 100.0% |
| Every cited note exists in the knowledge base | 100.0% |
| Every draft cites at least one note | 100.0% |
| Letters have all required sections | 100.0% |
| Letter produced exactly when action is appeal | 100.0% |
| Letters with all claim facts present | 100.0% |
| Letters with no stray numbers | 100.0% |
| Cases with no forbidden (unsupported) phrase | 100.0% |

## Cases where the recommended action was not the expected one
- none

Cases are hand-written in `knowledge/eval_cases.yaml`; retrieval is offline TF-IDF over 20 policy notes.
Limits: the cases and the playbook were written by the same author, so this checks the system against its own design, not against an independent benchmark. 'Acceptable' notes were assigned after inspecting the retrieval output. Real denials would need a larger, independently labelled set.

#!/usr/bin/env bash
# Creates milestones (one per week) and starter issues using the GitHub CLI.
# Prereq: `gh auth login`, and run from inside the cloned repo (after it exists on GitHub).
set -euo pipefail

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Creating milestones and issues in $REPO"

mk_milestone() { gh api "repos/$REPO/milestones" -f title="$1" -f due_on="$2" >/dev/null || true; }

mk_milestone "Week 1 - Foundation and Data"       "2026-11-01T23:59:00Z"
mk_milestone "Week 2 - Warehouse and Labels"      "2026-11-08T23:59:00Z"
mk_milestone "Week 3 - dbt Feature Layer"         "2026-11-15T23:59:00Z"
mk_milestone "Week 4 - Modeling and Explainability" "2026-11-22T23:59:00Z"
mk_milestone "Week 5 - RAG Copilot and Root Cause" "2026-11-29T23:59:00Z"
mk_milestone "Week 6 - Productionize and Package" "2026-12-06T23:59:00Z"
mk_milestone "Week 7 - Buffer and Launch"         "2026-12-13T23:59:00Z"

issue() { gh issue create --title "$1" --body "$2" --milestone "$3" >/dev/null && echo "  + $1"; }

W1="Week 1 - Foundation and Data"
issue "Download DE-SynPUF Sample 1 and fill data dictionary" "Acceptance: docs/data_dictionary.md section D has no TBD." "$W1"
issue "Profile data in EDA notebook" "Acceptance: 5 written findings, notebook committed." "$W1"
issue "Set up Synthea and decide dataset mix (ADR-006)" "Acceptance: ADR-006 written." "$W1"
issue "Define claim grain and provider ID (ADR-007)" "Acceptance: claims_unified schema agreed." "$W1"
issue "Review and refine denial rules v0.1" "Acceptance: each rule justified, tests pass." "$W1"
issue "Commit 3 reusable SQL queries" "Acceptance: monthly denial rate, provider rolling rate, duplicate detection." "$W1"

W2="Week 2 - Warehouse and Labels"
issue "Load raw tables into BigQuery" "Acceptance: raw tables queryable, costs under control." "$W2"
issue "Build claims_unified and generate labeled dataset" "Acceptance: labeled table in BigQuery, simulator versioned." "$W2"
issue "EDA: denial rate by payer, procedure, provider, amount, time" "Acceptance: 5+ insights documented." "$W2"

W3="Week 3 - dbt Feature Layer"
issue "dbt staging, features and marts" "Acceptance: dbt build passes." "$W3"
issue "Leakage-safe historical features (as-of date)" "Acceptance: leakage checklist signed off." "$W3"
issue "dbt tests and docs" "Acceptance: tests on keys and accepted values." "$W3"

W4="Week 4 - Modeling and Explainability"
issue "Baselines and time-based split" "Acceptance: logistic regression baseline logged in MLflow." "$W4"
issue "LightGBM + calibration + threshold tied to review capacity" "Acceptance: metrics table complete." "$W4"
issue "SHAP global and per-claim + expected-loss ROI simulation" "Acceptance: plots and ROI table saved." "$W4"
issue "Write model card" "Acceptance: docs/model_card.md." "$W4"

W5="Week 5 - RAG Copilot and Root Cause"
issue "Collect public policy docs and build vector store" "Acceptance: docs/rag_sources.md and working retriever." "$W5"
issue "Appeal generator with cite-or-abstain guardrails" "Acceptance: end-to-end draft with citations." "$W5"
issue "RAG evaluation set (20 to 30 cases) and results table" "Acceptance: groundedness rate reported." "$W5"
issue "Root-cause clustering and Pareto" "Acceptance: top fixable causes documented." "$W5"

W6="Week 6 - Productionize and Package"
issue "FastAPI endpoints with tests" "Acceptance: /predict /explain /rank documented." "$W6"
issue "Streamlit app" "Acceptance: risk queue, claim detail, root causes, appeal copilot." "$W6"
issue "Dockerize and deploy" "Acceptance: live URL." "$W6"
issue "README polish, architecture diagram, demo video, LinkedIn post" "Acceptance: all published." "$W6"

W7="Week 7 - Buffer and Launch"
issue "Mock interview run (2, 5 and 10 minute versions)" "Acceptance: talk track in docs." "$W7"
echo "Done."

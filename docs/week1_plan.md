# Week 1 Plan: Foundation and Data (26 Oct to 1 Nov 2026)

**Goal:** repo live, data loaded locally and profiled, claim grain decided, denial rules drafted.
**Time budget:** about 2 to 3 hours on weekdays, longer on the weekend, plus DSA 30 min/day.

## Already done in this starter kit (Sat 24 Oct)
- [x] Repo structure, `.gitignore`, `pyproject.toml`, `requirements.txt`, Makefile
- [x] Pre-commit (ruff, whitespace, large-file guard) and GitHub Actions CI
- [x] README skeleton with honest "simulated labels" note
- [x] Decision log with 5 starting ADRs
- [x] Draft data dictionary and data sources guide
- [x] Draft denial rules (v0.1) + working simulator + 7 passing tests
- [x] Toy claims generator so you can develop before real data is loaded
- [x] EDA starter notebook
- [x] GitHub issues script (board + milestones)

## Daily tasks

### Mon 26 Oct: Repo live
- [ ] Create empty GitHub repo `claim-denial-intelligence-engine` (public)
- [ ] Unzip starter kit, `git init`, first commit, push to `main`
- [ ] `make setup`, then `make toy`, `make simulate`, `make test` (all must pass)
- [ ] Run `bash scripts/create_github_issues.sh` (needs GitHub CLI `gh auth login`) to create the board items
- [ ] Confirm CI turns green on GitHub
- **Done when:** green CI badge and 3+ commits

### Tue 27 Oct: Real data download
- [ ] Download DE-SynPUF Sample 1 files (see `docs/data_sources.md`) into `data/raw/desynpuf/`
- [ ] Read the CMS codebook for inpatient, outpatient, carrier and beneficiary files
- [ ] Record row counts and real column names in `docs/data_dictionary.md` section D
- **Done when:** section D has no TBD

### Wed 28 Oct: Profile the data
- [ ] Copy `notebooks/01_eda_starter.ipynb` to a working version, point it at real files
- [ ] Check: missing values, date ranges, amount distributions, top diagnosis and procedure codes
- [ ] Note 5 observations in the notebook (markdown cells)
- **Done when:** notebook committed with clear findings

### Thu 29 Oct: Synthea
- [ ] Install Java, download Synthea, generate a 5,000 patient sample with CSV export
- [ ] Compare Synthea claims tables with DE-SynPUF: what does each add?
- [ ] Add ADR-006 in `docs/decisions.md`: final dataset mix and why
- **Done when:** ADR-006 written

### Fri 30 Oct: Claim grain and unified schema
- [ ] Decide how carrier (line-level) claims roll up to claim level
- [ ] Decide provider ID per claim type
- [ ] Write the `claims_unified` build script plan (columns from `docs/data_dictionary.md` section A)
- [ ] Refine `simulator/denial_rules.yaml`: check each rule makes business sense
- **Done when:** schema agreed, rules reviewed, ADR-007 (grain and provider ID) written

### Sat 31 Oct: SQL practice on claims
- [ ] Practice: running denial rate by month, provider rolling averages, duplicate detection using window functions and CTEs (DuckDB or pandas SQL on the toy or real data is fine)
- [ ] Commit 3 reusable queries in `notebooks/` or `docs/sql_practice.md`
- **Done when:** 3 queries committed

### Sun 1 Nov: Weekly review
- [ ] Fill `docs/weekly_review_template.md` copy as `docs/reviews/week1.md`
- [ ] Update README status table
- [ ] Re-plan Week 2 (BigQuery load + label simulation) using actual pace
- **Done when:** review file committed

## Week 1 exit criteria (all must be true)
1. Public repo with green CI
2. Real data downloaded and profiled, data dictionary filled
3. Dataset mix and claim grain decided and logged
4. Denial rules reviewed and tests passing
5. EDA notebook with written findings
6. Week 2 plan adjusted

## If you fall behind
Cut Synthea depth first (use DE-SynPUF only, log it as an ADR). Never skip the data dictionary or the weekly review.

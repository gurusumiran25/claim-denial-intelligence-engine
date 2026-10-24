# Data Sources and Setup

All data is public or synthetic. Do not commit raw data (it is gitignored).

## 1. CMS DE-SynPUF (primary)
Synthetic Medicare claims released by CMS. Search for "CMS DE-SynPUF" on cms.gov to find the official download page (sample 1 is enough to start; more samples can be added later).

Files to download for Sample 1 (names follow this pattern; verify against the page):
- Beneficiary Summary Files (2008, 2009, 2010)
- Inpatient Claims
- Outpatient Claims
- Carrier Claims (two parts, 1A and 1B)
- Prescription Drug Events (optional, for later)
- The data users' documentation and codebook (read it before profiling)

Put the unzipped CSVs in `data/raw/desynpuf/`.

Day-1 task: open each file, record real column names and row counts in `docs/data_dictionary.md`.

## 2. Synthea (secondary)
Open-source synthetic patient generator from MITRE (github.com/synthetichealth/synthea). Requires Java.
Typical flow: download the latest release jar, run it with a population size (for example 5000) and enable CSV export. Output goes to `output/csv/` (patients, encounters, claims and related tables). Move to `data/raw/synthea/`.

Use Synthea to add payer and encounter detail and to generate extra volume if needed.

## 3. Public reference data (Week 3)
Code sets (ICD, HCPCS) and public fee schedules from CMS for feature enrichment.

## 4. Public payer policy documents (Week 5, for RAG)
Collect only publicly available coverage policies and medical policy PDFs. Keep a source list (title, URL, date accessed) in `docs/rag_sources.md`.

## Compliance rules (non-negotiable)
- No employer data, screenshots, logic or documents
- No real PHI
- Cite every dataset and policy source in the README

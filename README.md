# Claim Denial Intelligence Engine

> Predict which healthcare claims will be denied **before** submission, rank the work queue by **expected dollar loss**, explain **why**, and draft **policy-grounded appeal letters** with an LLM.

![status](https://img.shields.io/badge/status-week%201%20of%207-blue) ![python](https://img.shields.io/badge/python-3.10%2B-blue)

**Live demo:** _coming in Week 6_ | **Demo video:** _coming in Week 6_

## Why this project

Denials cost providers money and rework, and most teams fix them after the fact. This project moves the work earlier: score the claim, show the drivers, prioritize by money at stake, and cut appeal drafting time.

## Important note on data

This project uses **public and synthetic data only** (CMS DE-SynPUF, Synthea). No real PHI and no employer data.
Public claims datasets do not include a real denial flag, so the **denial label is simulated** from documented, versioned rules plus noise (see `simulator/denial_rules.yaml` and `docs/decisions.md`). Results show how well the system recovers realistic denial patterns and prioritizes dollars, not performance on a real payer.

## What it will do

1. Data pipeline on BigQuery + dbt
2. Denial prediction (LightGBM) with calibration and SHAP explanations
3. Expected-loss ranking (probability x claim amount) and ROI simulation
4. Denial root-cause analysis (reason-code clustering, Pareto)
5. RAG appeal copilot with cite-or-abstain guardrails
6. FastAPI + Streamlit app, Docker, CI

## Architecture (target)

```
CMS / Synthea data -> Python ingestion -> BigQuery raw -> dbt (staging, features, marts)
  -> LightGBM + MLflow -> SHAP -> FastAPI -> Streamlit
Policy docs -> chunks -> embeddings -> vector store -> RAG -> appeal draft with citations
```

## Project status

| Week | Focus | Status |
|---|---|---|
| 1 | Foundation, data profiling, rule drafting | In progress |
| 2 | BigQuery load + label simulation + EDA | Planned |
| 3 | dbt feature layer | Planned |
| 4 | Modeling, calibration, SHAP, ROI | Planned |
| 5 | RAG appeal copilot + root cause | Planned |
| 6 | API, app, deploy, packaging | Planned |
| 7 | Buffer and launch | Planned |

## Quick start

```bash
git clone https://github.com/gurusumiran25/claim-denial-intelligence-engine.git
cd claim-denial-intelligence-engine
make setup              # venv + deps + pre-commit
make toy                # generate fake sample claims (dev only)
make simulate           # apply draft denial rules to the toy claims
make test               # run tests
```

## Repo layout

```
docs/         decisions log, data dictionary, data sources, weekly plans
simulator/    denial rules (YAML) + label simulator
ingestion/    data loading scripts (+ toy data generator for dev)
dbt_project/  warehouse models (Week 3)
src/          features, training, explain, rag, api
app/          Streamlit app (Week 6)
notebooks/    EDA and modeling notebooks
tests/        pytest suite
```

## Results

_To be filled in Week 4 (metrics table, SHAP plots, dollars protected at top-k)._

## Limitations

- Labels are simulated; absolute metrics are not claims about real payers
- Synthetic data does not capture every real-world billing behavior

## Author

M. Guru Sumiran | [LinkedIn](https://linkedin.com/in/m-guru-sumiran-2a3a6a291) | [GitHub](https://github.com/gurusumiran25)

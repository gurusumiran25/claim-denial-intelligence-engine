.PHONY: setup lint format test toy simulate all

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pre-commit install

lint:
	ruff check .

format:
	ruff format .

test:
	pytest -q

toy:  ## generate a small fake claims file to develop against before real data is loaded
	python -m ingestion.make_toy_claims --n 20000 --out data/processed/toy_claims.parquet

simulate:  ## apply denial rules to the toy claims
	python -m simulator.simulate_denials --in data/processed/toy_claims.parquet --out data/processed/toy_claims_labeled.parquet

all: lint test

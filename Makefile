.PHONY: setup dev test lint evaluate benchmark benchmark-live generate-data docker-up docker-down

setup:
	python -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

dev:
	docker compose up --build

test:
	python -m pytest backend/tests evaluation/tests -q
	cd frontend && npm test

lint:
	python -m ruff check backend evaluation scripts
	python -m mypy backend/app --ignore-missing-imports
	cd frontend && npm run lint

generate-data:
	python scripts/generate_enterprise_assets.py
	python scripts/validate_evaluation_assets.py

evaluate:
	python -m evaluation.run_experiments --config evaluation/configs/ci.yaml

benchmark:
	python -m evaluation.run_experiments --config evaluation/configs/local.yaml

benchmark-live:
	python -m evaluation.run_experiments --config evaluation/configs/full.yaml

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

.PHONY: install test lint format-check typecheck frontend-test frontend-build schemas quality serve live smoke docker

install:
	python -m pip install -e ".[dev]"

test:
	pytest --cov=berlin_mobility_twin --cov-report=term-missing

lint:
	ruff check .

format-check:
	ruff format --check .

typecheck:
	mypy src/berlin_mobility_twin

frontend-test:
	cd frontend && npm ci && npm test

frontend-build:
	cd frontend && npm ci && npm run build

schemas:
	rm -rf schemas && berlin-mobility-twin export-schemas --output-dir schemas

quality: lint format-check typecheck test frontend-test frontend-build

serve:
	berlin-mobility-twin serve

live:
	berlin-mobility-twin serve --live

smoke:
	python scripts/smoke_real_data.py

docker:
	docker build -t berlin-urban-mobility-twin .

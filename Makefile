# Targets for Linux/CI. On Windows see the README (PowerShell commands).

PY ?= python
VENV ?= .venv
BIN := $(VENV)/bin
export PATH := $(BIN):$(PATH)

.PHONY: help install test arch contract dev web-dev web-build docker-build docker-up docker-down clean

help:
	@echo "install    - uv sync: .venv with the backend, PDF and the dev group"
	@echo "test       - backend and frontend tests with coverage (80%+)"
	@echo "arch       - import-linter (DDD gates)"
	@echo "contract   - regenerate TS types from the JSON Schema"
	@echo "format     - bring both corpora (content/compendium, content/bestiary) to contract/compendium-format.json"
	@echo "format-check - check that the corpora follow the canon"
	@echo "dev        - uvicorn --reload"
	@echo "web-dev    - vite dev"
	@echo "web-build  - tsc + vite build"
	@echo "docker-build - build the image (API + SPA + compendium)"
	@echo "docker-up  - start the container on http://127.0.0.1:8000"
	@echo "docker-down - stop the container"
	@echo "clean      - remove caches"

install:
	uv sync --all-extras

test:
	$(BIN)/python -m pytest backend --cov --cov-config=backend/pyproject.toml
	cd frontend && npm run test:coverage

arch:
	$(BIN)/lint-imports --config backend/pyproject.toml

contract:
	cd frontend && npm run contract

format:
	$(BIN)/python -m scripts.normalize --write

format-check:
	$(BIN)/python -m scripts.normalize --check

dev:
	$(BIN)/python -m uvicorn dndsheet.main:app --reload

web-dev:
	cd frontend && npm run dev

web-build:
	cd frontend && npm run build

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache backend/.pytest_cache frontend/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

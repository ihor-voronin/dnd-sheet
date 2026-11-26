# Цілі для Linux/CI. На Windows зручніше дивитись README (команди в PowerShell).

PY ?= python
VENV ?= .venv
BIN := $(VENV)/bin
export PATH := $(BIN):$(PATH)

.PHONY: help install test arch contract dev web-dev web-build docker-build docker-up docker-down clean

help:
	@echo "install    - створити venv і встановити backend[dev]"
	@echo "test       - pytest"
	@echo "arch       - import-linter (DDD-гейти)"
	@echo "contract   - перегенерувати TS-типи з JSON Schema"
	@echo "format     - привести обидва корпуси (content/compendium, content/bestiary) до contract/compendium-format.json"
	@echo "format-check - перевірити, що корпуси за каноном"
	@echo "dev        - uvicorn --reload"
	@echo "web-dev    - vite dev"
	@echo "web-build  - tsc + vite build"
	@echo "docker-build - зібрати образ (API + SPA + довідник)"
	@echo "docker-up  - підняти контейнер на http://127.0.0.1:8000"
	@echo "docker-down - зупинити контейнер"
	@echo "clean      - прибрати кеші"

install:
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip
	$(BIN)/python -m pip install -e "backend[dev]"

test:
	$(BIN)/python -m pytest backend

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

"""Спільні фікстури тестів: шляхи до контракту та фікстур."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = REPO_ROOT / "contract"
SCHEMA_PATH = CONTRACT_DIR / "sheet-document.schema.json"
FIXTURES_DIR = CONTRACT_DIR / "fixtures"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def fixture_files() -> list[Path]:
    files = sorted(FIXTURES_DIR.glob("*.json"))
    assert files, f"Немає фікстур у {FIXTURES_DIR}"
    return files


@pytest.fixture(scope="session")
def fixture_documents(fixture_files: list[Path]) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in fixture_files}

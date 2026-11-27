"""Shared test fixtures: paths to the contract and fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# API tests run as the "local player": sign-in is checked by separate tests
# (`tests/identity`) that enable it explicitly. The corpus comes from the repository,
# wherever pytest is run from.
os.environ.setdefault("DNDSHEET_AUTH", "off")
os.environ.setdefault("DNDSHEET_CONTENT_DIR", str(REPO_ROOT / "content"))
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
    assert files, f"No fixtures in {FIXTURES_DIR}"
    return files


@pytest.fixture(scope="session")
def fixture_documents(fixture_files: list[Path]) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in fixture_files}

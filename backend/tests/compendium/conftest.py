"""Спільні фікстури тестів довідника.

Сам корпус збирається в `corpus.py`: `content_dir` дає теку з маленьким
корпусом (`compendium/`, `index/spell-lists.json`, `sources.yml`), а
`repository`/`service` — готові обʼєкти над нею.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import corpus
import pytest
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.infrastructure.jsonl_corpus import JsonlCompendiumRepository
from dndsheet.compendium.infrastructure.sources_registry import load_titles
from dndsheet.compendium.infrastructure.spell_lists import JsonSpellListRepository


@pytest.fixture()
def content_dir() -> Path:
    shutil.rmtree(corpus.BASE, ignore_errors=True)
    corpus.BASE.mkdir(parents=True)
    content = corpus.build_content(corpus.BASE)
    try:
        yield content
    finally:
        shutil.rmtree(corpus.BASE, ignore_errors=True)


@pytest.fixture()
def repository(content_dir: Path) -> JsonlCompendiumRepository:
    return JsonlCompendiumRepository(directory=content_dir / "compendium")


@pytest.fixture()
def service(content_dir: Path) -> CompendiumService:
    repository = JsonlCompendiumRepository(directory=content_dir / "compendium")
    spell_lists = JsonSpellListRepository(path=content_dir / "index" / "spell-lists.json")
    titles = load_titles(content_dir / "sources.yml")
    return CompendiumService(repository, spell_lists, titles)

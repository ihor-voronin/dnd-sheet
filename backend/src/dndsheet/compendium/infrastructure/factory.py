"""Збирання сервісу довідника з реальних файлів на диску.

Єдине місце, де домен зустрічається з `content/`: репозиторій корпусу,
похідні індекси (класові списки заклять, механіки класів і видів) і назви
книг з реєстру джерел.
"""

from __future__ import annotations

from pathlib import Path

from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.infrastructure.jsonl_corpus import (
    JsonlCompendiumRepository,
    default_content_dir,
)
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository
from dndsheet.compendium.infrastructure.sources_registry import load_ddb_slugs, load_market, load_titles
from dndsheet.compendium.infrastructure.spell_lists import JsonSpellListRepository


def build_service(
    content_dir: Path | str | None = None,
    compendium_dir: Path | str | None = None,
    spell_lists_file: Path | str | None = None,
    sources_file: Path | str | None = None,
    mechanics_dir: Path | str | None = None,
) -> CompendiumService:
    """Сервіс над текою `content/` (за замовчуванням — репозиторій)."""
    content = Path(content_dir) if content_dir is not None else default_content_dir()
    repository = JsonlCompendiumRepository(
        directory=Path(compendium_dir) if compendium_dir is not None else content / "compendium"
    )
    spell_lists = JsonSpellListRepository(
        path=Path(spell_lists_file)
        if spell_lists_file is not None
        else content / "index" / "spell-lists.json"
    )
    index_dir = Path(mechanics_dir) if mechanics_dir is not None else content / "index"
    mechanics = JsonMechanicsRepository(
        classes_path=index_dir / "class-mechanics.json",
        origins_path=index_dir / "origin-mechanics.json",
    )
    sources = Path(sources_file) if sources_file is not None else content / "sources.yml"
    titles = load_titles(sources)
    return CompendiumService(
        repository,
        spell_lists,
        titles,
        mechanics,
        ddb_slugs=load_ddb_slugs(sources),
        market=load_market(content / "books_market.json"),
    )

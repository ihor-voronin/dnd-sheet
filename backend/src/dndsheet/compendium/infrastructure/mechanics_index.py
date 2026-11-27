"""Читання похідних індексів механік (`content/index/*-mechanics.json`).

Індекси складає `scripts/ingest/mechanics.py` з дзеркала 5e.tools: корпус
довідника містить текст умінь, але не хіт-дайс, володіння й таблиці слотів.
Тут лише читання: жодного розбору 5e.tools-формату, жодних `_copy`.

Індекс необовʼязковий. Немає файлу, стара схема, битий JSON — це не привід
падати: `available()` скаже `false`, `warnings()` — чому саме, а візард
чесно покаже, що механік немає.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from pathlib import Path
from typing import Any, Mapping

from dndsheet.compendium.domain.entry import search_key
from dndsheet.compendium.infrastructure.jsonl_corpus import default_content_dir
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
    TERRAINS,
    SubclassSpells,
)

CLASS_SCHEMA = "class-mechanics/1"
ORIGIN_SCHEMA = "origin-mechanics/1"


def default_class_mechanics_file() -> Path:
    return default_content_dir() / "index" / "class-mechanics.json"


def default_origin_mechanics_file() -> Path:
    return default_content_dir() / "index" / "origin-mechanics.json"


@dataclass(slots=True)
class JsonMechanicsRepository:
    """Механіки з двох JSON-файлів, завантажені ліниво."""

    classes_path: Path | None = None
    origins_path: Path | None = None
    _loaded: bool = field(default=False, init=False, repr=False)
    _classes: dict[str, ClassMechanics] = field(default_factory=dict, init=False, repr=False)
    _species: dict[str, SpeciesMechanics] = field(default_factory=dict, init=False, repr=False)
    _subspecies: dict[str, SpeciesMechanics] = field(default_factory=dict, init=False, repr=False)
    _backgrounds: dict[str, BackgroundMechanics] = field(
        default_factory=dict, init=False, repr=False
    )
    _warnings: list[str] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.classes_path is None:
            self.classes_path = default_class_mechanics_file()
        if self.origins_path is None:
            self.origins_path = default_origin_mechanics_file()
        self.classes_path = Path(self.classes_path)
        self.origins_path = Path(self.origins_path)

    # --- порт ---------------------------------------------------------------

    def available(self) -> bool:
        self._ensure_loaded()
        return bool(self._classes or self._species or self._backgrounds)

    def warnings(self) -> tuple[str, ...]:
        self._ensure_loaded()
        return tuple(self._warnings)

    def classes(self) -> Mapping[str, ClassMechanics]:
        self._ensure_loaded()
        return self._classes

    def class_mechanics(self, name: str) -> ClassMechanics | None:
        self._ensure_loaded()
        key = search_key(name)
        found = self._classes.get(key)
        if found is not None:
            return found
        # Ключ у індексі — назва в нижньому регістрі; search_key прибирає
        # пунктуацію, тому «Half-Elf» і «half elf» ведуть в один запис.
        for stored, entry in self._classes.items():
            if search_key(stored) == key:
                return entry
        return None

    def species(self) -> Mapping[str, SpeciesMechanics]:
        self._ensure_loaded()
        return self._species

    def subspecies(self) -> Mapping[str, SpeciesMechanics]:
        self._ensure_loaded()
        return self._subspecies

    def species_mechanics(self, name: str) -> SpeciesMechanics | None:
        self._ensure_loaded()
        key = search_key(name)
        for bucket in (self._species, self._subspecies):
            found = bucket.get(key)
            if found is not None:
                return found
            for stored, entry in bucket.items():
                if search_key(stored) == key:
                    return entry
        return None

    def backgrounds(self) -> Mapping[str, BackgroundMechanics]:
        self._ensure_loaded()
        return self._backgrounds

    def background_mechanics(self, name: str) -> BackgroundMechanics | None:
        self._ensure_loaded()
        key = search_key(name)
        found = self._backgrounds.get(key)
        if found is not None:
            return found
        for stored, entry in self._backgrounds.items():
            if search_key(stored) == key:
                return entry
        return None

    # --- завантаження -------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._load_classes()
        self._load_origins()

    def _load_classes(self) -> None:
        payload = self._read(self.classes_path, CLASS_SCHEMA, "класів")
        if payload is None:
            return
        for key, record in (payload.get("classes") or {}).items():
            if not isinstance(record, dict):
                self._warnings.append(f"механіки класу {key!r}: не обʼєкт")
                continue
            try:
                self._classes[str(key)] = ClassMechanics.from_index(str(key), record)
            except ValidationError as exc:
                self._warnings.append(f"механіки класу {key!r}: {exc}")
        if not self._classes:
            self._warnings.append("індекс класів порожній")
        self._merge_subclass_tables()

    def _merge_subclass_tables(self) -> None:
        """Закляття домену, клятви тощо за всіма рівнями — з тексту підкласу.

        Індекс зберігає лише 1 рівень, а повна таблиця («| Cleric Level |
        Spells |») є в тексті підкласу в корпусі поруч із індексом.
        """
        assert self.classes_path is not None
        root = self.classes_path.parent.parent / "compendium"
        for path in sorted(root.glob("*/subclass.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                klass = str((record.get("data") or {}).get("class") or "").casefold()
                definition = self._classes.get(klass)
                tables = subclass_spell_tables(str(record.get("text_en") or ""), klass)
                if definition is None or not tables:
                    continue
                # Круг Землі: по таблиці на кожну місцевість, у порядку з тексту (PHB, p. 68).
                terrains = TERRAINS if len(tables) == len(TERRAINS) else ()
                if len(tables) != 1 and not terrains:
                    continue
                table = tables[0] if not terrains else {}
                slug = str(record.get("id") or "").rsplit("/", 1)[-1]
                old = definition.subclass_spells.get(slug) or SubclassSpells()
                merged = dict(definition.subclass_spells)
                merged[slug] = replace(
                    old,
                    by_level=MappingProxyType(table),
                    by_terrain=MappingProxyType(
                        {name: MappingProxyType(rows) for name, rows in zip(terrains, tables)}
                    ),
                    prepared=old.prepared or table.get(1, ()),
                )
                self._classes[klass] = replace(
                    definition, subclass_spells=MappingProxyType(merged)
                )

    def _load_origins(self) -> None:
        payload = self._read(self.origins_path, ORIGIN_SCHEMA, "видів")
        if payload is None:
            return
        for key, record in (payload.get("species") or {}).items():
            if isinstance(record, dict):
                self._load_species(key, record, self._species)
        for key, record in (payload.get("subspecies") or {}).items():
            if isinstance(record, dict):
                self._load_species(key, record, self._subspecies)
        for key, record in (payload.get("backgrounds") or {}).items():
            if not isinstance(record, dict):
                continue
            try:
                self._backgrounds[str(key)] = BackgroundMechanics.from_index(str(key), record)
            except ValidationError as exc:
                self._warnings.append(f"механіки передісторії {key!r}: {exc}")

    def _load_species(
        self, key: Any, record: Mapping[str, Any], bucket: dict[str, SpeciesMechanics]
    ) -> None:
        try:
            bucket[str(key)] = SpeciesMechanics.from_index(str(key), record)
        except ValidationError as exc:
            self._warnings.append(f"механіки виду {key!r}: {exc}")

    def _read(self, path: Path | None, schema: str, what: str) -> dict | None:
        assert path is not None
        if not path.is_file():
            self._warnings.append(
                f"немає індексу механік {what}: {path.name} "
                f"(складає scripts/ingest/mechanics.py --write)"
            )
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._warnings.append(f"{path.name}: невірний JSON ({exc.msg})")
            return None
        except OSError as exc:
            self._warnings.append(f"{path.name}: {exc}")
            return None
        if payload.get("schema") != schema:
            self._warnings.append(
                f"{path.name}: схема {payload.get('schema')!r}, очікується {schema!r}"
            )
            return None
        return payload


_SPELL_TABLE = re.compile(r"^\|\s*(\w+) Level\s*\|\s*(?:Circle\s+)?Spells?\s*\|[^\n]*\n\|[- |]+\|\n((?:\|[^\n]*\|\n?)+)", re.M)


def subclass_spell_tables(text: str, class_key: str) -> list[dict[int, tuple[str, ...]]]:
    """Кожна «| Cleric Level | Spells |» → {1: ("bless", "cure wounds"), 3: (…)}."""
    tables: list[dict[int, tuple[str, ...]]] = []
    for match in _SPELL_TABLE.finditer(text):
        if match.group(1).casefold() != class_key:
            continue
        result: dict[int, tuple[str, ...]] = {}
        for row in match.group(2).splitlines():
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            level = re.match(r"\d+", cells[0]) if cells else None
            if level and len(cells) > 1:
                result[int(level.group())] = tuple(
                    name.strip() for name in cells[1].split(",") if name.strip()
                )
        tables.append(result)
    return tables

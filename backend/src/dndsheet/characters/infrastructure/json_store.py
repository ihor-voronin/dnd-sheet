"""Файлове сховище персонажів і чернеток (до БД — етап 6).

Один файл на агрегат: `<каталог>/<id>.json`. Запис атомарний — у тимчасовий
файл і `os.replace`, інакше перерваний запис лишив би обрізаний JSON, і
персонаж «зник» би.

Ідентифікатор із запиту — це імʼя файлу, тому він перевіряється: лише
`[A-Za-z0-9_-]`, до 64 символів. Інакше `../` у шляху читав би чужі файли.

Правила (`RulesSource`) потрібні лише на читанні: файл зберігає **стан**
(клас, рівень, кидки), а числа хітів, КЗ і комірок рахуються заново.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.wizard import Draft
from dndsheet.characters.infrastructure.character_json import (
    character_from_record,
    character_to_record,
    draft_from_record,
    draft_to_record,
)
from dndsheet.shared.errors import NotFoundError, ValidationError

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _check_id(value: str) -> str:
    if not _ID_RE.match(value or ""):
        raise ValidationError(f"неприпустимий ідентифікатор {value!r}")
    return value


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path.name}: невірний JSON ({exc.msg})") from exc


@dataclass(slots=True)
class JsonCharacterRepository:
    """Персонажі у файлах. Робочий каталог створюється на першому записі."""

    directory: Path
    rules: RulesSource

    def save(self, character: Character) -> None:
        _check_id(character.id)
        _write_atomic(self.directory / f"{character.id}.json", character_to_record(character))

    def get(self, character_id: str) -> Character | None:
        payload = _read_json(self.directory / f"{_check_id(character_id)}.json")
        return None if payload is None else character_from_record(payload, self.rules)

    def ids(self) -> tuple[str, ...]:
        if not self.directory.is_dir():
            return ()
        return tuple(
            sorted(path.stem for path in self.directory.glob("*.json") if _ID_RE.match(path.stem))
        )

    def delete(self, character_id: str) -> None:
        path = self.directory / f"{_check_id(character_id)}.json"
        if not path.is_file():
            raise NotFoundError(f"немає персонажа {character_id!r}")
        path.unlink()


@dataclass(slots=True)
class JsonDraftRepository:
    """Чернетки візарда у файлах."""

    directory: Path
    rules: RulesSource

    def save(self, draft: Draft) -> None:
        _check_id(draft.id)
        _write_atomic(self.directory / f"{draft.id}.json", draft_to_record(draft))

    def get(self, draft_id: str) -> Draft | None:
        payload = _read_json(self.directory / f"{_check_id(draft_id)}.json")
        return None if payload is None else draft_from_record(payload, self.rules)

    def delete(self, draft_id: str) -> None:
        path = self.directory / f"{_check_id(draft_id)}.json"
        if not path.is_file():
            raise NotFoundError(f"немає чернетки {draft_id!r}")
        path.unlink()


def default_data_dir() -> Path:
    """Каталог даних: `DNDSHEET_DATA_DIR` або `<repo>/var`."""
    configured = os.environ.get("DNDSHEET_DATA_DIR")
    if configured:
        return Path(configured)
    # backend/src/dndsheet/characters/infrastructure/json_store.py -> repo root
    return Path(__file__).resolve().parents[5] / "var"

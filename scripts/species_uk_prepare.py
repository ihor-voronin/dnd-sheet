"""Підготувати тексти видів до перекладу: назви, уміння, описи.

Корпус тримає особливості виду всередині `text_en`, тому переклад живе не в
записах довідника, а поруч — у `content/translations/species/`. Щоб не платити
двічі за однаковий текст (Darkvision у двадцяти видів — той самий рядок),
файли ріжуться за **унікальним** текстом: ключ — `sha1(текст)[:10]`.

Скрипт нічого не перекладає: він лише готує вхідні файли для агентів і
друкує, скільки всього треба перекласти.

    python scripts/species_uk_prepare.py

Пише:

* `var/uk/input/names.json` — 198 назв умінь (`{id, name_en}`);
* `var/uk/input/texts-01.json` … — унікальні тексти умінь (`{id, name_en, text_en}`);
* `var/uk/input/descriptions-01.json` … — описи видів (`{id, species, text_en}`);
* `var/uk/GLOSSARY.md` — глосарій термінів, спільний для всіх агентів.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("DNDSHEET_CONTENT_DIR", str(ROOT / "content"))

from dndsheet.characters.api.species_traits import species_details  # noqa: E402
from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

OUT = ROOT / "var" / "uk"
TEXTS_PER_CHUNK = 35
DESCRIPTIONS_PER_CHUNK = 5


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def collect() -> tuple[dict[str, str], dict[str, dict], dict[str, dict]]:
    service = build_service()
    names: dict[str, str] = {}
    texts: dict[str, dict] = {}
    descriptions: dict[str, dict] = {}

    def take(name_en: str, text: str) -> None:
        names.setdefault(name_en, ident(name_en))
        if text and text.strip():
            texts.setdefault(ident(text), {"name_en": name_en, "text_en": text})

    def take_description(species: str, text: str | None) -> None:
        if text and text.strip():
            descriptions.setdefault(ident(text), {"species": species, "text_en": text})

    for species in service.species_list():
        details = species_details(service, species.name_en) or {}
        take_description(species.name_en, details.get("description"))
        for trait in details.get("traits") or []:
            take(trait["name_en"], trait["text"])
        # Підрасу треба розбирати з батьком: половина з них описана в тексті
        # батьківського виду, і без `parent_name_en` їхні вміння не знайдуться.
        for child in service.subspecies_of(species.name_en):
            resolved = (
                species_details(
                    service, child.name_en, parent_name_en=species.name_en
                )
                or {}
            )
            take_description(child.name_en, resolved.get("description"))
            for trait in resolved.get("traits") or []:
                take(trait["name_en"], trait["text"])
    return names, texts, descriptions


def write_chunks(folder: Path, prefix: str, items: list[dict], size: int) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    count = 0
    for start in range(0, len(items), size):
        chunk = items[start : start + size]
        path = folder / f"{prefix}-{count + 1:02d}.json"
        path.write_text(
            json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        count += 1
    return count


def existing_ids(field: str) -> set[str]:
    """Які id уже перекладені — щоб не платити за них удруге."""
    done: set[str] = set()
    folder = ROOT / "content" / "translations" / "species"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get(field):
                done.add(str(row.get("id")))
    return done


def main() -> int:
    names, texts, descriptions = collect()
    input_dir = OUT / "input"
    (OUT).mkdir(parents=True, exist_ok=True)
    if "--missing" in sys.argv:
        done_names, done_texts = existing_ids("name_uk"), existing_ids("text_uk")
        names = {key: value for key, value in names.items() if value not in done_names}
        texts = {key: row for key, row in texts.items() if key not in done_texts}
        descriptions = {
            key: row for key, row in descriptions.items() if key not in done_texts
        }
        for old in input_dir.glob("*.json"):
            old.unlink()

    (input_dir).mkdir(parents=True, exist_ok=True)
    prefix = "extra-" if "--missing" in sys.argv else ""
    (input_dir / f"{prefix}names.json").write_text(
        json.dumps(
            [{"id": key, "name_en": name} for name, key in sorted(names.items())],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    text_rows = [
        {"id": key, "name_en": row["name_en"], "text_en": row["text_en"]}
        for key, row in sorted(texts.items(), key=lambda kv: kv[1]["name_en"])
    ]
    text_chunks = write_chunks(input_dir, f"{prefix}texts", text_rows, TEXTS_PER_CHUNK)

    description_rows = [
        {"id": key, "species": row["species"], "text_en": row["text_en"]}
        for key, row in sorted(descriptions.items(), key=lambda kv: kv[1]["species"])
    ]
    description_chunks = write_chunks(
        input_dir, f"{prefix}descriptions", description_rows, DESCRIPTIONS_PER_CHUNK
    )

    print(f"назв: {len(names)}")
    print(f"унікальних текстів умінь: {len(text_rows)} → {text_chunks} файлів")
    print(
        f"описів видів: {len(description_rows)} → {description_chunks} файлів, "
        f"{sum(len(row['text_en']) for row in description_rows)} символів"
    )
    print(f"символів умінь: {sum(len(row['text_en']) for row in text_rows)}")
    print(f"файли: {input_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




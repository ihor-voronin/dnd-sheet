"""Збирач класових списків заклять: «Spell Lists» з книг → `content/index/spell-lists.json`.

Навіщо: у корпусі закляття майже не мають `data.classes`, тому «які закляття
доступні волшебнику з 1 рівня» з самих записів не видно. У книзі ж є окрема
сторінка зі списками по класах і рівнях — з неї й беремо.

Сторінка (mirror dndbeyond) має стабільну структуру: `h2` = «Bard Spells»,
`h4` = «Cantrips (0 Level)» / «1st Level», далі `<p><a>Назва</a></p>`. Тому
розбір — це один прохід по заголовках, без HTML-парсера й без залежностей.

Запуск:
    python -m scripts.ingest.spell_lists --write     # записати індекс
    python -m scripts.ingest.spell_lists --check     # порівняти з тим, що на диску
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "spell-lists/1"

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
RAW = CONTENT / "raw"
TARGET = CONTENT / "index" / "spell-lists.json"

_HEADING_RE = re.compile(r"<h(?P<level>[24])\b[^>]*>(?P<inner>.*?)</h(?P=level)>", re.S)
_ANCHOR_RE = re.compile(r"<p\b[^>]*>\s*<a\b[^>]*>(?P<text>.*?)</a>\s*</p>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_LEVEL_RE = re.compile(r"(?P<ordinal>cantrip|\d+)(?:st|nd|rd|th)?\s*(?:-\s*)?level", re.IGNORECASE)
_ORDINALS = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9}


@dataclass(slots=True)
class ExtractResult:
    """Результат розбору однієї книги."""

    book: str
    page: str
    lists: dict[str, dict[int, list[str]]] = field(default_factory=dict)
    classes_seen: tuple[str, ...] = ()
    problems: list[str] = field(default_factory=list)


def clean(text: str) -> str:
    """Текст із HTML: без тегів, з розкритими сутностями, без подвійних пробілів."""
    plain = html.unescape(_TAG_RE.sub(" ", text))
    return " ".join(plain.split())


def parse_page(book: str, path: Path) -> ExtractResult:
    page = path.read_text(encoding="utf-8", errors="replace")
    result = ExtractResult(book=book, page=path.name)

    current_class: str | None = None
    current_level: int | None = None
    anchors: list[str] = []

    # Заголовки й абзаци-посилання в порядку появи: один прохід, без вкладених циклів.
    tokens: list[tuple[int, str, str]] = []
    for match in _HEADING_RE.finditer(page):
        tokens.append((match.start(), f"h{match.group('level')}", match.group("inner")))
    for match in _ANCHOR_RE.finditer(page):
        tokens.append((match.start(), "link", match.group("text")))
    tokens.sort(key=lambda item: item[0])

    for _, kind, payload in tokens:
        if kind == "h2":
            title = clean(payload)
            current_class = _class_from_heading(title)
            current_level = None
            anchors = []
            continue
        if kind == "h4":
            current_level = _level_from_heading(clean(payload))
            continue
        if kind == "link":
            if current_class is None or current_level is None:
                continue
            name = clean(payload)
            if not name:
                continue
            bucket = result.lists.setdefault(current_class, {}).setdefault(current_level, [])
            if name in bucket:
                continue
            bucket.append(name)
            anchors.append(name)

    result.classes_seen = tuple(result.lists)
    for class_name, per_level in result.lists.items():
        for level, names in per_level.items():
            if not names:
                result.problems.append(f"{class_name}: рівень {level} без заклять")
    if not result.lists:
        result.problems.append("не знайдено жодного класового списку")
    return result


def _class_from_heading(title: str) -> str | None:
    """«Bard Spells» → `Bard`; заголовок без «Spells» — не список класу."""
    if not title.lower().endswith(" spells"):
        return None
    name = title[: -len(" spells")].strip()
    return name or None


def _level_from_heading(title: str) -> int | None:
    if title.lower().startswith("cantrip"):
        return 0
    match = _LEVEL_RE.search(title)
    if not match:
        return None
    token = match.group("ordinal").lower()
    if token == "cantrip":
        return 0
    return _ORDINALS.get(token)


def discover_pages() -> list[tuple[str, Path]]:
    """Сторінки «Spell Lists» у дзеркалі: `content/raw/<book>/*__spells.html`."""
    pages: list[tuple[str, Path]] = []
    if not RAW.is_dir():
        return pages
    for book_dir in sorted(path for path in RAW.iterdir() if path.is_dir()):
        for file in sorted(book_dir.glob("*__spells.html")):
            pages.append((book_dir.name, file))
    return pages


def build_index() -> dict:
    pages = discover_pages()
    if not pages:
        raise SystemExit("немає сторінок «Spell Lists» у content/raw/*/ — спершу запустіть ingest")

    lists: dict[str, dict[str, dict[int, list[str]]]] = {}
    sources: dict[str, str] = {}
    problems: list[str] = []
    skipped: list[str] = []
    for book, path in pages:
        result = parse_page(book, path)
        if not result.lists:
            # Сторінка із закляттями, але без класових списків — це не помилка.
            skipped.append(book)
            continue
        problems.extend(f"{book}: {message}" for message in result.problems)
        sources[book] = result.page
        lists[book] = {
            class_name: {str(level): names for level, names in per_level.items()}
            for class_name, per_level in result.lists.items()
        }

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources,
        "skipped": skipped,
        "problems": problems,
        "lists": lists,
        "stats": {
            book: {
                class_name: sum(len(names) for names in per_level.values())
                for class_name, per_level in per_book.items()
            }
            for book, per_book in lists.items()
        },
    }


def load_corpus_spells() -> dict[str, set[str]]:
    """Книга → назви заклять з корпусу (для перевірки, що список не вигаданий)."""
    from dndsheet.compendium.infrastructure.jsonl_corpus import load_corpus

    corpus = load_corpus(CONTENT / "compendium")
    names: dict[str, set[str]] = {}
    for entry in corpus.entries:
        if entry.category.value == "spell":
            names.setdefault(entry.source_id, set()).add(entry.name_en.casefold())
    return names


def report(payload: dict) -> None:
    print(f"сторінок зі списками: {len(payload['sources'])}")
    if payload.get("skipped"):
        print("  без списків (не помилка): " + ", ".join(payload["skipped"]))
    for book, per_class in payload["stats"].items():
        counts = ", ".join(f"{name} {count}" for name, count in per_class.items())
        print(f"  {book}: {counts}")

    known = load_corpus_spells()
    unknown: list[str] = []
    for book, per_class in payload["lists"].items():
        corpus_names = known.get(book, set())
        for class_name, per_level in per_class.items():
            for names in per_level.values():
                for name in names:
                    if corpus_names and name.casefold() not in corpus_names:
                        unknown.append(f"{book}/{class_name}: {name}")
    if unknown:
        print(f"немає в корпусі ({len(unknown)}):")
        for line in unknown[:15]:
            print("  -", line)
    for problem in payload["problems"]:
        print("  !", problem)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Класові списки заклять з книг")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="записати індекс")
    group.add_argument("--check", action="store_true", help="не писати, лише порівняти")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    payload = build_index()
    current = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else None
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        if current is None:
            print(f"індексу немає: {TARGET.relative_to(ROOT)}")
            return 1
        stored = json.loads(current)
        if stored.get("lists") != payload["lists"]:
            print("індекс застарів: перезапустіть --write")
            return 1
        print("індекс класових списків актуальний")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(serialized, encoding="utf-8")
    if not args.quiet:
        report(payload)
        print(f"записано {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

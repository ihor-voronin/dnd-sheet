"""Реєстр джерел ← розібрані теки дзеркала 5e.tools.

Дописує в `content/sources.yml` записи про книги, текст яких уже лежить у
`content/raw/<тека>/` і розібраний у корпуси, але яких немає в `sources`.
Назва, рік і тип беруться з каталогу дзеркала (`books-5etools.json`,
`adventures-5etools.json`), категорії й кількості — з розібраних записів,
ліцензія — з таблиці `FREE` (решта — proprietary, це найобережніше
твердження, коли джерело — дзеркало, а не власна бібліотека).

Блок `free_official` — це книги, яких у нас немає; коли текст книги вже
розібраний, її запис переїздить звідти в `sources`, щоб не було двох записів
на одну книгу.

    python -m scripts.ingest.sync_sources            # що буде зроблено
    python -m scripts.ingest.sync_sources --write    # записати
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from . import config
from . import mirror5e

# Книги, які WotC роздає безкоштовно. Решта — proprietary.
FREE = {
    "ps-amonkhet",
    "ps-dominaria",
    "ps-innistrad",
    "ps-ixalan",
    "ps-kaladesh",
    "ps-zendikar",
    "al",
    "aitfr-avt",
    "aitfr-thp",
    "awm",
    "azfyt",
    "hftt",
    "mgelft",
    "nrh-at",
    "nrh-tlt",
    "rmbre",
    "xmts",
}

TYPE_BY_GROUP = {
    "core": "core",
    "setting": "sourcebook",
    "setting-alt": "sourcebook",
    "supplement": "sourcebook",
    "supplement-alt": "sourcebook",
    "organized-play": "accessory",
}

CATEGORY_ORDER = ("class", "subclass", "species", "background", "feat",
                  "optionalfeature", "spell", "item", "monster", "rule")

PLURALS = {
    "monster": ("статблок", "статблоки", "статблоків"),
    "item": ("предмет", "предмети", "предметів"),
    "species": ("вид", "види", "видів"),
    "background": ("передісторія", "передісторії", "передісторій"),
    "feat": ("риса", "риси", "рис"),
    "optionalfeature": ("опційне вміння", "опційні вміння", "опційних умінь"),
    "subclass": ("підклас", "підкласи", "підкласів"),
    "spell": ("закляття", "закляття", "заклять"),
    "class": ("клас", "класи", "класів"),
    "rule": ("розділ правил", "розділи правил", "розділів правил"),
}


def plural(count: int, forms: tuple[str, str, str]) -> str:
    one, few, many = forms
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def load_registry() -> dict:
    return yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))


def _counts(folder: str, mapping, catalogue, feature_index) -> dict[str, int]:
    records = mirror5e.build_folder(
        folder,
        mapping=mapping,
        catalogue=catalogue,
        sources={},
        fetched_at="",
        feature_index=feature_index,
    )
    counts: dict[str, int] = {}
    for entry in records:
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1
    return counts


def _catalogue_entry(folder: str, catalogue: dict[str, dict],
                     inverse: dict[str, str]) -> dict | None:
    """Запис каталогу для теки: спершу за кодом книги, потім за назвою теки.

    Коди дзеркала й теки не збігаються (PS-A → ps-amonkhet, MaBJoV → mabjov),
    тому основний шлях — обернена мапа з mirror5e.folder_sources.
    """
    code = inverse.get(folder)
    if code and code in catalogue:
        return catalogue[code]
    for key, entry in catalogue.items():
        if key.lower() == folder or str(entry.get("source", "")).lower() == folder:
            return entry
    return None


def _scope(counts: dict[str, int]) -> str:
    if any(category in counts for category in
           ("class", "subclass", "species", "background", "feat",
            "optionalfeature", "spell")):
        return "sheet"
    if "item" in counts:
        return "items"
    if "monster" in counts:
        return "monsters"
    return "excluded"


def _note(counts: dict[str, int]) -> str:
    if not counts:
        return "Текст книги на дзеркалі є, але жодної сутності для листка вона не дає"
    parts = []
    for category in CATEGORY_ORDER:
        if category in counts:
            count = counts[category]
            parts.append(f"{count} {plural(count, PLURALS[category])}")
    return "З дзеркала 5e.tools: " + ", ".join(parts)


def _entry_lines(folder: str, catalogue_entry: dict | None, counts: dict[str, int]) -> list[str]:
    title = (catalogue_entry or {}).get("name") or folder
    year = str((catalogue_entry or {}).get("published") or "")[:4]
    group = str((catalogue_entry or {}).get("group") or "supplement")
    kind = (catalogue_entry or {}).get("_kind")
    book_type = "adventure" if kind == "adventure" else TYPE_BY_GROUP.get(group, "sourcebook")
    mirror_id = (catalogue_entry or {}).get("id") or folder
    categories = [category for category in CATEGORY_ORDER if category in counts]
    lines = [
        f"  - id: {folder}",
        f"    title: {json.dumps(title, ensure_ascii=False)}",
        f"    type: {book_type}",
    ]
    if year.isdigit():
        lines.append(f"    year: {year}")
    lines += [
        "    tier: 3",
        f"    mirror: {mirror_id}",
        f"    license: {'free' if folder in FREE else 'proprietary'}",
        f"    scope: {_scope(counts)}",
    ]
    if categories:
        lines.append("    categories: [" + ", ".join(categories) + "]")
    lines += ["    status: ingested", f"    note: {json.dumps(_note(counts), ensure_ascii=False)}"]
    return lines


def _list_block(lines: list[str], start: int) -> tuple[int, int]:
    """Межі списку під ключем на рядку `start`: від наступного рядка до кінця."""
    index = start + 1
    while index < len(lines) and (lines[index].startswith(("  ", "\t")) or not lines[index].strip()):
        index += 1
    return start + 1, index


def _split_entries(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Розбити рядки списку на записи за рядком «  - id: …»."""
    entries: list[tuple[str, list[str]]] = []
    current_id: str | None = None
    current: list[str] = []
    for line in lines:
        match = re.match(r"\s*-\s+id:\s*(\S+)", line)
        if match:
            if current_id is not None:
                entries.append((current_id, current))
            current_id = match.group(1)
            current = [line]
        elif current_id is not None:
            current.append(line)
    if current_id is not None:
        entries.append((current_id, current))
    return entries


def plan(force: bool = False) -> tuple[list[str], list[str], dict[str, dict[str, int]]]:
    registry = load_registry()
    sources = {entry["id"] for entry in registry.get("sources") or []}
    if force:
        # --force перегенеровує записи тек дзеркала, тому вони не «вже є».
        sources -= set(mirror5e.mirror_folders())
    free = {entry["id"]: entry for entry in registry.get("free_official") or []}
    folders = mirror5e.mirror_folders()
    catalogue = mirror5e.load_catalogue()
    mapping = mirror5e.folder_sources(folders + list(sources))
    inverse: dict[str, str] = {}
    for code, folder in mapping.items():
        if code in catalogue:
            inverse.setdefault(folder, code)
    _, _, feature_index = mirror5e.class_data()

    new_entries: list[str] = []
    moved: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    for folder in folders:
        if folder in sources:
            counts[folder] = _counts(folder, mapping, catalogue, feature_index)
            continue
        got = _counts(folder, mapping, catalogue, feature_index)
        counts[folder] = got
        new_entries.extend(
            _entry_lines(folder, _catalogue_entry(folder, catalogue, inverse), got)
        )
        if folder in free:
            moved.append(folder)
    return new_entries, moved, counts


def _drop_entries(lines: list[str], drop: set[str]) -> list[str]:
    """Прибрати записи sources із цими id (разом із їхніми рядками)."""
    out: list[str] = []
    index = 0
    while index < len(lines):
        match = re.match(r"  - id:\s*(\S+)", lines[index])
        if match and match.group(1) in drop:
            index += 1
            while index < len(lines) and lines[index].startswith("    "):
                index += 1
            continue
        out.append(lines[index])
        index += 1
    return out


def write(new_entries: list[str], moved: list[str], *, force: bool = False) -> None:
    text = config.SOURCES_FILE.read_text(encoding="utf-8")
    lines = text.splitlines()
    if force:
        drop = {
            match.group(1)
            for line in lines
            if (match := re.match(r"  - id:\s*(\S+)", line))
        } & set(mirror5e.mirror_folders())
        lines = _drop_entries(lines, drop)
        lines = [
            line
            for line in lines
            if not line.startswith("# ---------- З дзеркала 5e.tools")
            and not line.startswith("# Книги, чий текст узяли з дзеркала")
            and not line.startswith("# розібрано 2026-11-26, license=proprietary")
            and not line.startswith("# підтверджена. Поле mirror")
        ]
        text = "\n".join(lines)

    # 1) прибрати з free_official записи, які переїхали в sources
    if moved:
        free_line = next(i for i, line in enumerate(lines) if line.startswith("free_official:"))
        start, end = _list_block(lines, free_line)
        entries = _split_entries(lines[start:end])
        kept: list[str] = []
        for entry_id, entry_lines in entries:
            if entry_id in moved:
                continue
            kept.extend(entry_lines)
        lines[start:end] = kept + [""]
        text = "\n".join(lines)
        lines = text.splitlines()

    # 2) дописати нові записи в кінець sources
    if new_entries:
        anchor = next(i for i, line in enumerate(lines) if line.startswith("free_official:"))
        while anchor > 0 and lines[anchor - 1].startswith("#"):
            anchor -= 1
        header = [
            "# ---------- З дзеркала 5e.tools ----------",
            "# Книги, чий текст узяли з дзеркала (не з власної бібліотеки D&D Beyond):",
            "# розібрано 2026-11-26, license=proprietary там, де безкоштовність не",
            "# підтверджена. Поле mirror — id книги на 5e.tools (він же суфікс URL).",
        ]
        block = [""] + header + new_entries
        lines[anchor:anchor] = block
    config.SOURCES_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    parser = argparse.ArgumentParser(prog="scripts.ingest.sync_sources")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="перегенерувати записи тек дзеркала (видалити й додати)")
    args = parser.parse_args(argv)

    new_entries, moved, counts = plan(force=args.force)
    folders = len(counts)
    print(f"тек дзеркала: {folders}")
    for folder, got in sorted(counts.items()):
        summary = ", ".join(f"{key}={value}" for key, value in sorted(got.items()))
        print(f"  {folder:14s} {summary or '—'}")
    ids = [line.split(":", 1)[1].strip() for line in new_entries if line.startswith("  - id:")]
    print(f"\nдодати в sources: {len(ids)}")
    if moved:
        print(f"перенести з free_official: {', '.join(sorted(moved))}")
    if not args.write:
        print("\n(нічого не записано — додайте --write)")
        return 0
    write(new_entries, moved, force=args.force)
    print("\nsources.yml перезаписано й перевірено парсером")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

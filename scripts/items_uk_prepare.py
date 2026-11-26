"""Нарізка предметів на черги для перекладу українською.

Корпус тримає 1562 записи предметів із 54 книг, але унікальних назв — 1135.
Назви перекладаємо всі: без них у каталозі мішанина з двох мов. Описи —
лише там, де є справжній текст (базові правила, 235 записів): решта — це
рядки таблиць («Longsword · 15 gp · 3 lb. »), і їх збирає сама програма з
полів `data`, перекладати нічого.

Черга — це один файл: агент читає його, пише переклад у файл із тим самим
імʼям у `out/`. Розмір порізаний так, щоб один агент не читав більше за
~9 тисяч символів: довші записи (Deck of Many Things — 7.8 тис.) ідуть
окремо, інакше агент губить кінець.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPENDIUM = ROOT / "content" / "compendium"
WORK = ROOT / "var" / "translations" / "items"
IN_DIR = WORK / "in"
OUT_DIR = WORK / "out"

#: Мінімум, з якого текст вважаємо описом, а не рядком таблиці.
PROSE = 120
#: Описи перекладаємо спершу для базових правил: це той самий набір, що в
#: безкоштовних правилах, і саме він дає змістовний текст, а не рядок таблиці.
#: Пригоди й сеттінги лишаються англійською, доки не дійде черга.
PROSE_SOURCES = {"basic-rules-2014"}
#: Скільки символів англійського тексту кладемо в одну чергу.
TEXT_BUDGET = 9000
#: Скільки назв в одній черзі.
NAME_BUDGET = 60
#: Один запис, довший за це, іде в чергу сам.
HUGE = 4000


def read_items() -> list[dict]:
    records: list[dict] = []
    for path in sorted(COMPENDIUM.glob("*/item.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def main() -> None:
    for directory in (IN_DIR, OUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        for stale in directory.glob("*.json"):
            stale.unlink()

    records = read_items()
    #: Один предмет у кількох книгах: назву беремо з базових правил, а якщо
    #: його там немає — з першої книги за абеткою, щоб вибір був сталий.
    by_name: dict[str, dict] = {}
    for record in sorted(
        records,
        key=lambda row: (row["source_id"] != "basic-rules-2014", row["source_id"]),
    ):
        key = record["name_en"].strip().casefold()
        by_name.setdefault(key, record)
    unique = sorted(by_name.values(), key=lambda row: row["name_en"].casefold())

    prose = [
        row
        for row in unique
        if len(row.get("text_en") or "") > PROSE and row["source_id"] in PROSE_SOURCES
    ]
    prose_ids = {row["id"] for row in prose}
    names_only = [row for row in unique if row["id"] not in prose_ids]

    texts = _pack_texts(prose)
    names = _pack_names(names_only)

    index = {"names": [], "texts": []}
    for number, chunk in enumerate(texts, start=1):
        name = f"text-{number:02d}.json"
        _dump(IN_DIR / name, {"kind": "text", "items": chunk})
        index["texts"].append(name)
    for number, chunk in enumerate(names, start=1):
        name = f"names-{number:02d}.json"
        _dump(IN_DIR / name, {"kind": "names", "items": chunk})
        index["names"].append(name)

    _dump(WORK / "index.json", index)
    total_chars = sum(len(row.get("text_en") or "") for row in prose)
    print(
        f"записів: {len(records)}, унікальних назв: {len(unique)}, "
        f"з описом: {len(prose)} ({total_chars} символів), "
        f"лише назви: {len(names_only)}"
    )
    print(f"черг: назви {len(names)}, описи {len(texts)}")


def _pack_texts(rows: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for row in rows:
        text = row.get("text_en") or ""
        item = {"id": row["id"], "name_en": row["name_en"], "text_en": text}
        if len(text) > HUGE:
            if current:
                chunks.append(current)
                current, size = [], 0
            chunks.append([item])
            continue
        if current and (size + len(text) > TEXT_BUDGET or len(current) >= 12):
            chunks.append(current)
            current, size = [], 0
        current.append(item)
        size += len(text)
    if current:
        chunks.append(current)
    return chunks


def _pack_names(rows: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    for start in range(0, len(rows), NAME_BUDGET):
        chunks.append(
            [
                {"id": row["id"], "name_en": row["name_en"]}
                for row in rows[start : start + NAME_BUDGET]
            ]
        )
    return chunks


def _dump(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

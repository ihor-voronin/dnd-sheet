"""HTML сторінок → записи компендіуму (JSONL за схемою contract/compendium-entry.schema.json)."""

from __future__ import annotations

import datetime as dt
import json
import re
import sys

import yaml

from ..normalize import canonical as compendium_format
from . import config, discover, entities, html2md

CATEGORY_BY_PREFIX = {
    "spells": "spell",
    "spell": "spell",
    "equipment": "item",
    "magic-items": "item",
    "items": "item",
    "monsters": "monster",
    "bestiary": "monster",
    "backgrounds": "background",
    "feats": "feat",
    "races": "species",
    "species": "species",
    "classes": "class",
}

CLASS_SLUGS = {
    "barbarian",
    "bard",
    "cleric",
    "druid",
    "fighter",
    "monk",
    "paladin",
    "ranger",
    "rogue",
    "sorcerer",
    "warlock",
    "wizard",
}

HEADER_FIELD_RE = re.compile(r"^\s{0,3}(?P<key>[A-Za-z][A-Za-z \-/]{1,30}):\s*(?P<value>.+)$")

# Скільки тексту сторінки має лишитися поза сутностями, щоб це був окремий
# запис-розділ, а не залишок розмітки.
PAGE_REMAINDER_MIN = 800


def _compact_with_offsets(text: str) -> tuple[str, list[int]]:
    """Текст без повторних пробілів + карта «стиснута позиція → позиція в оригіналі»."""
    chars: list[str] = []
    offsets: list[int] = []
    previous_space = True
    for index, char in enumerate(text):
        if char.isspace():
            if previous_space:
                continue
            chars.append(" ")
            offsets.append(index)
            previous_space = True
        else:
            chars.append(char)
            offsets.append(index)
            previous_space = False
    while chars and chars[-1] == " ":
        chars.pop()
        offsets.pop()
    return "".join(chars), offsets


def _remainder(markdown: str, items: list[dict]) -> str:
    """Текст сторінки, який не ввійшов у сутності (лор, вставки, таблиці).

    Порівняння йде по тексту зі стиснутими пробілами: абзаци markdown
    збираються назад із різною кількістю порожніх рядків, тому пряме
    входження підрядка не завжди працює. Якщо ж сутність не знайдена взагалі
    (так буває з закляттями — їхній текст не містить рядків «Casting Time»),
    повертаємо сторінку цілком, і виклик бачить, що це сторінка-список.
    """
    compact, offsets = _compact_with_offsets(markdown)
    spans: list[tuple[int, int]] = []
    for item in items:
        key, _ = _compact_with_offsets(item["text"])
        if not key:
            continue
        position = compact.find(key)
        if position < 0:
            continue
        spans.append((offsets[position], offsets[position + len(key) - 1] + 1))
    spans.sort()

    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            pieces.append(markdown[cursor:start])
        cursor = max(cursor, end)
    pieces.append(markdown[cursor:])
    text = "".join(pieces)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def categorize(page_path: str) -> str:
    parts = [part for part in page_path.split("/") if part]
    if not parts:
        return "rule"
    prefix = parts[0].lower()
    # Класи в PHB лежать окремими сторінками (barbarian, bard, ...), а не під
    # загальним префіксом classes, тому їх треба назвати явно.
    if prefix in CLASS_SLUGS:
        return "subclass" if len(parts) >= 2 else "class"
    if prefix.startswith("spell-descriptions"):
        return "spell"
    if prefix.startswith("appendix-d-creature"):
        return "monster"
    category = CATEGORY_BY_PREFIX.get(prefix)
    if category is None:
        return "rule"
    if category == "class" and len(parts) >= 3:
        return "subclass"
    return category


def extract_data(markdown: str, category: str) -> dict:
    """Витягує пари `Поле: значення` з перших рядків; для заклять — окремі ключі."""
    data: dict = {}
    for line in markdown.splitlines()[:40]:
        match = HEADER_FIELD_RE.match(line)
        if not match:
            continue
        key = match.group("key").strip().lower().replace(" ", "_").replace("-", "_")
        value = match.group("value").strip()
        if len(value) > 200 or key in data:
            continue
        data[key] = value
    if category == "spell":
        header = "\n".join(markdown.splitlines()[:25])
        level = _first_int(data.get("level", ""))
        if level is None:
            match = re.search(r"(\d+)(?:st|nd|rd|th)?[-\s]level", header, re.IGNORECASE)
            if match:
                level = int(match.group(1))
            elif re.search(r"\bcantrip\b", header, re.IGNORECASE):
                level = 0
        data["level"] = level
        school = re.search(
            r"(abjuration|conjuration|divination|enchantment|evocation|illusion"
            r"|necromancy|transmutation)",
            header,
            re.IGNORECASE,
        )
        data["school"] = school.group(1).lower() if school else None
        data["ritual"] = "ritual" in header.lower()
        data["concentration"] = "concentration" in (data.get("duration", "") or "").lower()
        data["classes"] = [part.strip() for part in re.split(r"[,/]", str(data.get("classes", ""))) if part.strip()]
    return data


def _first_int(text: str) -> int | None:
    match = re.search(r"\d+", text or "")
    return int(match.group()) if match else None


def load_sources() -> dict[str, dict]:
    raw = yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in raw.get("sources", [])}


def _make_record(
    *,
    source: str,
    category: str,
    name: str,
    slug: str,
    text: str,
    data: dict,
    license_value: str,
    url: str,
    fetched_at: str,
) -> dict:
    return {
        "id": f"{source}/{category}/{slug}",
        "schema": "compendium-entry/1",
        "source_id": source,
        "category": category,
        "name_en": name,
        "name_uk": None,
        "edition": "2014",
        "license": license_value,
        "url": url,
        "page": None,
        "text_en": text,
        "text_uk": None,
        "data": data,
        "status": "raw",
        "fetched_at": fetched_at,
        "notes": [],
    }


def _deduplicate(records: list[dict]) -> list[dict]:
    """Один id — один запис: лишаємо повніший, згадку про інший — у notes.

    Трапляється, коли та сама назва приходить із двох шарів книги: «Potion of
    healing» є і рядком таблиці спорядження (ціна, вага), і описом магічного
    предмета. Обидва потрібні, але id мусить бути унікальним, інакше в базі
    два записи з тим самим ключем.
    """
    best: dict[str, dict] = {}
    for record in records:
        record_id = record["id"]
        if record_id not in best:
            best[record_id] = record
            continue
        previous = best[record_id]
        keep, drop = (record, previous) if len(record["text_en"]) > len(previous["text_en"]) else (previous, record)
        keep = dict(keep)
        notes = list(keep.get("notes") or [])
        notes.append("той самий id мав коротший запис: " + drop["text_en"].strip().splitlines()[0][:160])
        keep["notes"] = notes
        best[record_id] = keep
    return list(best.values())


def parse_source(source: str) -> dict[str, int]:
    source_meta = load_sources().get(source, {})
    license_value = source_meta.get("license", "proprietary")
    directory = config.RAW_DIR / source
    if not directory.exists():
        raise FileNotFoundError(f"Немає сирих даних {directory} — спочатку fetch")

    records: list[dict] = []
    seen_tails: set[str] = set()
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    for file in sorted(
        directory.glob("*.html"),
        key=lambda path: (
            0 if discover.tail_of(path.stem.replace("__", "/")) else 1,
            path.stem,
        ),
    ):
        rel = file.stem.replace("__", "/")
        page_path = discover.tail_of(rel)
        if not page_path or page_path in seen_tails:
            continue  # корінь книги або дубль під іншим шляхом
        seen_tails.add(page_path)
        try:
            html = file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        title, markdown = html2md.parse_page(html)
        if not title or len(markdown) < 80:
            continue
        category = categorize(page_path)
        url = discover.page_url(rel)

        # Сторінка-розділ містить десятки сутностей (напр. 41 закляття на
        # «Spell Descriptions (A-B)») — ріжемо на окремі записи, інакше білдер
        # персонажа не зможе вибрати одне закляття.
        items = entities.split_page(page_path, markdown, scope=source_meta.get("scope"))
        if items:
            for item in items:
                records.append(
                    _make_record(
                        source=source,
                        category=item["category"],
                        name=item["name"],
                        slug=entities.slugify(item["name"]),
                        text=item["text"],
                        data=item["data"],
                        license_value=license_value,
                        url=url,
                        fetched_at=fetched_at,
                    )
                )
            # Що із сторінки не ввійшло в сутності, теж потрібне: на сторінках
            # Mordenkainen's Tome і Volo's статблоки займають ~3/4 тексту, а
            # решта — лор про групу істот; у пригодах поруч зі статблоками
            # лежить опис локації. Тому сторінковий запис лишаємо з тим
            # текстом, що не став сутністю, — без дублювання статблоків.
            rest = _remainder(markdown, items)
            if rest.strip() == markdown.strip():
                # Жодна сутність не зіставилася з текстом сторінки: так буває
                # з закляттями (їхній текст не містить рядків «Casting Time»)
                # і з таблицями спорядження (рядок таблиці перетворюється на
                # «Group · Name · 15 gp · 3 lb.»). Різниця принципова: сторінка
                # заклять — це і є список сутностей, а сторінка спорядження
                # містить правила, яких у таблицях немає.
                covered = sum(len(item["text"]) for item in items)
                page_text = "" if covered >= 0.6 * len(markdown) else markdown
            else:
                page_text = rest
            if len(page_text) >= PAGE_REMAINDER_MIN:
                records.append(
                    _make_record(
                        source=source,
                        category=category,
                        name=title,
                        slug=re.sub(r"[^a-z0-9./-]+", "-", page_path.lower()).strip("-"),
                        text=page_text,
                        data={},
                        license_value=license_value,
                        url=url,
                        fetched_at=fetched_at,
                    )
                )
            continue

        records.append(
            _make_record(
                source=source,
                category=category,
                name=title,
                slug=re.sub(r"[^a-z0-9./-]+", "-", page_path.lower()).strip("-"),
                text=markdown,
                data=extract_data(markdown, category),
                license_value=license_value,
                url=url,
                fetched_at=fetched_at,
            )
        )

    # Один id — один запис, і кожен запис — у канонічному форматі
    # (contract/compendium-format.json), щоб корпус не залежав від того, який
    # конвеєр його зібрав.
    records = _deduplicate(records)
    spec = compendium_format.load_spec()
    records = [compendium_format.canonicalize(record, spec)[0] for record in records]

    counters: dict[str, int] = {}
    spec = compendium_format.load_spec()
    by_corpus: dict[str, dict[str, list[dict]]] = {}
    for record in records:
        # Кожна категорія живе у своєму корпусі (contract/compendium-format.json):
        # монстри — окремо від того, що читає лист персонажа.
        corpus = spec.corpus_of(record["category"])
        by_corpus.setdefault(corpus, {}).setdefault(record["category"], []).append(record)

    for corpus, by_category in by_corpus.items():
        target_dir = spec.corpus_dir(corpus) / source
        target_dir.mkdir(parents=True, exist_ok=True)
        for category, items in by_category.items():
            target = target_dir / f"{category}.jsonl"
            with target.open("w", encoding="utf-8") as handle:
                for item in items:
                    handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            counters[category] = len(items)

    # Прибираємо категорії, яких після нового розбору більше немає: інакше в
    # базі лишаються записи від попередньої версії розпізнавачів, і зведення
    # по книзі показує більше, ніж є насправді. Обходимо всі корпуси — інакше
    # файл, чия категорія переїхала в інший корпус, лишився б дублем.
    for corpus in spec.corpus_names():
        directory = spec.corpus_dir(corpus) / source
        if not directory.is_dir():
            continue
        written = set(by_corpus.get(corpus, {}))
        for stale in directory.glob("*.jsonl"):
            if stale.stem not in written:
                stale.unlink()

    counters["_total"] = len(records)
    return counters


def validate_source(source: str) -> list[str]:
    """Перевіряє JSONL проти JSON Schema. Повертає список проблем."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema не встановлено — валідацію пропущено"]

    schema = json.loads(config.SCHEMA_FILE.read_text(encoding="utf-8"))
    problems: list[str] = []
    spec = compendium_format.load_spec()
    for directory in (spec.corpus_dir(name) / source for name in spec.corpus_names()):
        if not directory.is_dir():
            continue
        for file in sorted(directory.glob("*.jsonl")):
            for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                try:
                    jsonschema.validate(record, schema)
                except jsonschema.ValidationError as exc:
                    problems.append(f"{file.name}:{number}: {exc.message}")
                if len(problems) > 50:
                    return problems
    return problems


def summarize(counters: dict[str, int]) -> str:
    parts = [f"{key}={value}" for key, value in sorted(counters.items())]
    return ", ".join(parts)


if __name__ == "__main__":
    print(summarize(parse_source(sys.argv[1])))

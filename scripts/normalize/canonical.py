"""Канонічний формат записів довідника: одна категорія — одна форма.

Навіщо це окремий шар. Корпус збирають чотири різні конвеєри: HTML зі сторінок
D&D Beyond, сторінка за сторінкою; OCR сканованого PDF (Glory of the Giants);
текстовий шар PDF (Elemental Evil); рукописні правила й сутності в білдерах.
Кожен писав `data` своїми ключами й `text_en` своїм способом — тому «всі
закляття» на ділі мали три різні формати, а «всі монстри» — п'ятдесят п'ять
наборів ключів. Цей модуль зводить кожну категорію до однієї форми:

* `data` — однаковий набір і порядок ключів; невідоме `null`, прапорці `false`;
* `text_en` — однаковий скелет тексту для категорії;
* порядок полів запису — як у `entry_keys`.

Специфікація — `contract/compendium-format.json` (єдине джерело істини).
Модуль навмисно на stdlib: його викликають і конвеєри, і `scripts/preflight.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORMAT_FILE = ROOT / "contract" / "compendium-format.json"

# Порядкові числівники для рядка рівня закляття.
def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


SHORT_ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
LONG_ABILITIES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
SPELL_SCHOOLS = (
    r"(?:abjuration|conjuration|divination|enchantment|evocation|illusion"
    r"|necromancy|transmutation)"
)
# «8th-level necromancy», «3rd-Level Transmutation», «Conjuration cantrip».
# Школа обовʼязкова: інакше «3rd-level Beast Master feature» теж зійшло б за
# закляття, і вміння класу потрапило б у категорію заклять.
SPELL_LINE_RE = re.compile(
    rf"^(?:\d{{1,2}}(?:st|nd|rd|th)[-\s]+level\s+{SPELL_SCHOOLS}\b.*"
    rf"|[A-Za-z][A-Za-z' ]*\s+cantrip)$",
    re.IGNORECASE,
)
PREREQ_RE = re.compile(r"^Prerequisite[:.]\s*(.*)$", re.IGNORECASE)


# --- специфікація ---------------------------------------------------------

class FormatSpec:
    """Завантажена й перевірена специфікація формату."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.entry_keys: list[str] = list(payload["entry_keys"])
        self.categories: dict[str, dict] = dict(payload["categories"])
        self.corpora: dict[str, dict] = {
            name: rules
            for name, rules in (payload.get("corpora") or {}).items()
            if not name.startswith("$")
        }
        self.refine: dict = dict(payload.get("refine") or {})

    # --- доступ ---
    def text_style(self, category: str) -> str:
        return self.categories[category]["text"]

    def data_kinds(self, category: str) -> dict[str, str]:
        return dict(self.categories[category]["data"])

    def data_keys(self, category: str) -> list[str]:
        return list(self.categories[category]["data"])

    def categories_ordered(self) -> list[str]:
        return list(self.categories)

    # --- корпуси ---
    def corpus_names(self) -> list[str]:
        return list(self.corpora)

    def corpus_categories(self, corpus: str) -> list[str]:
        return list(self.corpora[corpus]["categories"])

    def corpus_dir(self, corpus: str) -> Path:
        return ROOT / str(self.corpora[corpus]["dir"])

    def corpus_of(self, category: str) -> str:
        """Назва корпусу, у якому живе категорія."""
        for name, rules in self.corpora.items():
            if category in rules["categories"]:
                return name
        raise KeyError(category)

    def category_dir(self, category: str, source: str) -> Path:
        """Тека книги в тому корпусі, якому належить категорія."""
        return self.corpus_dir(self.corpus_of(category)) / source


def load_spec(path: Path | None = None) -> FormatSpec:
    source = Path(path) if path else FORMAT_FILE
    payload = json.loads(source.read_text(encoding="utf-8"))
    _validate_spec(payload, source)
    return FormatSpec(payload)


def _validate_spec(payload: dict, source: Path) -> None:
    problems: list[str] = []
    if payload.get("schema") != "compendium-format/1":
        problems.append("schema != compendium-format/1")
    keys = payload.get("entry_keys")
    if not isinstance(keys, list) or "text_en" not in keys or "data" not in keys:
        problems.append("entry_keys неповний")
    categories = payload.get("categories")
    if not isinstance(categories, dict) or not categories:
        problems.append("categories порожні")
    else:
        for name, rules in categories.items():
            if rules.get("text") not in {"spell-block", "prose", "section"}:
                problems.append(f"{name}: невідомий text-скелет {rules.get('text')!r}")
            data = rules.get("data")
            if not isinstance(data, dict):
                problems.append(f"{name}: data має бути об'єктом")
                continue
            for key, kind in data.items():
                if kind not in {
                    "str",
                    "str_lower",
                    "int",
                    "bool",
                    "lower",
                    "abilities",
                    "ability_increases",
                }:
                    problems.append(f"{name}.{key}: невідомий тип {kind!r}")
    corpora = payload.get("corpora")
    if not isinstance(corpora, dict) or not corpora:
        problems.append("corpora порожні")
    else:
        owner: dict[str, str] = {}
        for name, rules in corpora.items():
            if name.startswith("$"):
                continue
            directory = rules.get("dir") if isinstance(rules, dict) else None
            listed = rules.get("categories") if isinstance(rules, dict) else None
            if not directory or not isinstance(listed, list) or not listed:
                problems.append(f"corpus {name}: потрібні dir і categories")
                continue
            for category in listed:
                if category in owner:
                    problems.append(
                        f"категорія {category!r} у двох корпусах: {owner[category]}, {name}"
                    )
                owner[category] = name
                if isinstance(categories, dict) and category not in categories:
                    problems.append(f"corpus {name}: невідома категорія {category!r}")
        if isinstance(categories, dict):
            orphans = sorted(set(categories) - set(owner))
            if orphans:
                problems.append("категорії без корпусу: " + ", ".join(orphans))
    if problems:
        raise ValueError(f"{source}: " + "; ".join(problems))


# --- допоміжне для тексту -------------------------------------------------

def _first_line(text: str) -> str:
    return text.split("\n", 1)[0] if text else ""


def _title_key(title: str) -> str:
    """Нормалізована назва для порівняння заголовка з name_en."""
    return re.sub(r"\s+", " ", title).strip().strip(".").casefold()


def _heading_title(text: str) -> str | None:
    match = HEADING_RE.match(_first_line(text))
    return match.group(2).strip().rstrip(".") if match else None


def clean_text(text: str) -> str:
    """Гігієна тексту, спільна для всіх категорій."""
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "").replace("\u00ad", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def spell_header(level, school) -> str | None:
    """Рядок «8th-level necromancy» / «Conjuration cantrip»."""
    if level is None or not school:
        return None
    school = str(school).strip().lower()
    if not school:
        return None
    if int(level) == 0:
        return f"{school.capitalize()} cantrip"
    return f"{_ordinal(int(level))}-level {school}"


def _strip_leading_heading(text: str) -> str:
    if not HEADING_RE.match(_first_line(text)):
        return text
    _, _, rest = text.partition("\n")
    return rest.lstrip("\n")


def _strip_spell_line(text: str) -> str:
    if not SPELL_LINE_RE.match(_first_line(text).strip()):
        return text
    _, _, rest = text.partition("\n")
    return rest.lstrip("\n")


def _strip_prerequisite(text: str, data: dict) -> str:
    match = PREREQ_RE.match(_first_line(text).strip())
    if not match:
        return text
    value = match.group(1).strip()
    if value and not data.get("prerequisite"):
        data["prerequisite"] = value
    _, _, rest = text.partition("\n")
    return rest.lstrip("\n")


def _canonical_text(
    category: str, name: str, text: str, data: dict, spec: FormatSpec
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    style = spec.text_style(category)
    before = text

    if style == "spell-block":
        title = _heading_title(text)
        if title is not None:
            text = _strip_leading_heading(text)
            reasons.append(f"text_en: прибрано заголовок «{title}»")
        if SPELL_LINE_RE.match(_first_line(text).strip()):
            text = _strip_spell_line(text)
            reasons.append("text_en: прибрано рядок рівня неканонічного вигляду")
        header = spell_header(data.get("level"), data.get("school"))
        if header:
            text = f"{header}\n\n{text}".strip()
            if not before.startswith(header):
                reasons.append(f"text_en: додано рядок «{header}»")

    elif style == "prose":
        title = _heading_title(text)
        if title is not None and _title_key(title) == _title_key(name):
            text = _strip_leading_heading(text)
            reasons.append(f"text_en: прибрано дубль заголовка «{title}»")
        if category == "feat" and PREREQ_RE.match(_first_line(text).strip()):
            text = _strip_prerequisite(text, data)
            reasons.append("text_en: рядок «Prerequisite» перенесено в data.prerequisite")

    elif style == "section":
        heading = HEADING_RE.match(_first_line(text).strip())
        if heading is None:
            text = f"# {name}\n\n{text}".strip()
            reasons.append("text_en: додано заголовок розділу")
        elif len(heading.group(1)) > 1:
            # Розділ мусить починатися з заголовка першого рівня: підрозділ
            # («#### M1. Foyer») — це вже тіло, а назва запису — над ним.
            text = f"# {name}\n\n{text}".strip()
            reasons.append("text_en: додано заголовок над підрозділом")

    text = clean_text(text)
    if text == before:
        # Розбір «прибрали рядок і додали той самий» не є зміною тексту.
        return text, []
    if not reasons:
        reasons.append("text_en: пробіли/порожні рядки")
    return text, reasons


# --- допоміжне для data ---------------------------------------------------

def _as_str(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _as_str_lower(value) -> str | None:
    text = _as_str(value)
    return text.lower() if text else None


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else None


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "так"}


def _as_lower_list(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parts = re.split(r"[,/;]", value)
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        return None
    cleaned = sorted({str(part).strip().lower() for part in parts if str(part).strip()})
    return cleaned or None


def _as_ability_scores(value, keys: tuple[str, ...]) -> dict[str, int | None]:
    scores: dict[str, int | None] = {key: None for key in keys}
    if isinstance(value, dict):
        for key in keys:
            scores[key] = _as_int(value.get(key))
    return scores


_KIND_COERCERS = {
    "str": _as_str,
    "str_lower": _as_str_lower,
    "int": _as_int,
    "bool": _as_bool,
    "lower": _as_lower_list,
    "abilities": lambda value: _as_ability_scores(value, SHORT_ABILITIES),
    "ability_increases": lambda value: _as_ability_scores(value, LONG_ABILITIES),
}

_BOOL_DEFAULTS = {"bool"}


def _default_for(kind: str):
    if kind in _BOOL_DEFAULTS:
        return False
    if kind in {"abilities", "ability_increases"}:
        return _KIND_COERCERS[kind]({})
    return None


def _canonical_data(category: str, data: dict, spec: FormatSpec) -> tuple[dict, list[str]]:
    kinds = spec.data_kinds(category)
    output: dict = {}
    added: list[str] = []
    for key, kind in kinds.items():
        coerce = _KIND_COERCERS[kind]
        if key in data and data[key] is not None:
            output[key] = coerce(data[key])
        else:
            output[key] = _default_for(kind)
            if key not in data:
                added.append(key)
    dropped = [key for key in data if key not in kinds]
    reasons: list[str] = []
    if added:
        reasons.append("data: додано ключі " + ", ".join(added))
    if dropped:
        shown = ", ".join(sorted(dropped)[:6])
        more = " …" if len(dropped) > 6 else ""
        reasons.append(f"data: прибрано ключі {shown}{more}")
    if not added and not dropped and list(data) != list(kinds):
        if set(data) == set(kinds):
            reasons.append("data: інший порядок ключів")
    return output, reasons


# --- категорія ------------------------------------------------------------

def refine_category(
    category: str, name: str, text: str, data: dict, spec: FormatSpec
) -> tuple[str, str]:
    """Механічне виправлення категорії (розділ → правило, закляття → закляття)."""
    entity_categories = set(spec.refine.get("entity_categories") or [])
    prefixes = tuple(spec.refine.get("chapter_prefixes") or [])
    section_titles = set(spec.refine.get("section_titles") or [])

    first = _first_line(text).strip()
    title = _heading_title(text)

    if title is not None and category in entity_categories:
        key = _title_key(title)
        if (prefixes and key.startswith(prefixes)) or key in section_titles:
            return "rule", f"сторінка-розділ «{title}»"
        if _title_key(title) != _title_key(name):
            # Сутність починається з чужого заголовка: це не статблок і не
            # опис предмета, а сторінка-розділ (Sage Advice, сторінка вміння).
            return "rule", f"сторінка-розділ «{title}»"

    if category == "monster":
        if SPELL_LINE_RE.match(first):
            return "spell", "текст починається блоком закляття"
        if not (data or {}).get("creature_type"):
            # Статблок без рядка типу істоти — не статблок: так виглядають
            # сторінки правил і вмінь, у які вбудовано приклад статблока.
            return "rule", "немає рядка типу істоти"

    if category not in spec.categories:
        return "rule", "невідома категорія"
    return category, ""


# --- запис ----------------------------------------------------------------

def canonicalize(record: dict, spec: FormatSpec) -> tuple[dict, list[str]]:
    """Повертає (канонічний запис, перелік змін). Ідемпотентна."""
    rec = dict(record)
    name = _as_str(rec.get("name_en")) or ""
    raw_text = str(rec.get("text_en") or "")
    text = clean_text(raw_text)
    data = dict(rec.get("data") or {})
    category = str(rec.get("category") or "rule")

    new_category, why = refine_category(category, name, text, data, spec)
    reasons: list[str] = []
    if new_category != category:
        reasons.append(f"категорія: {category} → {new_category} ({why})")
        category = new_category
        old_id = str(rec.get("id") or "")
        parts = old_id.split("/", 2)
        if len(parts) == 3:
            rec["id"] = f"{parts[0]}/{category}/{parts[2]}"
            reasons.append(f"id: {old_id} → {rec['id']}")

    text, text_reasons = _canonical_text(category, name, text, data, spec)
    reasons.extend(text_reasons)
    if text != raw_text and not any(reason.startswith("text_en") for reason in reasons):
        reasons.append("text_en: пробіли/порожні рядки")

    data, data_reasons = _canonical_data(category, data, spec)
    reasons.extend(data_reasons)

    rec["name_en"] = name
    rec["category"] = category
    rec["text_en"] = text
    rec["data"] = data

    ordered: dict = {}
    for key in spec.entry_keys:
        if key in rec:
            ordered[key] = rec[key]
    for key, value in rec.items():
        if key not in ordered:
            ordered[key] = value
    if list(ordered) != list(record) and not reasons:
        reasons.append("порядок полів запису")
    return ordered, reasons


# --- файли ----------------------------------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
    return rows


def dump_record(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False)


def write_jsonl(path: Path, records: list[dict]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(dump_record(record) + "\n")
    temp.replace(path)


def corpus_roots(spec: FormatSpec) -> list[tuple[str, Path]]:
    """(назва корпусу, тека) у порядку контракту."""
    return [(name, spec.corpus_dir(name)) for name in spec.corpus_names()]


def source_directory(source: str, spec: FormatSpec | None = None, corpus: str | None = None) -> Path:
    """Тека книги в корпусі (типово — у компендіумі)."""
    if spec is None:
        spec = load_spec()
    name = corpus or spec.corpus_names()[0]
    return spec.corpus_dir(name) / source


def corpus_sources(spec: FormatSpec) -> list[str]:
    """Усі книги, які є хоч в одному корпусі."""
    found: set[str] = set()
    for _, root in corpus_roots(spec):
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.is_dir() and any(path.glob("*.jsonl")):
                found.add(path.name)
    return sorted(found)


def categories_of(directory: Path) -> list[str]:
    return sorted(path.stem for path in directory.glob("*.jsonl"))


def iter_corpus(spec: FormatSpec, corpus: str | None = None):
    """Потік (корпус, книга, категорія, запис) — для тестів і звітів."""
    for name, root in corpus_roots(spec):
        if corpus and name != corpus:
            continue
        if not root.is_dir():
            continue
        for directory in sorted(root.iterdir()):
            if not directory.is_dir():
                continue
            for category in categories_of(directory):
                for row in read_jsonl(directory / f"{category}.jsonl"):
                    yield name, directory.name, category, row


def _fill_score(record: dict) -> tuple[int, int]:
    """Наскільки запис «повніший»: заповнені поля data, потім довжина тексту.

    Потрібно, коли два записи зводяться до одного id: у сторінкового запису
    закляття разом зі статблоком data майже порожня, у справжнього закляття —
    заповнена рівнем, школою, часом читання.
    """
    filled = sum(
        1 for value in (record.get("data") or {}).values() if value not in (None, "", [], {})
    )
    return filled, len(record.get("text_en") or "")


def _merge_duplicates(records: list[dict]) -> tuple[list[dict], list[tuple[str, str, list[str]]]]:
    """Один id — один запис. Другий зливається в notes, а не лишається поруч."""
    best: dict[str, dict] = {}
    order: list[str] = []
    merged: list[tuple[str, str, list[str]]] = []
    for record in records:
        record_id = str(record.get("id") or "")
        if record_id not in best:
            best[record_id] = record
            order.append(record_id)
            continue
        previous = best[record_id]
        keep, drop = (
            (record, previous)
            if _fill_score(record) > _fill_score(previous)
            else (previous, record)
        )
        keep = dict(keep)
        notes = list(keep.get("notes") or [])
        notes.append(
            "дубль id: прибрано запис "
            f"{drop.get('category')} на {len(drop.get('text_en') or '')} символів — "
            + (str(drop.get("text_en") or "").strip().splitlines() or [""])[0][:120]
        )
        keep["notes"] = notes
        best[record_id] = keep
        if record is not keep:
            merged.append(
                (
                    str(record.get("category") or ""),
                    record_id,
                    [
                        "дубль id: прибрано запис на "
                        f"{len(drop.get('text_en') or '')} символів "
                        f"({(str(drop.get('text_en') or '').strip().splitlines() or [''])[0][:80]})"
                    ],
                )
            )
    return [best[record_id] for record_id in order], merged


def normalize_source(
    source: str, spec: FormatSpec, write: bool = False
) -> tuple[int, list[tuple[str, str, list[str]]], list[str]]:
    """Приводить одну книгу до канону — в усіх її корпусах одразу.

    Книга може лежати у двох корпусах (статблоки — окремо від решти), тому
    читаємо обидві теки, канонізуємо злитий потік і пишемо кожен запис у ту
    теку, яку для його категорії визначив контракт. Записи, що потрапили не в
    свій корпус (наприклад, монстр у компендіумі), переїжджають під час запису.

    Повертає (кількість змінених записів, [(категорія, id, зміни)], проблеми).
    """
    changed: list[tuple[str, str, list[str]]] = []
    problems: list[str] = []
    existing: list[Path] = []
    canonical_rows: list[dict] = []
    found = False

    for _, root in corpus_roots(spec):
        directory = root / source
        if not directory.is_dir():
            continue
        found = True
        for category in categories_of(directory):
            path = directory / f"{category}.jsonl"
            existing.append(path)
            for row in read_jsonl(path):
                canonical, reasons = canonicalize(row, spec)
                if dump_record(canonical) != dump_record(row):
                    changed.append((category, str(canonical.get("id") or "?"), reasons))
                canonical_rows.append(canonical)

    if not found:
        return 0, changed, [f"{source}: немає каталогу в жодному корпусі"]

    canonical_rows, merged = _merge_duplicates(canonical_rows)
    changed.extend(merged)

    targets: dict[Path, list[dict]] = {}
    for row in canonical_rows:
        category = str(row.get("category") or "rule")
        try:
            directory = spec.category_dir(category, source)
        except KeyError:
            problems.append(f"{source}: категорія {category!r} не належить жодному корпусу")
            continue
        targets.setdefault(directory / f"{category}.jsonl", []).append(row)

    if write:
        for path, rows in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            write_jsonl(path, rows)
        # Прибираємо файли, чиї записи переїхали в інший корпус (напр. монстр
        # лежав у компендіумі): інакше той самий id існував би двічі.
        for path in existing:
            if path not in targets and path.exists():
                path.unlink()
    return len(changed), changed, problems

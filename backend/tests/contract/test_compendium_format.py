"""Формат корпусів: одна категорія — одна форма, і кожна — у своєму корпусі.

Цей тест — другий бік `scripts/normalize`: конвеєри можуть мінятися, але
кожен запис корпусу мусить мати однакові поля, однакові ключі `data` (у
однаковому порядку) і однаковий скелет `text_en` для своєї категорії.

Корпусів два, і межа між ними — частина контракту:

* `content/compendium/` — те, з чого збирається лист персонажа;
* `content/bestiary/` — статблоки монстрів; листок їх не читає.

Формат запису в обох однаковий, тому перевірки спільні й ідуть по обох
корпусах одразу. Специфікація — `contract/compendium-format.json`.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.normalize import canonical  # noqa: E402

CONTENT = ROOT / "content"


@pytest.fixture()
def scratch() -> Path:
    """Порожня тека всередині репозиторію.

    `tmp_path` тут не працює: у пісочниці сесії системна тека temp недоступна
    для запису, а `logs/` — доступна й так само одноразова.
    """
    base = ROOT / "logs" / "_pytest" / "routing"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


pytestmark = pytest.mark.skipif(not (CONTENT / "compendium").is_dir(), reason="корпусу content/compendium немає")


def _corpus() -> list[tuple[str, str, str, dict]]:
    """(корпус, книга, категорія, запис) по всіх корпусах."""
    spec = canonical.load_spec()
    return [(corpus, source, category, row) for corpus, source, category, row in canonical.iter_corpus(spec)]


@pytest.fixture(scope="module")
def spec() -> canonical.FormatSpec:
    return canonical.load_spec()


@pytest.fixture(scope="module")
def corpus() -> list[tuple[str, str, str, dict]]:
    return _corpus()


def test_spec_covers_every_category_in_corpus(corpus, spec):
    categories = {category for _, _, category, _ in corpus}
    missing = sorted(categories - set(spec.categories))
    assert not missing, f"категорії без опису у форматі: {missing}"


def test_spec_puts_each_category_in_exactly_one_corpus(spec):
    seen: dict[str, str] = {}
    for name in spec.corpus_names():
        for category in spec.corpus_categories(name):
            assert category not in seen, f"{category}: у двох корпусах ({seen[category]}, {name})"
            seen[category] = name
    orphans = sorted(set(spec.categories) - set(seen))
    assert not orphans, f"категорії без корпусу: {orphans}"


def test_compendium_holds_no_monsters(corpus):
    """Монстри живуть окремо: лист персонажа їх не читає.

    Це не косметика: якщо монстр повернеться в компендіум (наприклад, конвеєр
    забуде про корпус), то «всі записи довідника» знову переважно монстри.
    """
    stray = [
        f"{source}/{record['id']}"
        for name, source, category, record in corpus
        if name == "compendium" and category == "monster"
    ]
    files = sorted((CONTENT / "compendium").glob("*/monster.jsonl"))
    assert not stray and not files, "монстр у компендіумі: " + ", ".join(stray[:10])


def test_bestiary_holds_only_monsters(corpus):
    stray = [
        f"{source}/{record['id']} ({category})"
        for name, source, category, record in corpus
        if name == "bestiary" and category != "monster"
    ]
    assert not stray, "у бестіарії не монстр: " + ", ".join(stray[:10])


def test_every_book_with_monsters_has_a_bestiary(  # noqa: D103 — назва-опис
) -> None:
    bestiary = CONTENT / "bestiary"
    if not bestiary.is_dir():
        pytest.skip("бестіарію немає")
    for book in sorted(bestiary.iterdir()):
        if book.is_dir():
            assert (book / "monster.jsonl").is_file(), f"{book.name}: бестіарій без записів"


def test_corpus_files_live_in_books():
    """Записи лежать у теці книги, а не в корені корпусу.

    Це не формальність: якщо нормалізатор помилиться з текою, файл поїде в
    `content/bestiary/monster.jsonl`, а старі файли книги будуть прибрані як
    «переїхали» — тобто книга зникне, і побачити це можна лише тут.
    """
    stray: list[str] = []
    for name in ("compendium", "bestiary"):
        root = CONTENT / name
        if not root.is_dir():
            continue
        stray.extend(f"{name}/{path.name}" for path in sorted(root.glob("*.jsonl")))
    assert not stray, "файли записів поза теками книг: " + ", ".join(stray)


def test_normalize_moves_stray_record_to_its_corpus(scratch, monkeypatch, spec):
    """Запис не у своєму корпусі переїжджає, а не зникає.

    Монстр у компендіумі — саме та помилка, яку легко зробити конвеєром і
    важко помітити: id лишається тим самим, тому «кількість записів» не
    змінюється.
    """
    monkeypatch.setattr(canonical, "ROOT", scratch)

    def record(category: str, slug: str, text: str, data: dict | None = None) -> dict:
        return {
            "id": f"demo/{category}/{slug}",
            "schema": "compendium-entry/1",
            "source_id": "demo",
            "category": category,
            "name_en": slug.title(),
            "name_uk": None,
            "edition": "2014",
            "license": "proprietary",
            "url": None,
            "page": None,
            "text_en": text,
            "text_uk": None,
            "data": data or {},
            "status": "raw",
            "fetched_at": None,
            "notes": [],
        }

    compendium = scratch / "content" / "compendium" / "demo"
    compendium.mkdir(parents=True)
    canonical.write_jsonl(
        compendium / "monster.jsonl",
        [
            # Тип істоти обовʼязковий: статблок без нього — не статблок, і
            # нормалізатор слушно переведе його в правило.
            record(
                "monster",
                "aboleth",
                "Large aberration, lawful evil\n\nArmor Class 17",
                {"creature_type": "aberration", "size": "large"},
            )
        ],
    )
    canonical.write_jsonl(
        compendium / "rule.jsonl",
        [record("rule", "chapter-one", "# Chapter One\n\nТекст правила.")],
    )

    _, _, problems = canonical.normalize_source("demo", spec, write=True)
    assert not problems

    assert (scratch / "content" / "bestiary" / "demo" / "monster.jsonl").is_file()
    assert not (compendium / "monster.jsonl").exists()
    assert (compendium / "rule.jsonl").is_file()
    rows = canonical.read_jsonl(scratch / "content" / "bestiary" / "demo" / "monster.jsonl")
    assert [row["id"] for row in rows] == ["demo/monster/aboleth"]


def test_ids_are_unique(corpus):
    seen: dict[str, tuple[str, str]] = {}
    duplicates: list[str] = []
    for name, source, category, record in corpus:
        record_id = record["id"]
        if record_id in seen:
            duplicates.append(f"{record_id} ({seen[record_id][0]}/{seen[record_id][1]} і {name}/{source}/{category})")
        seen[record_id] = (name, f"{source}/{category}")
    assert not duplicates, "повторювані id:\n" + "\n".join(duplicates[:20])


def test_entry_keys_are_canonical(corpus, spec):
    problems: list[str] = []
    for _, source, _, record in corpus:
        if list(record) != spec.entry_keys:
            problems.append(f"{source}/{record['id']}: поля {list(record)}")
    assert not problems, "\n".join(problems[:10])


def test_category_matches_file_and_id(corpus):
    problems: list[str] = []
    for _, source, file_category, record in corpus:
        if record["category"] != file_category:
            problems.append(f"{source}: {record['id']} лежить у {file_category}.jsonl")
        elif record["id"].split("/")[1] != file_category:
            problems.append(f"{source}: id {record['id']} не збігається з категорією")
    assert not problems, "\n".join(problems[:10])


def test_data_keys_are_canonical(corpus, spec):
    problems: list[str] = []
    for _, source, _, record in corpus:
        expected = spec.data_keys(record["category"])
        if list(record.get("data") or {}) != expected:
            problems.append(f"{source}/{record['id']}: {list(record.get('data') or {})} != {expected}")
    assert not problems, "\n".join(problems[:10])


def test_data_values_have_declared_types(corpus, spec):
    kinds = {"str": str, "str_lower": str, "int": int, "bool": bool, "lower": list}
    problems: list[str] = []
    for _, source, _, record in corpus:
        declared = spec.data_kinds(record["category"])
        data = record.get("data") or {}
        for key, kind in declared.items():
            value = data.get(key)
            allowed = kinds.get(kind)
            if allowed is None:
                if kind == "abilities":
                    assert isinstance(value, dict)
                    keys = canonical.SHORT_ABILITIES
                else:
                    keys = canonical.LONG_ABILITIES
                assert list(value) == list(keys), f"{source}/{record['id']}.{key}: {list(value)}"
                continue
            if value is None:
                if kind == "bool":
                    problems.append(f"{source}/{record['id']}.{key}: прапорець не може бути null")
                continue
            if kind == "int" and isinstance(value, bool):
                problems.append(f"{source}/{record['id']}.{key}: bool замість int")
            elif not isinstance(value, allowed):
                problems.append(f"{source}/{record['id']}.{key}: {type(value).__name__} замість {kind}")
    assert not problems, "\n".join(problems[:10])


def test_text_skeleton_per_category(corpus, spec):
    problems: list[str] = []
    for _, source, _, record in corpus:
        category = record["category"]
        text = record["text_en"]
        style = spec.text_style(category)
        if not text.strip():
            problems.append(f"{source}/{record['id']}: порожній text_en")
            continue
        first = text.split("\n", 1)[0]
        if style == "spell-block":
            if not canonical.SPELL_LINE_RE.match(first.strip()):
                problems.append(f"{source}/{record['id']}: перший рядок {first[:40]!r}")
        elif style == "prose":
            if first.startswith("#"):
                problems.append(f"{source}/{record['id']}: прозовий запис починається заголовком")
        elif style == "section" and not first.startswith("# "):
            problems.append(f"{source}/{record['id']}: розділ без заголовка {first[:40]!r}")
    assert not problems, "\n".join(problems[:10])


def test_spells_have_full_minimum(corpus):
    """У закляття мусить бути рівень, школа, час, дистанція, тривалість."""
    problems: list[str] = []
    for _, source, _, record in corpus:
        if record["category"] != "spell":
            continue
        data = record["data"]
        for key in ("level", "school", "casting_time", "range", "duration"):
            if data.get(key) is None:
                problems.append(f"{source}/{record['id']}: немає {key}")
    assert not problems, "\n".join(problems[:10])


def test_optional_features_have_a_group(corpus):
    """Опційне вміння мусить мати групу — інакше його нема де показати.

    `feature_type` — це те, чим дзеркало групує вміння (invocation, maneuver,
    fighting style…). Порожня група означає, що код дзеркала (`EI`, `FS:R`) не
    впізнано, і вміння повисне без розділу — саме так воно й лежало в тексті
    класу, поки категорії не існувало.
    """
    problems: list[str] = []
    for _, source, _, record in corpus:
        if record["category"] != "optionalfeature":
            continue
        if not record["data"].get("feature_type"):
            problems.append(f"{source}/{record['id']}: без групи")
    assert not problems, "\n".join(problems[:10])


def test_monsters_have_stat_block_minimum(corpus):
    """Статблок мусить мати розмір, тип, клас захисту й швидкість.

    Хіти й досвід бувають нечисловими («half the hit point maximum of its
    summoner»), тому їх вимагаємо лише тоді, коли є числовий рівень небезпеки.
    Виняток — статблок, у якому числових хітів немає взагалі («—(immune to
    damage)», Meeseeks з RMBRE): тоді це не прогалина розбору, а властивість
    істоти, і запис мусить мати про це примітку.
    """
    problems: list[str] = []
    for _, source, _, record in corpus:
        if record["category"] != "monster":
            continue
        data = record["data"]
        for key in ("size", "creature_type", "armor_class", "speed"):
            if data.get(key) is None:
                problems.append(f"{source}/{record['id']}: немає {key}")
        challenge = str(data.get("challenge_rating") or "")
        if challenge[:1].isdigit():
            no_hit_points_documented = any(
                str(note).startswith("статблок без числових хітів") for note in (record.get("notes") or [])
            )
            for key in ("hit_points", "xp"):
                if data.get(key) is None and not (key == "hit_points" and no_hit_points_documented):
                    problems.append(f"{source}/{record['id']}: немає {key}")
    assert not problems, "\n".join(problems[:10])

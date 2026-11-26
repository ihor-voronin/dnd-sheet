"""Preflight без сторонніх залежностей (тільки stdlib).

Що перевіряє:
  1. синтаксис усіх .py;
  2. валідність JSON контракту й фікстур;
  3. інваріанти SheetDocument: посилання на поля, id == ключ, двомовність, типи значень;
  4. чистоту домену (заміна import-linter, поки не встановлені залежності);
  5. арифметику домену на golden-числах;
  6. безпеку обчислювача формул.

Запуск:  python scripts/preflight.py
Коли встановлені залежності — повний прогін: pytest backend + lint-imports.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "backend" / "src"
BACKEND = ROOT / "backend"

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")
FORBIDDEN_DOMAIN_IMPORTS = (
    "fastapi",
    "sqlalchemy",
    "jinja2",
    "dndsheet.characters.application",
    "dndsheet.characters.infrastructure",
    "dndsheet.characters.api",
    "dndsheet.sheets.application",
    "dndsheet.sheets.infrastructure",
    "dndsheet.sheets.api",
    "dndsheet.export.application",
    "dndsheet.export.infrastructure",
    "dndsheet.export.api",
)
DOMAIN_DIRS = [
    SRC / "dndsheet" / "shared",
    SRC / "dndsheet" / "characters" / "domain",
    SRC / "dndsheet" / "sheets" / "domain",
    SRC / "dndsheet" / "export" / "domain",
]

problems: list[str] = []


def problem(message: str) -> None:
    problems.append(message)


def check_syntax() -> int:
    files = sorted(BACKEND.rglob("*.py"))
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            problem(f"syntax {path.relative_to(ROOT)}: {exc}")
    return len(files)


def check_json() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    schema_path = ROOT / "contract" / "sheet-document.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    fixtures: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "contract" / "fixtures").glob("*.json")):
        fixtures[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    required = {"schemaVersion", "edition", "title", "pages", "fields"}
    missing = required - set(schema.get("properties", {}))
    if missing:
        problem(f"схема: немає обовʼязкових властивостей {sorted(missing)}")
    if not fixtures:
        problem("фікстури: жодного файлу")
    return schema, fixtures


def _value_matches_type(field_type: str, value: Any) -> bool:
    if value is None:
        return True
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "checkbox":
        return isinstance(value, bool)
    if field_type == "list":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if field_type in {"text", "longtext", "dice"}:
        return isinstance(value, str)
    if field_type == "counter":
        return isinstance(value, (int, str))
    return True


def check_fixtures(fixtures: dict[str, dict[str, Any]]) -> int:
    checked = 0
    for name, document in fixtures.items():
        version = document.get("schemaVersion", "")
        if not VERSION_RE.match(version):
            problem(f"{name}: некоректний schemaVersion {version!r}")
        if document.get("edition") != "2014":
            problem(f"{name}: edition має бути '2014'")

        title = document.get("title", {})
        if not title.get("uk") or not title.get("en"):
            problem(f"{name}: заголовок має бути двомовним")

        fields = document.get("fields", {})
        for page_index, page in enumerate(document.get("pages", [])):
            for section in page.get("sections", []):
                for field_id in section.get("fields", []):
                    if field_id not in fields:
                        problem(
                            f"{name}: сторінка {page_index}, секція {section.get('id')!r} "
                            f"посилається на відсутнє поле {field_id!r}"
                        )

        for key, field in fields.items():
            checked += 1
            if field.get("id") != key:
                problem(f"{name}: ключ {key!r} != field.id {field.get('id')!r}")
            label = field.get("label", {})
            if not label.get("uk") or not label.get("en"):
                problem(f"{name}.{key}: підпис має бути двомовним (uk + en для тултіпа)")
            if not _value_matches_type(field.get("type", ""), field.get("value")):
                problem(f"{name}.{key}: значення не відповідає типу {field.get('type')!r}")
            if field.get("origin") not in {"input", "computed", "override"}:
                problem(f"{name}.{key}: некоректний origin {field.get('origin')!r}")
    return checked


def check_domain_purity() -> int:
    checked = 0
    for directory in DOMAIN_DIRS:
        for path in sorted(directory.rglob("*.py")):
            checked += 1
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    modules = [node.module]
                for module in modules:
                    if module.startswith(FORBIDDEN_DOMAIN_IMPORTS):
                        problem(
                            f"домен тягне заборонене: {path.relative_to(ROOT)} -> {module}"
                        )
    return checked


def check_domain_behaviour() -> None:
    sys.path.insert(0, str(SRC))

    from dndsheet.characters.domain.character import Character
    from dndsheet.characters.domain.class_level import CharacterClass
    from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
    from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
    from dndsheet.characters.domain.services.spell_slots import spellcasting_for_classes
    from dndsheet.shared.kernel import (
        Ability,
        AbilityScore,
        DiceExpression,
        Skill,
        proficiency_bonus,
    )
    from dndsheet.shared.rules import (
        CASTER_SLOT_TABLE,
        PACT_SLOT_TABLE,
        AbilityBonus,
        BackgroundMechanics,
        CasterProgression,
        ClassMechanics,
        Size,
        SkillChoice,
        SpeciesMechanics,
        caster_level,
        spell_slots,
    )
    from dndsheet.sheets.domain.formula import FormulaError, evaluate, sheet_functions

    if AbilityScore(16).modifier != 3 or AbilityScore(7).modifier != -2:
        problem("модифікатор характеристики рахується невірно")
    if [proficiency_bonus(level) for level in (1, 5, 9, 17, 20)] != [2, 3, 4, 6, 6]:
        problem("бонус майстерності рахується невірно")

    dice = DiceExpression.parse("2d6+3")
    if (dice.minimum, dice.maximum, dice.average) != (5, 15, 10.0):
        problem("межі DiceExpression невірні")

    # Таблиці правил: 20 рівнів, 9 рівнів заклять, узгоджені з правилами.
    if len(CASTER_SLOT_TABLE) != 20 or any(len(row) != 9 for row in CASTER_SLOT_TABLE):
        problem("таблиця слотів заклинателя не 20×9")
    if spell_slots(3) != (4, 2, 0, 0, 0, 0, 0, 0, 0):
        problem("слоти 3 рівня заклинателя невірні")
    if PACT_SLOT_TABLE[0] != (1, 1) or PACT_SLOT_TABLE[10] != (3, 5):
        problem("таблиця Pact Magic невірна")
    if caster_level([(None, 5), (None, 3)]) != 0:
        problem("неклинательські класи дали рівень заклинателя")

    class _Rules:
        """Мінімум правил для golden-перевірки: Воїн 1, людина, солдат."""

        def __init__(self) -> None:
            self._fighter = ClassMechanics(
                key="fighter",
                name_en="Fighter",
                source_id="PHB",
                hit_die=10,
                saving_throws=frozenset({Ability.STR, Ability.CON}),
                skill_choices=(
                    SkillChoice(
                        count=2,
                        options=(
                            Skill.ATHLETICS,
                            Skill.PERCEPTION,
                            Skill.SURVIVAL,
                            Skill.INSIGHT,
                        ),
                    ),
                ),
                armor_training=("light", "medium", "heavy", "shield"),
                weapon_training=("simple", "martial"),
                subclass_level=3,
            )
            self._wizard = ClassMechanics(
                key="wizard",
                name_en="Wizard",
                source_id="PHB",
                hit_die=6,
                saving_throws=frozenset({Ability.INT, Ability.WIS}),
                spellcasting_ability=Ability.INT,
                caster_progression=CasterProgression.FULL,
                spell_slots=CASTER_SLOT_TABLE,
                cantrips_known=(3, 3, 3),
            )
            self._human = SpeciesMechanics(
                key="human",
                name_en="Human",
                source_id="PHB",
                size=Size.MEDIUM,
                speed=30,
                ability_bonuses=tuple(
                    AbilityBonus(ability, 1) for ability in Ability
                ),
            )
            self._soldier = BackgroundMechanics(
                key="soldier",
                name_en="Soldier",
                source_id="PHB",
                skill_proficiencies=frozenset({Skill.ATHLETICS, Skill.INTIMIDATION}),
            )

        def class_mechanics(self, key: str):
            return {"fighter": self._fighter, "wizard": self._wizard}.get(key)

        def species_mechanics(self, key: str):
            return self._human if key == "human" else None

        def background_mechanics(self, key: str):
            return self._soldier if key == "soldier" else None

    rules = _Rules()
    character = Character(
        id="check-1",
        name="  Перевірка  ",
        abilities={
            Ability.STR: AbilityScore(15),
            Ability.DEX: AbilityScore(13),
            Ability.CON: AbilityScore(14),
            Ability.INT: AbilityScore(9),
            Ability.WIS: AbilityScore(11),
            Ability.CHA: AbilityScore(7),
        },
        rules=rules,
        species_key="human",
        background_key="soldier",
        classes=[CharacterClass(class_key="fighter", level=1)],
        inventory=Inventory(
            items=(
                InventoryItem(
                    name_en="chain mail",
                    kind=ItemKind.ARMOR,
                    equipped=True,
                    armor_base=16,
                    dex_cap=0,
                ),
                InventoryItem(name_en="shield", kind=ItemKind.SHIELD, equipped=True),
            )
        ),
    )
    computed = DerivedStatsCalculator().compute(character)
    expected = {
        "STR total": (computed.abilities[Ability.STR].total, 16),
        "AC": (computed.armor_class, 18),
        "HP": (computed.hit_points.maximum, 12),
        "STR save": (computed.saving_throws[Ability.STR], 5),
        "DEX save": (computed.saving_throws[Ability.DEX], 2),
        "athletics": (computed.skills[Skill.ATHLETICS], 5),
        "perception": (computed.skills[Skill.PERCEPTION], 1),
        "passive": (computed.passive_perception, 11),
        "initiative": (computed.initiative, 2),
    }
    for label, (actual, wanted) in expected.items():
        if actual != wanted:
            problem(f"golden {label}: очікували {wanted}, отримали {actual}")

    # Мультиклас: Воїн 1 + Волшебник 3 → рівень заклинателя 3, слоти 4/2.
    multiclass = Character(
        id="check-2",
        name="Мультиклас",
        abilities={ability: AbilityScore(12) for ability in Ability},
        rules=rules,
        classes=[
            CharacterClass(class_key="fighter", level=1),
            CharacterClass(class_key="wizard", level=3),
        ],
    )
    casting = DerivedStatsCalculator().compute(multiclass).spellcasting
    if casting.caster_level != 3 or dict(casting.slots.by_level) != {1: 4, 2: 2}:
        problem(
            f"мультиклас: рівень заклинателя {casting.caster_level}, "
            f"слоти {dict(casting.slots.by_level)}"
        )

    functions = sheet_functions({"str": 16, "dex": 14}, level=3)
    if evaluate("10 + mod('dex') + proficiency()", functions=functions) != 14:
        problem("формула AC-патерну рахується невірно")
    try:
        evaluate("__import__('os')", functions=functions)
    except FormulaError:
        pass
    else:
        problem("обчислювач формул пропустив __import__ — критично")


def check_mechanics_indexes() -> str:
    """Похідні індекси механік: наявність і базові інваріанти (stdlib-рівень).

    Повна перевірка — `python -m scripts.ingest.mechanics --check` і
    `tests/contract/test_mechanics_format.py`; тут — запобіжник, що числа
    не зламані (без індексів просто попередження: свіжий клон їх не має).
    """
    index_dir = ROOT / "content" / "index"
    class_path = index_dir / "class-mechanics.json"
    origin_path = index_dir / "origin-mechanics.json"
    if not class_path.is_file() or not origin_path.is_file():
        return "немає (свіжий клон)"

    classes = json.loads(class_path.read_text(encoding="utf-8"))
    origins = json.loads(origin_path.read_text(encoding="utf-8"))
    if len(classes.get("classes") or {}) < 12:
        problem(f"індекс класів: лише {len(classes.get('classes') or {})} класів")
    for key, entry in (classes.get("classes") or {}).items():
        if not 4 <= int(entry.get("hit_die") or 0) <= 20:
            problem(f"клас {key}: хіт-дайс {entry.get('hit_die')}")
        if len(entry.get("spell_slots") or []) not in (0, 20):
            problem(f"клас {key}: таблиця слотів не на 20 рівнів")
    for collection in ("species", "subspecies", "backgrounds"):
        if not (origins.get(collection) or {}):
            problem(f"індекс видів: порожня колекція {collection}")
    return (
        f"{len(classes.get('classes') or {})} класів, "
        f"{len(origins.get('species') or {})} видів, "
        f"{len(origins.get('subspecies') or {})} підрас, "
        f"{len(origins.get('backgrounds') or {})} передісторій"
    )


def check_compendium_format() -> tuple[dict[str, tuple[int, int]], list[str]]:
    """Корпуси: одна категорія — одна форма (contract/compendium-format.json).

    Той самий прогон, що й `python -m scripts.normalize --check`, але без
    зовнішніх залежностей: якщо корпус розійшовся з контрактом, preflight
    падає з першими прикладами. Перевіряються обидва корпуси — компендіум для
    листа персонажа і бестіарій — плюс те, що кожна категорія лежить саме у
    своєму корпусі (монстр не має права опинитися в компендіумі).

    Повертає статистику по корпусах і список відсутніх тек (свіжий клон).
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from scripts.normalize import canonical
    except ImportError as exc:  # pragma: no cover — контракт є в репозиторії
        problem(f"формат корпусу: не вдалося завантажити scripts.normalize ({exc})")
        return {}, []

    spec = canonical.load_spec()
    stats: dict[str, tuple[int, int]] = {}
    missing: list[str] = []
    changed = 0
    shown = 0

    for source in canonical.corpus_sources(spec):
        count, changes, source_problems = canonical.normalize_source(
            source, spec, write=False
        )
        changed += count
        for message in source_problems:
            problem(f"формат корпусу: {message}")
        for category, record_id, reasons in changes:
            if shown < 10:
                problem(
                    f"формат корпусу: {category}/{record_id} — " + "; ".join(reasons[:3])
                )
                shown += 1
    if changed > shown:
        problem(f"формат корпусу: ще {changed - shown} записів поза каноном")

    for corpus in spec.corpus_names():
        allowed = set(spec.corpus_categories(corpus))
        directory = spec.corpus_dir(corpus)
        books = 0
        rows = 0
        if directory.is_dir():
            for book in sorted(directory.iterdir()):
                if not book.is_dir():
                    continue
                files = sorted(book.glob("*.jsonl"))
                if not files:
                    continue
                books += 1
                for file in files:
                    rows += len(canonical.read_jsonl(file))
                    if file.stem not in allowed:
                        problem(
                            f"корпус {corpus}: {book.name}/{file.name} — категорія "
                            f"живе в іншому корпусі"
                        )
        else:
            # Свіжий клон репозиторію: текстів книг у ньому немає (копирайт і
            # обсяг). Це не привід падати — але й не привід мовчати.
            missing.append(f"{corpus} ({directory})")
        stats[corpus] = (books, rows)
    return stats, missing


def main() -> int:
    py_count = check_syntax()
    _, fixtures = check_json()
    field_count = check_fixtures(fixtures)
    domain_count = check_domain_purity()
    check_domain_behaviour()
    corpus_stats, missing_corpora = check_compendium_format()
    mechanics = check_mechanics_indexes()

    if problems:
        print(f"PREFLIGHT FAILED ({len(problems)}):")
        for item in problems:
            print("  -", item)
        return 1

    corpora = ", ".join(
        f"{name} {books} книг / {rows} записів"
        for name, (books, rows) in corpus_stats.items()
    )
    print(
        "PREFLIGHT OK: "
        f"{py_count} .py, {len(fixtures)} фікстур / {field_count} полів, "
        f"{domain_count} доменних модулів, домен рахує golden-числа, eval заблоковано, "
        f"корпус за каноном формату ({corpora or 'немає'}), "
        f"механіки: {mechanics}"
    )
    for missing in missing_corpora:
        print(f"  увага: корпусу {missing} немає — перевірено 0 записів")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

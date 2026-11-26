"""Особливості видів: розбір тексту книги й вимога підраси.

Перевіряється те, що бачив гравець: Harengon показував «без бонусів» і жодного
вміння, хоч у книзі в нього «Hare-Trigger» і «Rabbit Hop». Тести тримають
розбір на справжніх текстах корпусу (він є в репозиторії), а форми тексту
різні: з заголовком `### Harengon Traits`, без заголовка («Hill Dwarf»),
суцільним рядком (EEPC) і в розділі глави правил (SCAG, ERLW).
"""

from __future__ import annotations

import pytest

from dndsheet.characters.api.species_traits import parse_species_text, species_details
from dndsheet.compendium.infrastructure.factory import build_service
from dndsheet.shared.rules import requires_subspecies

HARENGON = """Harengons originated in the Feywild, where they spoke Sylvan.

Here and gone. Fey puns are a menace!

— Mordenkainen

### Harengon Traits

As a harengon, you have the following racial traits.

Creature Type. You are a Humanoid.

Size. You are Medium or Small.

Hare-Trigger. You can add your proficiency bonus to your initiative rolls.

Lucky Footwork. When you fail a Dexterity saving throw, you can use your
reaction to roll a d4 and add it to the save.
"""

HILL_DWARF = """As a hill dwarf, you have keen senses, deep intuition, and remarkable resilience.

Ability Score Increase. Your Wisdom score increases by 1.

Dwarven Toughness. Your hit point maximum increases by 1.
"""

INLINE = (
    "Aarakocra Traits As an aarakocra, you have certain traits in common with your people. "
    "Ability Score Increase. Your Dexterity score increases by 2. "
    "Age. Aarakocra reach maturity by age 3. "
    "Flight. You have a flying speed of 50 feet."
)


def test_traits_after_header() -> None:
    parsed = parse_species_text(HARENGON)

    assert [trait["name_en"] for trait in parsed["traits"]] == [
        "Creature Type",
        "Size",
        "Hare-Trigger",
        "Lucky Footwork",
    ]
    # Опис — проза до заголовка; цитата й підпис не потрапляють.
    assert "Feywild" in parsed["description"]
    assert "Mordenkainen" not in parsed["description"]
    assert parsed["lang"] == "en"


def test_traits_without_header() -> None:
    """«Hill Dwarf» — це просто два рядки «Назва. Текст»."""
    parsed = parse_species_text(HILL_DWARF)

    assert [trait["name_en"] for trait in parsed["traits"]] == [
        "Ability Score Increase",
        "Dwarven Toughness",
    ]
    assert "keen senses" in parsed["description"]


def test_inline_text_is_split_into_traits() -> None:
    """Тексти EEPC прийшли одним рядком — уміння все одно мають бути."""
    parsed = parse_species_text(INLINE)

    assert [trait["name_en"] for trait in parsed["traits"]] == [
        "Ability Score Increase",
        "Age",
        "Flight",
    ]


def test_multi_paragraph_trait_is_one_trait() -> None:
    text = (
        "### Test Traits\n\n"
        "As a test, you have the following traits.\n\n"
        "Chameleon Carapace. While you aren't wearing armor, your carapace gives you a base Armor Class of 13.\n\n"
        "As an action, you can change the color of your carapace.\n\n"
        "Sleepless. You do not require sleep.\n"
    )
    parsed = parse_species_text(text)

    names = [trait["name_en"] for trait in parsed["traits"]]
    assert names == ["Chameleon Carapace", "Sleepless"]
    assert "change the color" in parsed["traits"][0]["text"]


def test_language_is_detected() -> None:
    russian = "Тип существа. Вы — Гуманоид.\n\nБесстрашие. Вы совершаете спасброски."
    ukrainian = "Тип істоти. Ви — Гуманоїд.\n\nБезстрашність. Ви маєте перевагу."

    assert parse_species_text(russian)["lang"] == "ru"
    assert parse_species_text(ukrainian)["lang"] == "uk"


# ---------------------------------------------------------------------------
# справжній корпус
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def service():  # noqa: ANN201
    try:
        built = build_service()
    except Exception:  # pragma: no cover — немає корпусу в чистому клоні
        pytest.skip("немає корпусу довідника")
    if not built.species_list():
        pytest.skip("немає механік видів")
    return built


def test_harengon_has_traits_from_the_book(service) -> None:  # noqa: ANN001
    details = species_details(service, "Harengon", cache={})

    assert details is not None
    names = [trait["name_en"] for trait in details["traits"]]
    assert "Hare-Trigger" in names
    assert "Rabbit Hop" in names
    assert details["description"]


def test_every_species_has_something_to_show(service) -> None:  # noqa: ANN001
    """Хоч числа, хоч текст: виду, про який на екрані нема нічого, бути не має.

    «Gnoll» — єдиний виняток: у корпусі він є як монстр, а не як грабельний
    вид, тому тексту для гравця немає (лишаються числа з індексу).
    """
    cache: dict = {}
    empty: list[str] = []
    for item in service.species_list():
        details = species_details(service, item.name_en, cache=cache)
        if details is None or (not details["traits"] and not details["description"]):
            empty.append(item.name_en)
    assert empty == ["Gnoll"]


def test_subspecies_without_text_are_known(service) -> None:  # noqa: ANN001
    """Сім підрас корпус описує лише таблицею, без тексту.

    Список явний, а не «десь приблизно»: якщо колись текст зʼявиться (або
    зламається розбір), тест це покаже.
    """
    cache: dict = {}
    missing: list[str] = []
    for base in service.species_list():
        for child in service.subspecies_of(base.name_en):
            details = species_details(
                service, child.name_en, parent_name_en=base.name_en, cache=cache
            )
            if not details or not details["traits"]:
                missing.append(child.name_en)
    assert sorted(missing) == [
        "Asmodeus Tiefling",
        "Variant; Aquatic Elf Descent Half-Elf",
        "Variant; Devil's Tongue Tiefling",
        "Variant; Hellfire Tiefling",
        "Variant; Infernal Legacy Tiefling",
        "Variant; Moon Elf or Sun Elf Descent Half-Elf",
        "Variant; Winged Tiefling",
    ]


def test_subspecies_text_is_found_in_other_books(service) -> None:  # noqa: ANN001
    """«Beasthide Shifter» не має власного запису — текст у розділі «Shifter»."""
    details = species_details(
        service, "Beasthide Shifter", parent_name_en="Shifter", cache={}
    )

    assert details is not None
    names = [trait["name_en"] for trait in details["traits"]]
    assert "Ability Score Increase" in names
    assert len(names) >= 2


def test_subspecies_text_from_rule_chapter(service) -> None:  # noqa: ANN001
    """«Ghostwise Halfling» описаний у главі SCAG, а не в записі виду."""
    details = species_details(
        service, "Ghostwise Halfling", parent_name_en="Halfling", cache={}
    )

    assert details is not None
    names = [trait["name_en"] for trait in details["traits"]]
    assert "Silent Speech" in names


# ---------------------------------------------------------------------------
# вимога підраси
# ---------------------------------------------------------------------------


def test_subspecies_required_only_where_it_gives_numbers() -> None:
    for key in ("elf", "dwarf", "gnome", "halfling", "genasi", "shifter", "aasimar"):
        assert requires_subspecies(key) is True
    # У людини є «Variant Human», але звичайна людина теж грає.
    for key in ("human", "tiefling", "dragonborn", "half-elf", "custom lineage"):
        assert requires_subspecies(key) is False

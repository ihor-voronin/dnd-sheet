"""Каталог портретів: стабільні id, групи видів і поради для героя."""

from __future__ import annotations

from dndsheet.visuals.domain import catalog
from dndsheet.visuals.domain.catalog import Portrait


def test_catalog_is_large_and_ids_are_unique() -> None:
    items = catalog.all_portraits()
    ids = [item.id for item in items]
    assert 1000 <= len(ids) <= 2000
    assert len(set(ids)) == len(ids)
    assert all(catalog.looks_like_id(value) for value in ids)
    assert all(catalog.is_known(value) for value in ids[:50])


def test_every_group_has_every_class() -> None:
    for group in catalog.GROUPS:
        classes = {item.class_key for item in catalog.all_portraits() if item.group == group.key}
        assert classes == set(catalog.CLASSES), group.key


def test_ids_are_stable() -> None:
    """Id зберігає лист персонажа — зміна схеми зламала б збережені портрети."""
    assert catalog.portrait("elf-f-wizard-1") == Portrait("elf", "f", "wizard", 1)
    assert catalog.portrait("dragonborn-x-paladin-3") == Portrait("dragonborn", "x", "paladin", 3)
    assert catalog.portrait("elf-x-wizard-1") is None
    assert catalog.portrait("nope") is None
    assert not catalog.is_known("elf-f-wizard-9")


def test_label_describes_the_portrait() -> None:
    assert catalog.portrait("elf-f-wizard-2").label == "Портрет: ельф, жіночий, чарівник (2)"
    assert catalog.portrait("kenku-x-rogue-1").label == "Портрет: кенку, пройдисвіт"
    assert catalog.portrait("human-m-cleric-1").as_dict()["class"] == "cleric"


def test_species_group_by_name() -> None:
    assert catalog.species_group("Mountain Dwarf") == "dwarf"
    assert catalog.species_group("duergar dwarf Dwarf") == "duergar"
    assert catalog.species_group("Half-Elf") == "half-elf"
    assert catalog.species_group("drow elf Elf") == "drow"
    assert catalog.species_group("Elf") == "elf"
    assert catalog.species_group("Hobgoblin") == "hobgoblin"
    assert catalog.species_group("Goblin") == "goblin"
    assert catalog.species_group("Half-Orc") == "half-orc"
    assert catalog.species_group("Orc") == "half-orc"
    assert catalog.species_group("fire genasi Genasi") == "genasi-fire"
    assert catalog.species_group("Githyanki") == "gith"
    assert catalog.species_group("Variant Human") == "human"
    assert catalog.species_group("Something New") is None
    assert catalog.species_group(None) is None


def test_recommend_starts_with_species_gender_and_class() -> None:
    advice = catalog.recommend(species="High Elf", class_key="wizard", gender="female")
    assert 20 <= len(advice) <= 30
    assert advice[0].group == "elf" and advice[0].gender == "f" and advice[0].class_key == "wizard"
    assert all(item.gender in ("f", "x") for item in advice)
    # Спершу всі варіанти свого класу, потім інші класи свого виду.
    classes = [item.class_key for item in advice if item.group == "elf"]
    assert classes[:2] == ["wizard", "wizard"]
    assert set(classes[2:]) - {"wizard"}


def test_recommend_without_gender_takes_both() -> None:
    advice = catalog.recommend(species="Human", class_key="bard", limit=30)
    assert {item.gender for item in advice} == {"f", "m"}
    assert len(advice) == 30


def test_recommend_unknown_species_falls_back_to_class() -> None:
    advice = catalog.recommend(species="Plasmoid", class_key="monk", gender="male")
    assert advice and all(item.class_key == "monk" for item in advice)
    assert all(item.gender in ("m", "x") for item in advice)


def test_recommend_genderless_group_fills_with_class() -> None:
    advice = catalog.recommend(species="Kenku", class_key="rogue", gender="female")
    assert advice[0].id == "kenku-x-rogue-1"
    assert len(advice) == 24
    assert any(item.group != "kenku" for item in advice)

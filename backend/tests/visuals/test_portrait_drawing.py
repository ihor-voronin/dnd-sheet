"""Малюнки портретів: кожен — коректний SVG, маленький, без зовнішніх посилань."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from dndsheet.visuals.application import avatars, portraits
from dndsheet.visuals.domain import catalog

SVG = "{http://www.w3.org/2000/svg}"


def test_every_portrait_is_valid_small_svg() -> None:
    sizes = []
    for item in catalog.all_portraits():
        body = portraits.render(item)
        root = ET.fromstring(body)
        assert root.tag == f"{SVG}svg", item.id
        assert root.get("viewBox") == "5 3 90 90"
        assert (
            "href" not in body
            and "<script" not in body
            and "http://" not in body.replace("http://www.w3.org/2000/svg", "")
        )
        sizes.append(len(body))
    # Один портрет — кілька кілобайт: вибір із сотнею плиток не важить мегабайти.
    assert max(sizes) < 12_000
    assert sum(sizes) / len(sizes) < 7_000


def test_drawing_is_deterministic_and_varied() -> None:
    first = catalog.portrait("human-f-wizard-1")
    assert portraits.render(first) == portraits.render(first)
    variants = {portraits.render(catalog.portrait(f"human-f-wizard-{n}")) for n in (1, 2, 3)}
    assert len(variants) == 3


@pytest.mark.parametrize(
    ("portrait_id", "marker"),
    [
        ("dragonborn-x-fighter-1", "M 50 20 C 59 20 65.6 26"),  # голова дракона
        ("tabaxi-x-rogue-1", "M 37 32 L 35 15 L 47 24.6 Z"),  # котячі вуха
        ("kenku-x-wizard-1", "M 45.4 43.6"),  # дзьоб
        ("tortle-x-druid-1", "#6b5a3a"),  # панцир
        ("warforged-x-fighter-1", "M 50 21 L 61 24"),  # пластини
        ("minotaur-x-barbarian-1", "M 39 27 C 30 26 22 22 18 13"),  # роги
        ("loxodon-x-cleric-1", "M 45 44 C 45 56"),  # хобот
        ("leonin-m-paladin-1", "M 50 22 C 60 22 66 29"),  # котяча голова з гривою
        ("aasimar-f-cleric-1", "#f3d98a"),  # німб
        ("fairy-f-druid-1", "#bfe8e0"),  # крила
        ("harengon-f-bard-1", "#e8a8b0"),  # заячі вуха
        ("owlin-x-wizard-1", "#f2a53e"),  # очі сови
    ],
)
def test_species_have_their_features(portrait_id: str, marker: str) -> None:
    assert marker in portraits.render(catalog.portrait(portrait_id))


def test_class_gear_differs_between_variants() -> None:
    looks = {portraits.look_of(catalog.portrait(f"human-m-wizard-{n}")).headgear for n in (1, 2, 3)}
    assert looks == {"hat", "none", "hood"}
    hooded = portraits.look_of(catalog.portrait("tabaxi-x-fighter-1"))
    assert hooded.headgear == "none"  # шолом не налазить на котячі вуха


def test_warlock_in_a_hood_has_glowing_eyes() -> None:
    for n in (1, 2):
        look = portraits.look_of(catalog.portrait(f"human-f-warlock-{n}"))
        if look.headgear == "hood":
            assert look.eyes == "glow"


def test_mirror_flips_x_only() -> None:
    assert portraits._mirror("M 40 10 L 30 20 C 1 2 3 4 5 6 Q 7 8 9 10 Z") == (
        "M 60 10 L 70 20 C 99 2 97 4 95 6 Q 93 8 91 10 Z"
    )


def test_avatar_urls_carry_the_version() -> None:
    assert avatars.url("elf-f-wizard-1") == f"/assets/avatars/{avatars.VERSION}/elf-f-wizard-1.svg"
    assert len(avatars.VERSION) == 10
    assert avatars.svg("elf-f-wizard-1").startswith("<svg")
    assert avatars.svg("nope") is None


def test_default_portrait_fits_the_character_and_differs_between_heroes() -> None:
    first = avatars.default_for("a", species="High Elf", class_key="wizard", gender="female")
    assert (first.group, first.gender, first.class_key) == ("elf", "f", "wizard")
    picks = {
        avatars.default_for(seed, species="Human", class_key="fighter", gender="male").id
        for seed in ("a", "b", "c", "d", "e", "f")
    }
    assert len(picks) > 1
    assert all(pick.startswith("human-m-fighter-") for pick in picks)
    stranger = avatars.default_for("x", species=None, class_key=None, gender=None)
    assert catalog.is_known(stranger.id)


def test_portrait_of_prefers_the_chosen_one() -> None:
    chosen = avatars.portrait_of("id", chosen="kenku-x-bard-1", species="Human", class_key="bard", gender=None)
    assert chosen["id"] == "kenku-x-bard-1" and chosen["chosen"] is True
    fallback = avatars.portrait_of("id", chosen="gone-x-bard-1", species="Human", class_key="bard", gender=None)
    assert fallback["chosen"] is False and str(fallback["id"]).startswith("human-")
    assert avatars.species_name("Elf", "drow elf") == "drow elf Elf"
    assert avatars.species_name(None, None) is None

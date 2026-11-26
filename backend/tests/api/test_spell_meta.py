"""Короткі дані заклять для вкладки «Дії» — на справжньому корпусі.

Перевіряється саме те, що бачить гравець: час і дистанція переносяться з
`data`, урон і порятунок вичитуються з тексту. Без корпусу тести стрибають.
"""

from __future__ import annotations

import pytest

from dndsheet.characters.api.spell_meta import enrich_spells
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.infrastructure.factory import build_service
from dndsheet.compendium.infrastructure.jsonl_corpus import default_content_dir

CONTENT = default_content_dir()

pytestmark = pytest.mark.skipif(
    not (CONTENT / "compendium").is_dir(), reason="корпусу content/compendium немає"
)


@pytest.fixture(scope="module")
def service() -> CompendiumService:
    return build_service()


def _meta(service: CompendiumService, name_en: str, entry_id: str | None = None) -> dict:
    spells: list[dict] = [{"name_en": name_en, "entry_id": entry_id}]
    enrich_spells(spells, service)
    return spells[0]


def test_damage_cantrip_has_range_and_attack(service: CompendiumService) -> None:
    meta = _meta(service, "Eldritch Blast")
    assert meta["casting_time"] == "1 action"
    assert meta["range"] == "120 feet"
    assert meta["damage"] == {"dice": "1d10", "type": "force"}
    assert meta["attack_roll"] is True
    assert meta["save"] is None


def test_save_spell_without_damage_keeps_save(service: CompendiumService) -> None:
    meta = _meta(service, "Charm Person")
    assert meta["save"] == "wis"
    assert meta["damage"] is None


def test_utility_spell_does_not_invent_save(service: CompendiumService) -> None:
    """`Light` згадує порятунок лише як «to avoid the spell» — це не ефект."""
    meta = _meta(service, "Light")
    assert meta["save"] is None
    assert meta["damage"] is None
    assert meta["range"] == "Touch"


def test_bonus_action_and_concentration(service: CompendiumService) -> None:
    meta = _meta(service, "Hex")
    assert meta["casting_time"] == "1 bonus action"
    assert meta["concentration"] is True
    assert meta["damage"] == {"dice": "1d6", "type": "necrotic"}


def test_fixed_bonus_damage_kept(service: CompendiumService) -> None:
    meta = _meta(service, "Magic Missile", "phb-2014/spell/magic-missile")
    assert meta["damage"] == {"dice": "1d4+1", "type": "force"}


def test_components_and_description(service: CompendiumService) -> None:
    meta = _meta(service, "Shield", "phb-2014/spell/shield")
    assert meta["components"] == "V, S"
    assert meta["description"].startswith("An invisible barrier")
    assert "1st-level" not in meta["description"], "рядок рівня вже показаний окремо"
    assert meta["at_higher_levels"] == ""


def test_higher_levels_text(service: CompendiumService) -> None:
    meta = _meta(service, "Magic Missile", "phb-2014/spell/magic-missile")
    assert "one more dart" in meta["at_higher_levels"]


def test_material_components_kept(service: CompendiumService) -> None:
    meta = _meta(service, "Hex", "phb-2014/spell/hex")
    assert meta["components"].startswith("V, S, M")
    assert "petrified eye" in meta["components"]

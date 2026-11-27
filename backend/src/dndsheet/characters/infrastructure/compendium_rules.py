"""Адаптер порту `RulesSource` над довідником.

Це єдине місце, де контекст `characters` торкається `compendium`: усе інше
(агрегат, сервіси) бачить лише протокол `RulesSource` і значення з
`shared.rules`. Тому золоті персонажі перевіряються на маленькому наборі
правил, а застосунок — на справжньому корпусі, і це той самий код.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.errors import NotFoundError
from dndsheet.shared.kernel import Ability
from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
    feat_ability_options,
)

#: Ключ власної передісторії: її текст гравець пише сам, правила вибору —
#: стандартні (2 навички, 1 інструмент, 1 мова).
CUSTOM_BACKGROUND_KEY = "custom"


@dataclass(slots=True)
class CompendiumRulesSource:
    """Правила з `CompendiumService` (з кешем на час життя застосунку)."""

    service: CompendiumService
    _cache: dict[tuple[str, str], Any] = field(default_factory=dict, init=False, repr=False)

    def class_mechanics(self, key: str) -> ClassMechanics | None:
        return self._lookup("class", key, self.service.class_mechanics)

    def species_mechanics(self, key: str) -> SpeciesMechanics | None:
        return self._lookup("species", key, self.service.species_mechanics)

    def background_mechanics(self, key: str) -> BackgroundMechanics | None:
        cleaned = (key or "").strip().casefold()
        if cleaned == CUSTOM_BACKGROUND_KEY:
            # «Власна передісторія»: в корпусі її немає, але правила вибору
            # (2 навички, 1 інструмент, 1 мова) задає сама гра — ті самі
            # числа, що й у PHB для власної передісторії.
            return BackgroundMechanics(
                key=CUSTOM_BACKGROUND_KEY,
                name_en="Custom Background",
                source_id="custom",
                skill_any=2,
                tools_any=1,
                languages_any_standard=1,
            )
        return self._lookup("background", key, self.service.background_mechanics)

    def _lookup(self, kind: str, key: str, resolve) -> Any:  # noqa: ANN001
        cleaned = (key or "").strip().casefold()
        if not cleaned:
            return None
        cache_key = (kind, cleaned)
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            found = resolve(cleaned)
        except NotFoundError:
            found = None
        self._cache[cache_key] = found
        return found


@dataclass(slots=True)
class CompendiumSubclassCatalog:
    """Підкласи з довідника: id записів, за назвою класу.

    Ключ підкласу в персонажі — це `id` запису довідника
    (`phb-2014/subclass/champion`), а не назва: назви змінюються від
    перекладу, id — ні.
    """

    service: CompendiumService

    def subclass_keys(self, class_key: str) -> tuple[str, ...] | None:
        try:
            definition = self.service.class_mechanics(class_key)
        except NotFoundError:
            return None
        entries = self.service.subclasses(definition.name_en)
        return tuple(entry.id for entry in entries)


@dataclass(slots=True)
class CompendiumFeatCatalog:
    """Рисі з довідника: перевірка, що ключ існує.

    Індекс збирається один раз: рис кілька сотень, а питання «чи є така»
    виникає лише під час підвищення рівня.
    """

    service: CompendiumService
    _keys: set[str] | None = field(default=None, init=False, repr=False)

    def has(self, feat_key: str) -> bool:
        cleaned = (feat_key or "").strip().casefold()
        if not cleaned:
            return False
        return cleaned in self._index()

    def ability_options(self, feat_key: str) -> tuple[Ability, ...]:
        try:
            entry = self.service.entry(feat_key.strip().casefold())
        except NotFoundError:
            return ()
        return feat_ability_options(entry.text_en or "")

    def _index(self) -> set[str]:
        if self._keys is None:
            self._keys = {entry.id.casefold() for entry in self.service.feats()}
        return self._keys

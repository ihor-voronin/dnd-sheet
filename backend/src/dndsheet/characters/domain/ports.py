"""Порт до правил: звідки персонаж бере числа класів, видів і передісторій.

`characters` не читає `content/` і не імпортує `compendium`: він питає порт,
який реалізує адаптер (`characters/infrastructure/compendium_rules.py`).
Завдяки цьому золоті персонажі перевіряються на маленькому наборі правил без
корпусу, а той самий код працює з реальним довідником.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
)


@runtime_checkable
class RulesSource(Protocol):
    """Read-only джерело механік. `None` — таких правил немає."""

    def class_mechanics(self, key: str) -> ClassMechanics | None:
        """Механіки класу за ключем («fighter»)."""

    def species_mechanics(self, key: str) -> SpeciesMechanics | None:
        """Вид або підраса за ключем («human», «hill dwarf»)."""

    def background_mechanics(self, key: str) -> BackgroundMechanics | None:
        """Передісторія за ключем («acolyte»)."""

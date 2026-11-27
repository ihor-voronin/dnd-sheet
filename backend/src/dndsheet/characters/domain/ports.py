"""Порти: до правил і до сховища.

`characters` не читає `content/` і не знає, де лежать файли: він питає порт,
який реалізує адаптер (`characters/infrastructure/`). Завдяки цьому золоті
персонажі перевіряються на маленькому наборі правил без корпусу, а той самий
код працює з реальним довідником; і так само сховище можна замінити з файлів
на БД (етап 6), не чіпаючи домен.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from dndsheet.shared.kernel import Ability

from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
)

if TYPE_CHECKING:  # pragma: no cover - лише для типів
    from dndsheet.characters.domain.character import Character
    from dndsheet.characters.domain.wizard import Draft


@runtime_checkable
class RulesSource(Protocol):
    """Read-only джерело механік. `None` — таких правил немає."""

    def class_mechanics(self, key: str) -> ClassMechanics | None:
        """Механіки класу за ключем («fighter»)."""

    def species_mechanics(self, key: str) -> SpeciesMechanics | None:
        """Вид або підраса за ключем («human», «hill dwarf»)."""

    def background_mechanics(self, key: str) -> BackgroundMechanics | None:
        """Передісторія за ключем («acolyte»)."""


@runtime_checkable
class SubclassCatalog(Protocol):
    """Які підкласи існують у класу — довідник знає, домен ні.

    `None` означає «даних немає» (корпус без підкласів): тоді ключ не
    перевіряється, інакше створення персонажа залежало б від наявності книг.
    """

    def subclass_keys(self, class_key: str) -> tuple[str, ...] | None:
        """Id підкласів класу або `None`, якщо каталог їх не знає."""


@runtime_checkable
class CharacterRepository(Protocol):
    """Сховище готових персонажів."""

    def save(self, character: "Character") -> None:
        """Записати персонажа (перезапис за id)."""

    def get(self, character_id: str) -> "Character | None":
        """Прочитати персонажа; `None` — немає такого."""

    def ids(self) -> tuple[str, ...]:
        """Усі збережені id — для списку персонажів."""


@runtime_checkable
class FeatCatalog(Protocol):
    """Які риси існують у довіднику — домен знає лише ключ.

    Потрібно, щоб у поле `feats` не потрапив ключ, якого немає в корпусі:
    інакше лист показував би рису без тексту, а помилку було б видно лише
    через півроку.
    """

    def has(self, feat_key: str) -> bool:
        """Чи є така риса в довіднику."""

    def ability_options(self, feat_key: str) -> tuple[Ability, ...]:
        """Які характеристики риса дає підвищити на 1; порожньо — без вибору."""


@runtime_checkable
class DraftRepository(Protocol):
    """Сховище чернеток візарда."""

    def save(self, draft: "Draft") -> None:
        """Записати чернетку (перезапис за id)."""

    def get(self, draft_id: str) -> "Draft | None":
        """Прочитати чернетку; `None` — немає такої."""

    def delete(self, draft_id: str) -> None:
        """Прибрати чернетку після створення персонажа."""

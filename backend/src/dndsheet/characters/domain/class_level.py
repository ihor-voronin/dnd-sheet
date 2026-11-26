"""Рівень персонажа в конкретному класі.

Мультиклас — це не «рівень 5», а список «Воїн 2, Волшебник 3». Тому рівень
класу — окреме значення, а сумарний рівень персонажа його лише підсумовує.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import MAX_LEVEL, MIN_LEVEL


@dataclass(frozen=True, slots=True)
class CharacterClass:
    """Один рядок мультикласу: клас, рівень у ньому, підклас (якщо обрано)."""

    class_key: str
    level: int = MIN_LEVEL
    subclass_key: str | None = None

    def __post_init__(self) -> None:
        key = self.class_key.strip()
        if not key:
            raise ValidationError("клас без ключа")
        if key != key.casefold():
            raise ValidationError(f"ключ класу має бути в нижньому регістрі: {key!r}")
        if isinstance(self.level, bool) or not isinstance(self.level, int):
            raise ValidationError(f"{key}: рівень має бути цілим числом")
        if not MIN_LEVEL <= self.level <= MAX_LEVEL:
            raise ValidationError(f"{key}: рівень має бути в межах {MIN_LEVEL}..{MAX_LEVEL}")
        if self.subclass_key is not None:
            subclass = self.subclass_key.strip()
            if not subclass:
                raise ValidationError(f"{key}: порожній ключ підкласу")
            object.__setattr__(self, "subclass_key", subclass.casefold())

    def with_level(self, level: int) -> "CharacterClass":
        return replace(self, level=level)

    def with_subclass(self, subclass_key: str | None) -> "CharacterClass":
        return replace(self, subclass_key=subclass_key)

    def gain_level(self) -> "CharacterClass":
        return replace(self, level=self.level + 1)


@dataclass(frozen=True, slots=True)
class MulticlassWaiver:
    """Клас, узятий без вимог мультикласу (правило дому, а не PHB).

    Вимоги (PHB, p. 163) — це допуск до класу, а не похідне число листа.
    Коли група вирішує їх обійти, лист має це **памʼятати**: інакше персонаж
    виглядав би так, ніби відповідає вимогам, яких не має. Тому тут
    зберігається і клас, і те, чого саме не було («INT 13», «STR 13 або DEX 13»).
    """

    class_key: str
    requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        key = self.class_key.strip()
        if not key:
            raise ValidationError("вимоги проігноровано для класу без ключа")
        object.__setattr__(self, "class_key", key.casefold())
        object.__setattr__(
            self,
            "requirements",
            tuple(text.strip() for text in self.requirements if text and text.strip()),
        )

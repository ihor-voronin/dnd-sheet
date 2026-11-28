"""Власні вміння: те, що є за столом, але немає в книгах.

Дар майстра, сила предмета, домашнє правило — у довіднику їх немає, тож
текст пише гравець, а лист показує його з позначкою «власне». Правила з
нього нічого не виводять: жодних бонусів до чисел, лише текст.

Єдине, що лист уміє з ним робити, — лічильник «N разів на відпочинок»: такий
самий, як у класових ресурсів (`feature_resources`), тому короткий і
тривалий відпочинок відновлюють його без окремої логіки.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import MAX_LEVEL

#: Скільки власних умінь може мати персонаж: лист — не вікі кампанії.
MAX_CUSTOM_FEATURES = 50
MAX_NAME = 120
MAX_ORIGIN = 120
MAX_TEXT = 4000
#: Більше за 99 використань — уже не лічильник, а «за бажанням».
MAX_USES = 99

#: Коли відновлюється лічильник (ті самі значення, що в `feature_resources`).
RECHARGES = ("short", "long")

#: Префікс ключа лічильника у `SheetState.feature_used`.
RESOURCE_PREFIX = "custom:"


@dataclass(frozen=True, slots=True)
class CustomFeature:
    """Власне вміння персонажа: назва, звідки, текст і (за бажанням) лічильник."""

    id: str
    name: str
    text: str = ""
    #: Звідки вміння: «дар майстра», «Перстень вогню» — вільним текстом.
    origin: str | None = None
    #: З якого рівня персонажа (якщо це важливо для столу).
    level: int | None = None
    #: Скільки разів між відпочинками; `None` — без лічильника.
    uses: int | None = None
    recharge: str | None = None

    def __post_init__(self) -> None:
        key = (self.id or "").strip()
        if not key or len(key) > 40 or not all(char.isalnum() or char in "-_" for char in key):
            raise ValidationError("неприпустимий id власного вміння")
        object.__setattr__(self, "id", key)
        name = (self.name or "").strip()
        if not name:
            raise ValidationError("власне вміння без назви")
        if len(name) > MAX_NAME:
            raise ValidationError(f"назва вміння довша за {MAX_NAME} символів")
        object.__setattr__(self, "name", name)
        text = (self.text or "").strip()
        if len(text) > MAX_TEXT:
            raise ValidationError(f"{name}: текст вміння довший за {MAX_TEXT} символів")
        object.__setattr__(self, "text", text)
        origin = (self.origin or "").strip()
        if len(origin) > MAX_ORIGIN:
            raise ValidationError(f"{name}: «звідки» довше за {MAX_ORIGIN} символів")
        object.__setattr__(self, "origin", origin or None)
        if self.level is not None and (
            isinstance(self.level, bool) or not isinstance(self.level, int) or not 1 <= self.level <= MAX_LEVEL
        ):
            raise ValidationError(f"{name}: рівень має бути від 1 до {MAX_LEVEL}")
        self._validate_uses(name)

    def _validate_uses(self, name: str) -> None:
        if self.uses is None:
            if self.recharge is not None:
                raise ValidationError(f"{name}: відпочинок без кількості використань")
            return
        if isinstance(self.uses, bool) or not isinstance(self.uses, int) or not 1 <= self.uses <= MAX_USES:
            raise ValidationError(f"{name}: використань має бути від 1 до {MAX_USES}")
        if self.recharge not in RECHARGES:
            raise ValidationError(f"{name}: відновлення — short або long")

    @property
    def resource_key(self) -> str | None:
        """Ключ лічильника в `feature_used`; без використань — немає."""
        return f"{RESOURCE_PREFIX}{self.id}" if self.uses is not None else None

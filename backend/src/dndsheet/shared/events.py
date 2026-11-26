"""Доменні події: прості іммутабельні факти.

Шина подій зʼявиться разом із персистентністю (етап 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class CharacterCreated(DomainEvent):
    character_id: str = ""
    name: str = ""


@dataclass(frozen=True, slots=True)
class LevelGained(DomainEvent):
    character_id: str = ""
    level: int = 1


@dataclass(frozen=True, slots=True)
class AbilityScoresChanged(DomainEvent):
    character_id: str = ""


@dataclass(frozen=True, slots=True)
class LayoutCustomized(DomainEvent):
    character_id: str = ""


@dataclass(frozen=True, slots=True)
class SheetExported(DomainEvent):
    character_id: str = ""
    render_format: str = ""

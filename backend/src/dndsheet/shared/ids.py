"""Ідентифікатори агрегатів."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from dndsheet.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class CharacterId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValidationError("CharacterId не може бути порожнім")

    @classmethod
    def new(cls) -> "CharacterId":
        return cls(str(uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class UserId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValidationError("UserId не може бути порожнім")

    @classmethod
    def new(cls) -> "UserId":
        return cls(str(uuid4()))

    def __str__(self) -> str:
        return self.value

"""Помилки домену. Без залежностей від фреймворків."""

from __future__ import annotations


class DomainError(Exception):
    """Базова помилка домену."""


class ValidationError(DomainError):
    """Порушено інваріант домену."""


class NotFoundError(DomainError):
    """Агрегат не знайдено."""


class ConflictError(DomainError):
    """Конфлікт версій (optimistic locking)."""

"""Що публікуємо: ліцензія × політика × чи є українська; адреси сторінок."""

from __future__ import annotations

import pytest
from dndsheet.site.domain.publication import Policy, Publication, name_key, publication, slugify


@pytest.mark.parametrize("license", ["srd", "free"])
@pytest.mark.parametrize("policy", list(Policy))
def test_open_licenses_are_always_published_in_full(license: str, policy: Policy) -> None:
    assert publication(license, policy) == Publication(text=True, index=True)


def test_book_text_follows_the_policy() -> None:
    assert publication("proprietary", Policy.FULL) == Publication(text=True, index=True)
    assert publication("proprietary", Policy.SUMMARY) == Publication(text=False, index=True)
    assert publication("third_party", Policy.NOINDEX) == Publication(text=True, index=False)


def test_a_page_without_ukrainian_is_not_indexed() -> None:
    assert publication("srd", Policy.FULL, has_ukrainian=False) == Publication(text=True, index=False)
    assert publication("proprietary", Policy.SUMMARY, has_ukrainian=False) == Publication(text=False, index=False)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, Policy.FULL),
        ("", Policy.FULL),
        ("SUMMARY", Policy.SUMMARY),
        (" noindex ", Policy.NOINDEX),
        ("x", Policy.FULL),
    ],
)
def test_policy_parses_the_environment_value(raw: str | None, expected: Policy) -> None:
    assert Policy.parse(raw) is expected


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Fireball", "fireball"),
        ("Abi-Dalzim's Horrid Wilting", "abi-dalzims-horrid-wilting"),
        ("Ashardalon’s Stride", "ashardalons-stride"),
        ("Dragonborn (Chromatic)", "dragonborn-chromatic"),
        ("+1 Longsword", "1-longsword"),
        ("Mordenkainen's Magnificent Mansion", "mordenkainens-magnificent-mansion"),
    ],
)
def test_slugs_come_from_the_english_name(name: str, slug: str) -> None:
    assert slugify(name) == slug
    assert name_key(name) == slug

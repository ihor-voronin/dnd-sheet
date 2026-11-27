"""Єдина термінологія: `content/glossary.uk.yml` — джерело правди.

`avoid` — написання, заборонені скрізь (код, екран, переклади корпусу);
`avoid_code` — лише в коді й на екрані (у художніх текстах слово може мати
інше значення: «шкода» як harm). Згенеровані словники назв не скануються.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[3]
GLOSSARY = ROOT / "content" / "glossary.uk.yml"
SKIP = ("uk-items.ts", "uk-spells.ts", "uk-feats.ts")


def _rules(key: str) -> list[tuple[re.Pattern[str], str]]:
    terms = yaml.safe_load(GLOSSARY.read_text(encoding="utf-8"))["terms"]
    return [(re.compile(pattern), term["uk"]) for term in terms for pattern in term.get(key) or ()]


def _code_files() -> list[Path]:
    roots = [ROOT / "frontend" / "src", ROOT / "backend" / "src"]
    files = [p for root in roots if root.is_dir() for p in root.rglob("*") if p.suffix in {".ts", ".tsx", ".py"}]
    return [p for p in files if p.name not in SKIP]


def _content_files() -> list[Path]:
    folder = ROOT / "content" / "translations"
    return sorted(folder.rglob("*.json")) if folder.is_dir() else []


def _problems(files: list[Path], rules: list[tuple[re.Pattern[str], str]]) -> list[str]:
    found: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for pattern, canonical in rules:
            found.extend(
                f"{path.relative_to(ROOT)}: «{match.group(0)}» → {canonical}" for match in pattern.finditer(text)
            )
    return found


def test_glossary_parses_and_terms_are_unique() -> None:
    terms = yaml.safe_load(GLOSSARY.read_text(encoding="utf-8"))["terms"]
    ids = [term["id"] for term in terms]
    assert len(ids) == len(set(ids))
    assert all(term.get("uk") and term.get("en") for term in terms)


def test_code_uses_canonical_terms() -> None:
    problems = _problems(_code_files(), _rules("avoid") + _rules("avoid_code"))
    assert not problems, "застарілі терміни в коді:\n" + "\n".join(problems[:20])


def test_translations_use_canonical_terms() -> None:
    problems = _problems(_content_files(), _rules("avoid"))
    assert not problems, "застарілі терміни в перекладах:\n" + "\n".join(problems[:20])

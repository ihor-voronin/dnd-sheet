"""Єдина термінологія інтерфейсу (docs/translation-rules.md).

Ловить повернення до старих варіантів у коді екрана й сервера: «порятунок»
замість «рятівний кидок», «слот» замість «комірка закляття» тощо. Згенеровані
словники й переклади корпусу сюди не входять — у них свої тести.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: Застаріле написання → канонічне (див. docs/translation-rules.md).
FORBIDDEN = {
    r"[Пп]орятун": "рятівний кидок",
    r"[Хх]іт-дайс": "кість хітів",
    r"(?<![а-яіїєґ])[Сс]лот(?:и|ів|у|ом)?(?![а-яіїєґ])": "комірка закляття",
    r"[Ее]кспертніст": "експертиза",
    r"[Дд]овг\w* відпоч": "тривалий відпочинок",
    r"(?<![а-яіїєґ])[Вв]том[аиу](?![а-яіїєґ])": "виснаження",
    r"Пів-ельф|Пів-орк|Тіфлінг|Голіаф|Генасі|(?<![Нн]а)[Пп]іврослик": "назви видів за глосарієм",
    r"Мучительн": "болісний",
}
SKIP = ("uk-items.ts", "uk-spells.ts", "uk-feats.ts")


def _files() -> list[Path]:
    roots = [ROOT / "frontend" / "src", ROOT / "backend" / "src"]
    files = [p for root in roots if root.is_dir() for p in root.rglob("*") if p.suffix in {".ts", ".tsx", ".py"}]
    return [p for p in files if p.name not in SKIP]


def test_interface_uses_canonical_terms() -> None:
    problems: list[str] = []
    for path in _files():
        text = path.read_text(encoding="utf-8")
        for pattern, canonical in FORBIDDEN.items():
            for match in re.finditer(pattern, text):
                problems.append(f"{path.relative_to(ROOT)}: «{match.group(0)}» → {canonical}")
    assert not problems, "застарілі терміни:\n" + "\n".join(problems[:20])

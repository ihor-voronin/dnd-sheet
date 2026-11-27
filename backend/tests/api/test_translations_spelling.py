"""Правопис ігрових термінів у перекладах: «хіти», а не «хити».

Це не косметика: «хит» — інше слово, і саме так у текстах зʼявлялося
«кістки хитів» замість «кістки хітів». Тест ловить регресію, якщо хтось
згенерує переклад із тим самим написанням.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: Форми слова «хит» (з «и»): у нас «хіт» («хіти», «кістка хіту»). «Хитрість»,
#: «хитання», «хитнути» — звичайні слова й не збігаються з цим шаблоном.
WRONG = re.compile(
    r"(?<![А-Яа-яІіЇїЄєҐґ])[хХ][иИ]т(?:ів|у|ом|ами|ах|и)?(?![А-Яа-яІіЇїЄєҐґ])"
)


def _layer_files() -> list[Path]:
    folder = ROOT / "content" / "translations"
    return sorted(folder.rglob("*.json")) if folder.is_dir() else []


def test_ukrainian_translations_use_hit_not_hyt() -> None:
    problems: list[str] = []
    for path in _layer_files():
        text = path.read_text(encoding="utf-8")
        for match in WRONG.finditer(text):
            problems.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    assert not problems, "знайдено «хит…»: " + "; ".join(problems[:5])

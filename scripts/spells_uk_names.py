"""Переписати `frontend/src/features/character/uk-spells.ts` з `content/translations/spells/names.json`.

Джерело назв — переклад у `content/translations/spells/` (звірений із
D&D World, `var/reference/dndworld-spells.json`); фронтенд не читає `content/`,
тому словник дублюється згенерованим модулем.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "content" / "translations" / "spells" / "names.json"
TARGET = ROOT / "frontend" / "src" / "features" / "character" / "uk-spells.ts"

HEADER = """/** Українські назви заклять — генерований файл.
 *
 * Не правити руками: джерело — `content/translations/spells/names.json`
 * (переписує `scripts/spells_uk_names.py`). Ключ — англійська назва в нижньому
 * регістрі з прямим апострофом; значення — лише українська назва.
 */

export const SPELL_NAMES: Record<string, string> = {
"""


def main() -> None:
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    body = "".join(
        f"  {json.dumps(row['en'].casefold().replace('’', chr(39)), ensure_ascii=False)}: "
        f"{json.dumps(row['name_uk'], ensure_ascii=False)},\n"
        for row in sorted(rows, key=lambda row: row["en"].casefold())
    )
    TARGET.write_text(HEADER + body + "};\n", encoding="utf-8")


if __name__ == "__main__":
    main()

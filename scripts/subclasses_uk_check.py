"""Перевірити повноту перекладу класів: чи кожен вхід має вихід.

Переклад роблять агенти файлами, тому легко «загубити» один id — і екран
тихо покаже англійське вміння. Скрипт звіряє `var/uk/classes/input/*.json` з
`content/translations/classes/*.json` і каже, чого бракує.

    python scripts/classes_uk_check.py           # звіт
    python scripts/classes_uk_check.py --strict  # код виходу 1, якщо є діри
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "var" / "uk" / "subclasses" / "input"
OUTPUT = ROOT / "content" / "translations" / "subclasses"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  ! {path.name}: невалідний JSON — {exc}")
        return []
    return rows if isinstance(rows, list) else []


def main(strict: bool) -> int:
    problems = 0
    total_expected = 0
    total_done = 0

    pairs = []
    for path in sorted(INPUT.glob("*.json")):
        field = "name_uk" if path.name in ("names.json", "entries.json") else "text_uk"
        pairs.append((path.stem, path.name, field))

    for kind, name, field in pairs:
        expected = {str(row.get("id")) for row in load(INPUT / name)}
        got = {str(row.get("id")): str(row.get(field) or "") for row in load(OUTPUT / name)}
        total_expected += len(expected)
        total_done += sum(1 for key in expected if got.get(key, "").strip())
        missing = sorted(expected - set(got))
        empty = sorted(key for key in expected if not got.get(key, "").strip())
        if missing or empty:
            problems += 1
            print(
                f"  {name}: {len(expected) - len(missing)}/{len(expected)}"
                + (f", немає {len(missing)}" if missing else "")
                + (f", порожні {len(empty)}" if empty else "")
            )
            if missing:
                print(f"    відсутні id: {', '.join(missing[:8])}")
        else:
            print(f"  {name}: {len(expected)}/{len(expected)} ✓")

    share = (total_done / total_expected * 100) if total_expected else 0
    print(f"\nразом: {total_done}/{total_expected} ({share:.1f}%)")
    if strict and problems:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--strict" in sys.argv))

"""Перевірити переклад заклять, рис і опційних умінь.

Для кожної черги `var/uk/<шар>/input/texts-NN.json` шукає однойменний файл у
`content/translations/<шар>/` і перевіряє:

* кожен `id` має непорожній `text_uk`;
* кістки (`2d6`, `1d8`) і числа з оригіналу є в перекладі — загублене число
  на екрані стає неправильним правилом;
* переклад не коротший за 55 % оригіналу (обрізаний текст);
* немає заборонених написань із `content/glossary.uk.yml` (`avoid`).

    python scripts/rules_uk_check.py                 # усі шари
    python scripts/rules_uk_check.py spells 07       # один файл
    python scripts/rules_uk_check.py --strict        # код виходу 1, якщо є проблеми
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("spells", "feats", "optional-features")
DICE = re.compile(r"\b\d+d\d+\b")
#: Число, а не частина кубика чи дробу: «КС 20.» наприкінці речення — теж число.
NUMBER = re.compile(r"(?<![\w.])\d+(?!\w|\.\d)")


def avoid_patterns() -> list[tuple[str, re.Pattern[str]]]:
    data = yaml.safe_load((ROOT / "content" / "glossary.uk.yml").read_text(encoding="utf-8"))
    patterns = []
    for term in data.get("terms", []):
        for raw in term.get("avoid") or []:
            patterns.append((term.get("uk", ""), re.compile(raw)))
    return patterns


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  ! {path}: невалідний JSON — {exc}")
        return []
    return rows if isinstance(rows, list) else []


def check_file(layer: str, name: str, avoid: list[tuple[str, re.Pattern[str]]]) -> list[str]:
    source = {row["id"]: row for row in load(ROOT / "var" / "uk" / layer / "input" / name)}
    output = {str(row.get("id")): str(row.get("text_uk") or "") for row in load(ROOT / "content" / "translations" / layer / name)}
    problems: list[str] = []
    for key, row in source.items():
        text = output.get(key, "").strip()
        label = f"{layer}/{name} {key} «{row['name_en']}»"
        if not text:
            problems.append(f"{label}: немає перекладу")
            continue
        original = row["text_en"]
        for dice in set(DICE.findall(original)):
            if dice not in text:
                problems.append(f"{label}: загублено кістку {dice}")
        missing = sorted(set(NUMBER.findall(original)) - set(NUMBER.findall(text)), key=int)
        if missing:
            problems.append(f"{label}: загублено числа {', '.join(missing)}")
        if len(text) < 0.55 * len(original):
            problems.append(f"{label}: переклад закороткий ({len(text)} з {len(original)} символів)")
        for term, pattern in avoid:
            found = pattern.search(text)
            if found:
                problems.append(f"{label}: «{found.group(0)}» — за глосарієм «{term}»")
    extra = set(output) - set(source)
    if extra:
        problems.append(f"{layer}/{name}: зайві id {', '.join(sorted(extra))}")
    return problems


def main(args: list[str]) -> int:
    # Консоль Windows (cp1251) не друкує «✓» — пишемо UTF-8 незалежно від неї.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    strict = "--strict" in args
    args = [arg for arg in args if arg != "--strict"]
    layers = [args[0]] if args else list(LAYERS)
    only = f"texts-{args[1]}.json" if len(args) > 1 else None
    avoid = avoid_patterns()
    total = 0
    for layer in layers:
        for path in sorted((ROOT / "var" / "uk" / layer / "input").glob("texts-*.json")):
            if only and path.name != only:
                continue
            problems = check_file(layer, path.name, avoid)
            total += len(problems)
            mark = "✓" if not problems else f"{len(problems)} проблем"
            print(f"{layer}/{path.name}: {mark}")
            for problem in problems[:30]:
                print("   ", problem)
    print(f"Разом проблем: {total}")
    return 1 if strict and total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

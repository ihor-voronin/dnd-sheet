"""Злиття перекладів предметів у два артефакти для застосунку.

Перекладачі пишуть по файлу на чергу (`var/translations/items/out/`). Тут
вони перевіряються й збираються докупи:

* `frontend/src/features/character/uk-items.ts` — назви. Синхронні, бо
  список інвентаря має показати українською одразу, без «мигання».
* `frontend/public/items-uk.json` — описи. Вантажаться окремо й лише тоді,
  коли предмет розгорнули: тримати 200 КБ тексту в бандлі не треба.

Ключ — англійська назва в нижньому регістрі, як її віддає довідник. Одну
й ту саму назву різні книги дають кілька разів, тому перемагає запис, який
прийшов із описом; решта лише назви.

Перевірки не декоративні: без них у словник потрапляє обрізаний JSON,
чужа назва замість своєї або текст без кістки (1d6 «загубилась» у
перекладі) — і це видно вже на екрані, а не тут.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "var" / "translations" / "items"
IN_DIR = WORK / "in"
OUT_DIR = ROOT / "content" / "translations" / "items"
TS_FILE = ROOT / "frontend" / "src" / "features" / "character" / "uk-items.ts"
JSON_FILE = ROOT / "frontend" / "public" / "items-uk.json"

#: Кістки й числа, які переклад не має права змінити: «2d4 + 2», «1d6».
DICE = re.compile(r"\d+d\d+(?:\s*[+-]\s*\d+)?")
#: Пробіли в кістках різні («2d4+2» і «2d4 + 2») — порівнюємо без них.
SPACES = re.compile(r"\s+")

#: Слова, які перекладачі пишуть по-російському, а глосарій проєкту каже
#: інакше. Правку робимо тут, а не руками в 235 текстах: інакше наступна
#: черга перекладу поверне те саме.
REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # Spell Slot — «Комірка закляття» (content/glossary.uk.yml).
    ("ячеек", "комірок"),
    ("Ячеек", "Комірок"),
    ("ячейок", "комірок"),
    ("Ячейок", "Комірок"),
    ("ячейк", "комірк"),
    ("Ячейк", "Комірк"),
    # Wand — «паличка»: «палочка» це російське слово.
    ("палоч", "палич"),
    ("Палоч", "Палич"),
)


def polish(text: str) -> str:
    for wrong, right in REPLACEMENTS:
        text = text.replace(wrong, right)
    return text


def norm(value: str) -> str:
    """Ключ словника: та сама нормалізація, що в `uk.ts:itemKey`."""
    return SPACES.sub(" ", value.strip().lower()).replace("’", "'").replace("ʼ", "'")


def main() -> None:
    names: dict[str, str] = {}
    texts: dict[str, str] = {}
    problems: list[str] = []
    dice_warnings: list[str] = []

    for source in sorted(IN_DIR.glob("*.json")):
        target = OUT_DIR / source.name
        incoming = json.loads(source.read_text(encoding="utf-8"))
        if not target.exists():
            problems.append(f"{source.name}: перекладу немає")
            continue
        try:
            translated = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            problems.append(f"{source.name}: невалідний JSON ({error})")
            continue

        rows = translated.get("items")
        if not isinstance(rows, list):
            problems.append(f"{source.name}: немає списку items")
            continue
        by_id = {row.get("id"): row for row in rows if isinstance(row, dict)}
        for item in incoming["items"]:
            row = by_id.get(item["id"])
            if row is None:
                problems.append(f"{source.name}: бракує {item['id']}")
                continue
            name = polish(str(row.get("name_uk") or "").strip())
            if not name:
                problems.append(f"{source.name}: порожня назва {item['id']}")
                continue
            key = norm(item["name_en"])
            if key not in names:
                names[key] = name
            text = polish(str(row.get("text_uk") or "").strip())
            if not text:
                continue
            english = item.get("text_en") or ""
            if sorted(DICE.findall(english.replace(" ", ""))) != sorted(DICE.findall(text.replace(" ", ""))):
                dice_warnings.append(f"{item['name_en']}: кістки не збігаються")
            if key not in texts:
                texts[key] = text

    write_ts(names)
    write_json(names, texts)

    missing = sorted(set(names) - set(texts))
    print(f"назв: {len(names)}, з описом: {len(texts)}, назв без опису: {len(missing)}")
    for line in problems[:20]:
        print("ПРОБЛЕМА:", line)
    for line in dice_warnings[:20]:
        print("КІСТКИ:", line)
    print(f"файли: {TS_FILE.relative_to(ROOT)}, {JSON_FILE.relative_to(ROOT)}")


def write_ts(names: dict[str, str]) -> None:
    lines = [
        "/** Українські назви предметів — генерований файл.",
        " *",
        " * Не правити руками: його переписує `scripts/items_uk_merge.py` з черг",
        " * перекладу (`var/translations/items/out/`). Ключ — назва англійською в",
        " * нижньому регістрі, як її віддає довідник; значення — українська назва.",
        " */",
        "",
        "export const ITEM_NAMES: Record<string, string> = {",
    ]
    for key in sorted(names):
        lines.append(f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(names[key], ensure_ascii=False)},")
    lines.append("};")
    lines.append("")
    TS_FILE.write_text("\n".join(lines), encoding="utf-8")


def write_json(names: dict[str, str], texts: dict[str, str]) -> None:
    payload = {"items": {key: {"name": names.get(key, ""), "text": texts[key]} for key in sorted(texts)}}
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

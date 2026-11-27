"""Згенерувати `var/uk/GLOSSARY.md` для агентів перекладу з `content/glossary.uk.yml`.

Джерело правди — YAML; цей файл лише зручна для читання копія (не правити руками).
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "content" / "glossary.uk.yml"
RULES = ROOT / "docs" / "translation-rules.md"
TARGET = ROOT / "var" / "uk" / "GLOSSARY.md"


def main() -> None:
    terms = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))["terms"]
    lines = [
        "# Глосарій (згенеровано з content/glossary.uk.yml — не правити)",
        "",
        "| English | Українською | Не писати | Примітка |",
        "|---|---|---|---|",
    ]
    for term in terms:
        avoid = ", ".join(f"`{p}`" for p in (term.get("avoid") or []) + (term.get("avoid_code") or []))
        lines.append(f"| {term['en']} | {term['uk']} | {avoid} | {term.get('note') or ''} |")
    rules = RULES.read_text(encoding="utf-8")
    style = rules[rules.index("## Як показувати") :]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(lines) + "\n\n" + style, encoding="utf-8")


if __name__ == "__main__":
    main()

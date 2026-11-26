"""Конвеєр ingest: D&D Beyond → компендіум (JSON).

Етапи:
    discover — побудувати список сторінок книги (BFS по змісту)
    fetch    — завантажити сирий HTML у content/raw/<source>/ (з чекпойнтом)
    parse    — HTML → записи корпусів (JSONL) за contract/compendium-entry.schema.json;
               категорія визначає корпус: довідник листа (content/compendium)
               або бестіарій (content/bestiary)

Запуск з кореня репозиторію:
    python -m scripts.ingest.cli discover --source phb-2014
    python -m scripts.ingest.cli fetch --source phb-2014
    python -m scripts.ingest.cli parse --source phb-2014
    python -m scripts.ingest.cli run --source phb-2014

Сесія: cookies у content/.session/cookies.json (не комітяться, живі креденшели).
"""

__all__ = ["config", "session", "discover", "fetch", "html2md", "records", "cli"]

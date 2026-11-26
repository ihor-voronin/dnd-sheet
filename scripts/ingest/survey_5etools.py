"""Зріз 5e.tools: скільки передісторій / рис / видів дає кожна книга.

Джерело — довідкові корпуси дзеркала (content/raw/_index/*.json), а не файли
книг: у файлі книги опції лише посиланнями, текст лежить у корпусі категорії.

Друкує:
  1) загальні кількості;
  2) таблицю «джерело → кількість» для передісторій, рис і видів;
  3) записи, чиїх джерел немає в нашому корпусі (кандидати в прогалини).

Запуск:  python scripts/ingest/survey_5etools.py
"""
import json
from collections import Counter
from pathlib import Path

# 5e.tools source id книг, які вже розібрані в content/compendium. Записані саме
# id-ми дзеркала (вони не збігаються з нашими теками: FTD = ftod, MPMM = motm,
# AIS/AAG = sais, DSotDQ = sotdq). Locathah Rising (LR) свідомо немає: він лише
# завантажений, не розібраний.
OURS = {
    "PHB", "DMG", "MM", "XGE", "TCE", "SCAG", "FTD", "EGW", "AI", "VGM", "MTF",
    "MPMM", "GGR", "ERLW", "MOT", "VRGR", "SCC", "AIS", "AAG", "BMT", "WBtW",
    "TTP", "OGA", "WGTE", "DoD", "PotA", "SKT", "ToD", "WDH", "WDMM", "CM",
    "TftYP", "LLK", "CoTN", "LMoP", "Wa", "DDIA-MORD", "DDvRaM", "BGG", "EEPC",
    "DSotDQ", "SAC", "UA", "MPMV1", "MCV1", "MCV2", "MCV4", "MFFV1", "TVD",
}

# Книги лінійки 2024+ (або поза нею) — вони «відсутні в корпусі» законно.
OTHER_EDITION = {"XPHB", "FRHoF", "EFA", "RHW", "AU", "PL", "WoW", "LFL", "ABH"}


def repo_root() -> Path:
    for cand in Path(__file__).resolve().parents:
        if (cand / "content" / "raw").is_dir():
            return cand
    raise SystemExit("не знайдено корінь репозиторію з content/raw")


def load(root: Path, name: str, key: str) -> list:
    path = root / "content" / "raw" / "_index" / name
    if not path.exists():
        raise SystemExit(f"немає {path} — спершу scripts/ingest/fetch_5etools.py")
    return json.loads(path.read_text(encoding="utf-8")).get(key, [])


def main() -> None:
    root = repo_root()
    bg = load(root, "backgrounds-5etools.json", "background")
    feats = load(root, "feats-5etools.json", "feat")
    races = load(root, "races-5etools.json", "race")
    subraces = load(root, "races-5etools.json", "subrace")
    print(f"передісторії: {len(bg)}  риси: {len(feats)}  "
          f"види: {len(races)} (+{len(subraces)} підрас)")

    for label, records in (("ПЕРЕДІСТОРІЇ", bg), ("РИСИ", feats), ("ВИДИ", races)):
        counter = Counter(r.get("source", "?") for r in records)
        print(f"\n--- {label}: {len(counter)} джерел ---")
        for src, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
            if src in OURS:
                mark = ""
            elif src in OTHER_EDITION:
                mark = "   (лінійка 2024+)"
            else:
                mark = "   << немає в корпусі"
            print(f"  {src:12s} {count:3d}{mark}")

    for label, records in (("ПЕРЕДІСТОРІЇ", bg), ("РИСИ", feats), ("ВИДИ", races)):
        missing = [r for r in records
                   if r.get("source") not in OURS and r.get("source") not in OTHER_EDITION]
        print(f"\n--- {label} з книг лінійки 2014, яких немає в корпусі: {len(missing)} ---")
        for r in missing:
            print(f"  {r.get('source'):10s} {r.get('name')}")


if __name__ == "__main__":
    main()

"""Українські назви передісторій і їхніх рис — `content/translations/backgrounds/names.json`.

Назви передісторій уже живуть у `TERMS` на фронтенді («Солдат (Soldier)»), і
дублювати їх тут немає сенсу: скрипт **читає** `uk.ts` і бере звідти готові
назви. Так один список лишається єдиним джерелом, і розбіжність неможлива.

Назви рис (`Military Rank`, `Shelter of the Faithful`) — навпаки, тут: у
`FEATURES` їх було лише кілька, а бекенд віддає їх для шапки листа й картки.

Запуск: `python scripts/backgrounds_uk_names.py`
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "var" / "uk" / "backgrounds" / "input" / "names.json"
OUTPUT = ROOT / "content" / "translations" / "backgrounds" / "names.json"
UK_TS = ROOT / "frontend" / "src" / "features" / "character" / "uk.ts"

#: Назви рис передісторій. Ключі — як у корпусі.
FEATURE_NAMES: dict[str, str] = {
    "Wanderer": "Мандрівник",
    "Initiate of High Sorcery": "Посвячений Високого чаклунства",
    "Rustic Hospitality": "Сільська гостинність",
    "Legion Station": "Місце в легіоні",
    "Historical Knowledge": "Історичні знання",
    "Inheritance": "Спадок",
    "Rubblebelt Refuge": "Притулок у Рубблбелті",
    "Researcher": "Дослідник",
    "Never Tell Me the Odds": "Не кажи мені про шанси",
    "Squire of Solamnia": "Зброєносець Солампії",
    "Ear to the Ground": "Вухо до землі",
    "Criminal Contact": "Злочинні звʼязки",
    "Mercenary Life": "Найманське життя",
    "Rune Shaper": "Формувач рун",
    "Conclave's Shelter": "Притулок конклаву",
    "Legal Authority": "Правові повноваження",
    "Silverquill Initiate": "Посвячений Сільверквіллу",
    "Carnival Fixture": "Душа карнавалу",
    "Name Dropping": "Гра на йменнях",
    "Retainers": "Почет",
    "Dual Personalities": "Подвійна особистість",
    "Shelter of the Faithful": "Притулок вірних",
    "Guild Membership": "Членство в гільдії",
    "Respect of the Stout Folk": "Повага кременого народу",
    "Steady": "Непохитність",
    "Position of Privilege": "Привілейоване становище",
    "False Identity": "Фальшива особистість",
    "Adept Linguist": "Вправний мовознавець",
    "Prismari Initiate": "Посвячений Призмарі",
    "City Secrets": "Міські таємниці",
    "Undercity Paths": "Стежки підмістя",
    "Urban Infrastructure": "Міська інфраструктура",
    "Kept in Style": "Життя в розкоші",
    "Heart of Darkness": "Серце темряви",
    "Quandrix Initiate": "Посвячений Квандрікс",
    "Ship's Passage": "Місце на кораблі",
    "I'll Patch It!": "Я це залатаю!",
    "Ballad of the Grinning Fool": "Балада про Ґріннера",
    "Choose a Feature": "Вибір риси",
    "Lorehold Initiate": "Посвячений Лорголду",
    "Leverage": "Важіль впливу",
    "House Connections": "Звʼязки дому",
    "Conviction": "Переконання",
    "Safe Haven": "Безпечна гавань",
    "Supply Chain": "Ланцюг постачання",
    "Official Inquiry": "Офіційне розслідування",
    "Fearsome Reputation": "Страшна репутація",
    "Still Standing": "Усе ще на ногах",
    "Down Low": "Тихо й непомітно",
    "Bad Reputation": "Погана репутація",
    "By Popular Demand": "На загальний попит",
    "Watcher's Eye": "Око спостерігача",
    "Knightly Regard": "Лицарська повага",
    "All Eyes on You": "Усі погляди на вас",
    "Fortune's Favor": "Прихильність долі",
    "Planar Infusion": "Планарне просочення",
    "Harvest the Water": "Зібрати воду",
    "Library Access": "Доступ до бібліотеки",
    "Shadow Network": "Тіньова мережа",
    "Strike of the Giants": "Удар велетнів",
    "Spy Contact": "Звʼязок зі шпигуном",
    "Military Rank": "Військове звання",
    "Court Functionary": "Придворний чиновник",
    "Discovery": "Відкриття",
    "Legalese": "Юридична мова",
    "Inside Informant": "Інформатор зсередини",
    "Uthgardt Heritage": "Спадщина Утгарду",
    "Witherbloom Initiate": "Посвячений Візерблуму",
    "Feywild Connection": "Звʼязок із Фейвайлдом",
    "Echoes of Victory": "Відлуння перемоги",
}

#: Назви, яких немає в `TERMS` (нові книги): додаються тут.
EXTRA_BACKGROUND_NAMES: dict[str, str] = {
    "Gruul Anarch": "Анархіст Груула",
}

ENTRY = re.compile(r'(?:"([^"]+)"|([A-Za-z][\w \'’\-]*)):\s*"([^"]+)"')


def parse_terms(source: str) -> dict[str, str]:
    """Словник `TERMS` із `uk.ts` — щоб не тримати назви у двох місцях."""
    block = source.split("const TERMS", 1)[1].split("};", 1)[0]
    found: dict[str, str] = {}
    for match in ENTRY.finditer(block):
        key = (match.group(1) or match.group(2)).strip()
        found[normalise(key)] = match.group(3)
    return found


def normalise(text: str) -> str:
    return re.sub(r"[’ʼ'`]", "'", text.strip().casefold())


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def main() -> int:
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    terms = parse_terms(UK_TS.read_text(encoding="utf-8"))
    features = {normalise(key): value for key, value in FEATURE_NAMES.items()}
    extras = {normalise(key): value for key, value in EXTRA_BACKGROUND_NAMES.items()}

    translated: list[dict[str, str]] = []
    missing: list[str] = []
    for row in rows:
        name = row["name_en"]
        if row["kind"] == "background":
            value = terms.get(normalise(name)) or extras.get(normalise(name))
        else:
            value = features.get(normalise(name))
        if not value:
            missing.append(f"{row['kind']}: {name}")
            continue
        translated.append({"id": row["id"], "name_uk": value})

    if missing:
        print("БЕЗ ПЕРЕКЛАДУ:", *missing, sep="\n  ")
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(translated, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"назв: {len(translated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

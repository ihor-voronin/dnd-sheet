"""Українські назви класових умінь — джерело для `content/translations/classes/names.json`.

Тримаємо тут, а не в JSON, бо так видно весь список одним екраном: назви
повторюються у дванадцяти класів («Extra Attack», «Ability Score
Improvement»), і переклад має бути один. Назви підкласів-розділів
(«Martial Archetype», «Divine Domain») уже живуть у `TERMS` на фронтенді —
тут вони повторені дослівно, щоб не було двох варіантів.

Запуск: `python scripts/classes_uk_names.py`
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("DNDSHEET_CONTENT_DIR", str(ROOT / "content"))

from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

INPUT = ROOT / "var" / "uk" / "classes" / "input" / "names.json"
OUTPUT = ROOT / "content" / "translations" / "classes" / "names.json"

NAMES: dict[str, str] = {
    # --- спільні для всіх класів ----------------------------------------
    "Ability Score Improvement": "Покращення характеристик",
    "Extra Attack": "Додаткова атака",
    "Fighting Style": "Бойовий стиль",
    "Spellcasting": "Чарування",
    "Equipment": "Спорядження",
    "Hit Points": "Хіти",
    "Proficiencies": "Володіння",
    "Quick Build": "Швидка збірка",
    # --- варвар ----------------------------------------------------------
    "Rage": "Лють",
    "Unarmored Defense": "Оборона без броні",
    "Reckless Attack": "Безрозсудна атака",
    "Danger Sense": "Чуття небезпеки",
    "Primal Path": "Прадавній шлях",
    "Fast Movement": "Швидкий рух",
    "Feral Instinct": "Дикий інстинкт",
    "Brutal Critical": "Жорстокий критичний удар",
    "Relentless Rage": "Невтомна лють",
    "Persistent Rage": "Незгасна лють",
    "Indomitable Might": "Нескорена міць",
    "Primal Champion": "Первісний чемпіон",
    "Path of the Berserker": "Шлях берсерка",
    "Path of the Totem Warrior": "Шлях воїна-тотема",
    # --- бард ------------------------------------------------------------
    "Bardic Inspiration": "Бардівське натхнення",
    "Jack of All Trades": "Майстер на всі руки",
    "Font of Inspiration": "Джерело натхнення",
    "Song of Rest": "Пісня відпочинку",
    "Bard College": "Коледж бардів",
    "Countercharm": "Протичари",
    "Magical Secrets": "Магічні таємниці",
    "Superior Inspiration": "Вище натхнення",
    "College of Lore": "Колегія знань",
    "College of Valor": "Колегія звитяги",
    # --- жрець -----------------------------------------------------------
    "Divine Domain": "Божественний домен",
    "Channel Divinity": "Канал божественності",
    "Destroy Undead": "Знищення нежиті",
    "Divine Intervention": "Божественне втручання",
    "Knowledge Domain": "Домен знань",
    "Life Domain": "Домен життя",
    "Light Domain": "Домен світла",
    "Nature Domain": "Домен природи",
    "Tempest Domain": "Домен бурі",
    "Trickery Domain": "Домен обману",
    "War Domain": "Домен війни",
    # --- друїд -----------------------------------------------------------
    "Druidic": "Друїдська мова",
    "Wild Shape": "Дика форма",
    "Druid Circle": "Коло друїдів",
    "Timeless Body": "Позачасове тіло",
    "Beast Spells": "Звірині закляття",
    "Archdruid": "Архідруїд",
    "Circle of the Land": "Коло землі",
    "Circle of the Moon": "Коло місяця",
    # --- воїн ------------------------------------------------------------
    "Second Wind": "Друге дихання",
    "Action Surge": "Приплив сил",
    "Martial Archetype": "Військовий архетип",
    "Indomitable": "Нескорений",
    "Trained for Danger": "Навчений небезпеці",
    "Champion": "Чемпіон",
    "Battle Master": "Бойовий майстер",
    "Eldritch Knight": "Містичний лицар",
    # --- монах -----------------------------------------------------------
    "Training and Asceticism": "Тренування й аскетизм",
    "Martial Arts": "Бойові мистецтва",
    "Ki": "Кі",
    "Unarmored Movement": "Рух без броні",
    "Monastic Tradition": "Монастирська традиція",
    "Deflect Missiles": "Відбивання снарядів",
    "Ki-Empowered Strikes": "Удари, наділені кі",
    "Slow Fall": "Повільне падіння",
    "Stunning Strike": "Приголомшливий удар",
    "Stillness of Mind": "Спокій розуму",
    "Purity of Body": "Чистота тіла",
    "Tongue of the Sun and Moon": "Мова сонця й місяця",
    "Diamond Soul": "Діамантова душа",
    "Empty Body": "Порожнє тіло",
    "Perfect Self": "Досконале я",
    "Way of the Open Hand": "Шлях відкритої долоні",
    "Way of Shadow": "Шлях тіні",
    "Way of the Four Elements": "Шлях чотирьох стихій",
    # --- паладин ---------------------------------------------------------
    "Divine Sense": "Божественне чуття",
    "Lay on Hands": "Накладання рук",
    "Divine Smite": "Божественна кара",
    "Divine Health": "Божественне здоровʼя",
    "Sacred Oath": "Священна клятва",
    "Aura of Protection": "Аура захисту",
    "Aura of Courage": "Аура відваги",
    "Improved Divine Smite": "Покращена божественна кара",
    "Cleansing Touch": "Очищувальний дотик",
    "Oath of Devotion": "Клятва відданості",
    "Oath of the Ancients": "Клятва давніх",
    "Oath of Vengeance": "Клятва помсти",
    # --- слідопит --------------------------------------------------------
    "Favored Enemy": "Улюблений ворог",
    "Natural Explorer": "Природжений дослідник",
    "Ranger Archetype": "Архетип слідопита",
    "Primeval Awareness": "Первісне чуття",
    "Landʼs Stride": "Земний крок",
    "Land’s Stride": "Земний крок",
    "Hide in Plain Sight": "Сховатися на видноті",
    "Vanish": "Зникнення",
    "Feral Senses": "Дике чуття",
    "Foe Slayer": "Вбивця ворогів",
    "Hunter": "Мисливець",
    "Beast Master": "Володар звірів",
    # --- плут ------------------------------------------------------------
    "Expertise": "Експертиза",
    "Sneak Attack": "Підступна атака",
    "Thievesʼ Cant": "Злодійський жаргон",
    "Thieves’ Cant": "Злодійський жаргон",
    "Cunning Action": "Хитра дія",
    "Roguish Archetype": "Злодійський архетип",
    "Uncanny Dodge": "Неймовірне ухиляння",
    "Evasion": "Ухиляння",
    "Reliable Talent": "Надійний хист",
    "Blindsense": "Сліпе чуття",
    "Slippery Mind": "Слизький розум",
    "Elusive": "Невловимий",
    "Stroke of Luck": "Удар удачі",
    "Thief": "Злодій",
    "Assassin": "Убивця",
    "Arcane Trickster": "Містичний шахрай",
    # --- чародій ---------------------------------------------------------
    "Sorcerous Origin": "Чарівниче походження",
    "Font of Magic": "Джерело магії",
    "Metamagic": "Метамагія",
    "Sorcerous Restoration": "Відновлення чарів",
    "Draconic Bloodline": "Драконяча кров",
    "Wild Magic": "Дика магія",
    # --- чаклун ----------------------------------------------------------
    "Otherworldly Patron": "Потойбічний патрон",
    "Pact Magic": "Магія угоди",
    "Eldritch Invocations": "Містичні виклики",
    "Pact Boon": "Дар угоди",
    "Mystic Arcanum": "Містичний аркан",
    "Eldritch Master": "Містичний майстер",
    "The Archfey": "Архіфея",
    "The Fiend": "Диявол",
    "The Great Old One": "Великий Стародавній",
    # --- маг -------------------------------------------------------------
    "Arcane Recovery": "Арканне відновлення",
    "Arcane Tradition": "Арканна традиція",
    "Spell Mastery": "Майстерність заклять",
    "Signature Spells": "Знакові закляття",
    "School of Abjuration": "Школа захисту",
    "School of Conjuration": "Школа виклику",
    "School of Divination": "Школа віщування",
    "School of Enchantment": "Школа чар",
    "School of Evocation": "Школа втілення",
    "School of Illusion": "Школа ілюзії",
    "School of Necromancy": "Школа некромантії",
    "School of Transmutation": "Школа перетворення",
    # --- містичні виклики чаклуна ---------------------------------------
    "Agonizing Blast": "Мучительний розряд",
    "Armor of Shadows": "Броня тіней",
    "Ascendant Step": "Піднесений крок",
    "Beast Speech": "Мова звірів",
    "Beguiling Influence": "Чари впливу",
    "Bewitching Whispers": "Зачаровані шепоти",
    "Book of Ancient Secrets": "Книга давніх таємниць",
    "Chains of Carceri": "Ланцюги Карцері",
    "Devilʼs Sight": "Диявольський зір",
    "Devil’s Sight": "Диявольський зір",
    "Dreadful Word": "Жахливе слово",
    "Eldritch Sight": "Містичний зір",
    "Eldritch Spear": "Містичний спис",
    "Eyes of the Rune Keeper": "Очі охоронця рун",
    "Fiendish Vigor": "Диявольська міць",
    "Gaze of Two Minds": "Погляд двох розумів",
    "Lifedrinker": "Пивець життя",
    "Mask of Many Faces": "Маска багатьох облич",
    "Master of Myriad Forms": "Володар безлічі форм",
    "Minions of Chaos": "Слуги хаосу",
    "Mire the Mind": "Замутити розум",
    "Misty Visions": "Туманні видіння",
    "One with Shadows": "Єдиний із тінями",
    "Otherworldly Leap": "Потойбічний стрибок",
    "Repelling Blast": "Відштовхувальний розряд",
    "Sculptor of Flesh": "Скульптор плоті",
    "Sign of Ill Omen": "Знак лихої прикмети",
    "Thief of Five Fates": "Крадій пʼяти доль",
    "Thirsting Blade": "Спраглий клинок",
    "Visions of Distant Realms": "Видіння далеких світів",
    "Voice of the Chain Master": "Голос володаря ланцюгів",
    "Whispers of the Grave": "Шепоти могили",
    "Witch Sight": "Відьомський зір",
}


def normalise(text: str) -> str:
    """Порівнювати назви без різниці в апострофах і регістрі."""
    return re.sub(r"[’ʼ'`]", "'", text.strip().casefold())


#: Назви, яких немає серед заголовків глави, але які є в індексі механік:
#: варіанти («Extra Attack (2)»), кроки («Destroy Undead (CR 1)») і опційні
#: вміння з TCoE. Екран показує їх у списку «Усі вміння класу за рівнями»,
#: а лист — у вкладці «Уміння», тому вони теж мають бути українською.
EXTRA_NAMES: dict[str, str] = {
    "Action Surge (two uses)": "Приплив сил (два використання)",
    "Arcane Tradition feature": "Уміння арканної традиції",
    "Artificer Specialist": "Фах артифіцера",
    "Artificer Specialist Feature": "Уміння фаху артифіцера",
    "Aura improvements": "Покращення аур",
    "Bard College feature": "Уміння колегії бардів",
    "Bardic Inspiration (d10)": "Бардівське натхнення (d10)",
    "Bardic Inspiration (d12)": "Бардівське натхнення (d12)",
    "Bardic Inspiration (d8)": "Бардівське натхнення (d8)",
    "Bardic Versatility": "Бардівська універсальність",
    "Brutal Critical (1 die)": "Жорстокий критичний удар (1 кістка)",
    "Brutal Critical (2 dice)": "Жорстокий критичний удар (2 кістки)",
    "Brutal Critical (3 dice)": "Жорстокий критичний удар (3 кістки)",
    "Cantrip Formulas": "Формули заговорів",
    "Cantrip Versatility": "Універсальність заговорів",
    "Channel Divinity: Harness Divine Power": "Канал божественності: Спрямувати божественну силу",
    "Dedicated Weapon": "Віддана зброя",
    "Deft Explorer": "Вправний дослідник",
    "Deft Explorer Improvement": "Покращення вправного дослідника",
    "Destroy Undead (CR 1)": "Знищення нежиті (ПН 1)",
    "Destroy Undead (CR 1/2)": "Знищення нежиті (ПН 1/2)",
    "Destroy Undead (CR 2)": "Знищення нежиті (ПН 2)",
    "Destroy Undead (CR 3)": "Знищення нежиті (ПН 3)",
    "Destroy Undead (CR 4)": "Знищення нежиті (ПН 4)",
    "Divine Domain feature": "Уміння божественного домену",
    "Divine Intervention Improvement": "Покращення божественного втручання",
    "Druid Circle feature": "Уміння кола друїдів",
    "Eldritch Versatility": "Містична універсальність",
    "Extra Attack (2)": "Додаткова атака (2)",
    "Extra Attack (3)": "Додаткова атака (3)",
    "Favored Enemy and Natural Explorer improvements": "Покращення улюбленого ворога й природженого дослідника",
    "Favored Enemy improvement": "Покращення улюбленого ворога",
    "Favored Foe": "Улюблена здобич",
    "Flash of Genius": "Спалах генія",
    "Focused Aim": "Зосереджений приціл",
    "Indomitable (three uses)": "Нескорений (три використання)",
    "Indomitable (two uses)": "Нескорений (два використання)",
    "Infuse Item": "Наповнити предмет",
    "Instinctive Pounce": "Інстинктивний стрибок",
    "Ki-Fueled Attack": "Атака, живана кі",
    "Magic Item Adept": "Знавець магічних предметів",
    "Magic Item Master": "Майстер магічних предметів",
    "Magic Item Savant": "Ерудит магічних предметів",
    "Magical Guidance": "Магічний провід",
    "Magical Inspiration": "Магічне натхнення",
    "Magical Tinkering": "Магічне ремесло",
    "Martial Archetype feature": "Уміння військового архетипу",
    "Martial Versatility": "Військова універсальність",
    "Metamagic Options": "Варіанти метамагії",
    "Monastic Tradition feature": "Уміння монастирської традиції",
    "Mystic Arcanum (6th level)": "Містичний аркан (6-й рівень)",
    "Mystic Arcanum (7th level)": "Містичний аркан (7-й рівень)",
    "Mystic Arcanum (8th level)": "Містичний аркан (8-й рівень)",
    "Mystic Arcanum (9th level)": "Містичний аркан (9-й рівень)",
    "Natural Explorer improvement": "Покращення природженого дослідника",
    "Nature's Veil": "Завіса природи",
    "Optional Rule: Firearm Proficiency": "Варіантне правило: володіння вогнепальною зброєю",
    "Otherworldly Patron feature": "Уміння потойбічного патрона",
    "Path Feature": "Уміння шляху",
    "Path feature": "Уміння шляху",
    "Primal Awareness": "Прадавня свідомість",
    "Primal Knowledge": "Прадавні знання",
    "Quickened Healing": "Прискорене зцілення",
    "Ranger Archetype feature": "Уміння архетипу слідопита",
    "Roguish Archetype feature": "Уміння злодійського архетипу",
    "Sacred Oath feature": "Уміння священної клятви",
    "Song of Rest (d10)": "Пісня відпочинку (d10)",
    "Song of Rest (d12)": "Пісня відпочинку (d12)",
    "Song of Rest (d6)": "Пісня відпочинку (d6)",
    "Song of Rest (d8)": "Пісня відпочинку (d8)",
    "Sorcerous Origin feature": "Уміння чарівничого походження",
    "Sorcerous Versatility": "Чарівнича універсальність",
    "Soul of Artifice": "Душа артефакту",
    "Spell-Storing Item": "Предмет, що зберігає закляття",
    "Spellcasting Focus": "Осередок чарування",
    "Steady Aim": "Певний приціл",
    "The Right Tool for the Job": "Правильний інструмент для роботи",
    "Tool Expertise": "Експертиза інструментів",
    "Unarmored Movement improvement": "Покращення руху без броні",
    "Wild Companion": "Дикий супутник",
    "Wild Shape Improvement": "Покращення дикої форми",
}


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def mechanics_names() -> set[str]:
    """Усі назви з індексу механік — те, що показує список умінь і лист."""
    service = build_service()
    names: set[str] = set()
    for definition in service.class_definitions():
        for feature in definition.features:
            names.add(feature.name_en)
    return names


def main() -> int:
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    lookup = {normalise(key): value for key, value in NAMES.items()}
    lookup.update({normalise(key): value for key, value in EXTRA_NAMES.items()})
    translated: dict[str, str] = {}
    missing: list[str] = []
    for row in rows:
        value = lookup.get(normalise(row["name_en"]))
        if value is None:
            missing.append(row["name_en"])
            continue
        translated[row["id"]] = value

    # Назви з індексу механік — те, що показує список умінь за рівнями й
    # вкладка «Уміння» на листі. Вони не заголовки глави, але без перекладу
    # список мішає мови.
    for name_en in sorted(mechanics_names()):
        value = lookup.get(normalise(name_en))
        if value is None:
            missing.append(f"механіка: {name_en}")
            continue
        translated.setdefault(ident(name_en), value)

    if missing:
        print("БЕЗ ПЕРЕКЛАДУ:", *missing, sep="\n  ")
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            [{"id": key, "name_uk": value} for key, value in translated.items()],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"назв: {len(translated)} (глава класу + індекс механік)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

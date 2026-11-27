"""Українські фрази спорядження передісторій — `content/translations/backgrounds/equipment.json`.

Рядок `Equipment:` книги — це список предметів, а не правило, тому його
переклад живе тут, а не в тексті риси: фрази короткі, повторюються між
передісторіями («pouch containing 10 gp» у п'яти) і показуються на екрані
окремими пунктами. Пошук у довіднику й додавання предметів ідуть за
англійським текстом, тож переклад нічого не ламає.

Запуск: `python scripts/backgrounds_uk_equipment.py`
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "var" / "uk" / "backgrounds" / "input" / "equipment.json"
OUTPUT = ROOT / "content" / "translations" / "backgrounds" / "equipment.json"

UK: dict[str, str] = {
    "1 ounce of ink": "1 унція чорнила",
    "1 sp": "1 ср",
    "10 gp": "10 зм",
    "5 gp": "5 зм",
    "5 sticks of incense": "5 палочок ладану",
    "50 feet of silk rope": "50 футів шовкової мотузки",
    "Badge": "значок",
    "Disguise kit": "набір для маскування",
    "Fishing tackle": "рибальське приладдя",
    "One set of traveler’s clothes": "один комплект одягу мандрівника",
    "Your inheritance": "ваш спадок",
    "abacus": "рахівниця",
    "any one musical instrument": "будь-який один музичний інструмент",
    "artisan's tools (one of your choice)": "інструменти ремісника (на ваш вибір)",
    "artisan’s tools": "інструменти ремісника",
    "artisan’s tools (one of your choice)": "інструменти ремісника (на ваш вибір)",
    "artisan’s tools with which you are proficient": "інструменти ремісника, якими ви володієте",
    "banner": "прапор",
    "belaying pin (club)": "кабестан-кий (дробина)",
    "belt pouch containing 10 gp": "поясний гаманець із 10 зм",
    "belt pouch containing 15 gp": "поясний гаманець із 15 зм",
    "black cloak with a hood": "чорний плащ із каптуром",
    "blank book": "порожній зошит",
    "bone dice": "кістки з кості",
    "bone dice set": "набір кісток із кості",
    "book about plant identification": "книга про визначення рослин",
    "book of arcane theory": "книга з теорії аркани",
    "book of poetry": "збірка поезії",
    "borrowed book on the subject of your current study": "позичена книга з теми вашого поточного дослідження",
    "bottle of black ink": "пляшечка чорного чорнила",
    "bottle of ink": "пляшечка чорнила",
    "bronze discus": "бронзовий диск",
    "brooch": "брошка",
    "bullseye lantern": "спрямований ліхтар",
    "carnival uniform": "карнавальний однострій",
    "clothes appropriate to your duties and a pouch containing 20 gp": "одяг, доречний вашим обовʼязкам, і гаманець із 20 зм",
    "common clothes": "звичайний одяг",
    "common clothes in your faction's style": "звичайний одяг у стилі вашої фракції",
    "company": "загін",
    "copy of a seminal faction text (or a code-book for a covert faction)": "примірник основоположного тексту фракції (або шифрувальник для таємної фракції)",
    "costume": "костюм",
    "costume clothes": "костюмний одяг",
    "cracked hourglass": "тріснутий пісковий годинник",
    "crowbar": "ломик",
    "dagger that belonged to a fallen comrade": "кинджал, що належав полеглому товаришу",
    "dark common clothes including a hood": "темний звичайний одяг, зокрема каптур",
    "deck of cards": "колода карт",
    "disguise kit": "набір для маскування",
    "dungeon": "підземелля",
    "emblem of your faction": "емблема вашої фракції",
    "evidence from a past case (choose one or roll for a trinket from the Horror Trinkets table later in this chapter)": "доказ з минулої справи (виберіть один або киньте на дрібничку з таблиці жахливих дрібничок далі в цьому розділі)",
    "fancy leather vest": "вишуканий шкіряний жилет",
    "favor of an admirer (love letter, lock of hair, or trinket)": "знак уваги від шанувальника (любовний лист, пасмо волосся або дрібничка)",
    "favorite fishing lure": "улюблена рибальська приманка",
    "fine clothes": "вишуканий одяг",
    "fine clothes and a pouch containing 5 gp": "вишуканий одяг і гаманець із 5 зм",
    "five sheets of paper": "пʼять аркушів паперу",
    "folded flag emblazoned with the symbol of your ship": "складений прапор із символом вашого корабля",
    "gaming set (matching your chosen proficiency)": "набір для ігор (відповідно до обраного володіння)",
    "gaming set of your choice": "набір для ігор на ваш вибір",
    "gaming set you are proficient with": "набір для ігор, яким ви володієте",
    "gold-plated ring depicting a smiling face": "перстень із позолотою, на якому зображено усміхнене обличчя",
    "half-empty bottle": "напівпорожня пляшка",
    "hammer": "молоток",
    "herbalism kit": "набір травника",
    "holy symbol (a gift to you when you entered the priesthood)": "священний символ (дар вам, коли ви вступили до духовенства)",
    "hooded lantern": "ліхтар із кожухом",
    "horn with which to summon help": "ріг, щоб кликати допомогу",
    "house signet ring": "родовий перстень-печатка",
    "hunting trap": "мисливська пастка",
    "identification papers": "документи, що посвідчують особу",
    "ink pen": "письмове перо",
    "insignia of rank": "знаки розрізнення",
    "insignia of your rank": "знаки вашого звання",
    "iron pot": "залізний казан",
    "leather ball": "шкіряний мʼяч",
    "leather pouch with 10 gp": "шкіряний гаманець із 10 зм",
    "leather pouch with 15 gp": "шкіряний гаманець із 15 зм",
    "leather-bound diary": "щоденник у шкіряній оправі",
    "letter from a dead colleague posing a question you have not yet been able to answer": "лист від загиблого колеги з питанням, на яке ви досі не спромоглися відповісти",
    "letter of introduction from your guild": "рекомендаційний лист від вашої гільдії",
    "lucky charm": "талісман удачі",
    "lucky charm such as a rabbit foot": "талісман удачі, наприклад кроляча лапка",
    "magnifying glass": "збільшувальне скло",
    "maker’s mark chisel used to mark your handiwork with the symbol of the clan of crafters you learned your skill from": "різець для тавра майстра, яким ви позначаєте свої вироби символом клану ремісників, у якого вчилися",
    "manacles": "кайдани",
    "manifesto of your guiding philosophy": "маніфест вашої життєвої філософії",
    "map of the city you grew up in": "мапа міста, у якому ви виросли",
    "miner's pick": "гірницьке кайло",
    "monster hunter’s pack (containing a chest, a crowbar, a hammer, three wooden stakes, a holy symbol, a flask of holy water, a set of manacles, a steel mirror, a flask of oil, a tinderbox, and 3 torches)": "набір мисливця на монстрів (скриня, ломик, молоток, три деревʼяні кілки, священний символ, фляга святої води, набір кайданів, сталеве дзеркало, фляга олії, трутниця й 3 смолоскипи)",
    "musical instrument (one of your choice)": "музичний інструмент (на ваш вибір)",
    "musical instrument of your choice": "музичний інструмент на ваш вибір",
    "net": "сітка",
    "oiled leather wading boots": "промащені шкіряні чоботи для броду",
    "one trinket (determined by rolling on the Feywild Trinkets table)": "одна дрібничка (визначається кидком за таблицею дрібничок Фейвайлду)",
    "one trinket of special significance": "одна дрібничка особливого значення",
    "one trinket of special significance (choose one or roll on the Horror Trinkets table later in this chapter)": "одна дрібничка особливого значення (виберіть одну або киньте за таблицею жахливих дрібничок далі в цьому розділі)",
    "pair of leather boots": "пара шкіряних чобіт",
    "past trophy": "колишній трофей",
    "pet mouse": "ручний мишак",
    "playing card set": "набір гральних карт",
    "poisoner’s kit": "набір отруйника",
    "poorly wrought maps from your homeland that depict where you are in Faerûn": "недоладно намальовані мапи вашої батьківщини, що показують, де ви в Фаеруні",
    "portal key (such as a bag of golden tea leaves or the tooth of a planar beast)": "ключ порталу (наприклад, торбинка золотого чайного листя або зуб планарного звіра)",
    "pouch containing 10 gp": "гаманець із 10 зм",
    "pouch containing 10 gp worth of coins from different worlds and planes": "гаманець із монетами на 10 зм із різних світів і площин",
    "pouch containing 13 gp": "гаманець із 13 зм",
    "pouch containing 15 gp": "гаманець із 15 зм",
    "pouch containing 18 gp": "гаманець із 18 зм",
    "pouch containing 25 gp": "гаманець із 25 зм",
    "pouch containing 5 gp": "гаманець із 5 зм",
    "pouch containing 5 gp and a gem worth 10 gp": "гаманець із 5 зм і самоцвіт вартістю 10 зм",
    "pouch containing 8 gp": "гаманець із 8 зм",
    "pouch containing the remainder of your last wages (10 gp)": "гаманець із залишком вашої останньої платні (10 зм)",
    "prayer book": "молитовник",
    "prayer wheel": "молитовне колесо",
    "prayers": "молитви",
    "purse containing 20 gp": "гаманець із 20 зм",
    "purse containing 25 gp": "гаманець із 25 зм",
    "quill": "гусяче перо",
    "rank in the order": "звання в ордені",
    "ring of keys to unknown locks": "вʼязка ключів до невідомих замків",
    "rusty manacles": "іржаві кайдани",
    "scholar’s robes of your cloister": "учені шати вашого монастиря",
    "school uniform": "шкільний однострій",
    "scroll case stuffed full of notes from your studies": "тубус для сувоїв, набитий нотатками з ваших студій",
    "scroll of pedigree": "сувій із родоводом",
    "seal representing your place": "печатка, що представляє ваше місце",
    "set of tattoos marking your loyalty to Uthgar and your tribal totem": "набір татуювань, що позначають вашу відданість Утгару й ваш племінний тотем",
    "shovel": "лопата",
    "signet": "печатка",
    "signet ring": "перстень-печатка",
    "silk rope (50 feet)": "шовкова мотузка (50 футів)",
    "skin of fine zzar": "міх вишуканого ззару",
    "small knife": "малий ніж",
    "small piece of jewelry worth 10 gp in the style of your homeland’s craftsmanship": "невелика прикраса вартістю 10 зм у стилі ремесла вашої батьківщини",
    "small stone with a hole in the center (or you may roll for a random trinket on the Trinkets table in chapter 5)": "малий камінь із діркою посередині (або можете киньте на випадкову дрібничку з таблиці дрібничок у розділі 5)",
    "staff": "посох",
    "three trinkets (each determined by rolling on the Feywild Trinkets table)": "три дрібнички (кожна визначається кидком за таблицею дрібничок Фейвайлду)",
    "tinderbox": "трутниця",
    "token to remember your parents by": "памʼятний знак про ваших батьків",
    "tome of history": "том історії",
    "tool you choose for this background's tool proficiency": "інструмент, який ви обрали для володіння інструментами цієї передісторії",
    "tools of the con of your choice (ten stoppered bottles filled with colored liquid, a set of weighted dice, a deck of marked cards, or a signet ring of an imaginary duke)": "інструменти обраної вами афери (десять закупорених пляшечок із кольоровою рідиною, набір навантажених кісток, колода помічених карт або перстень-печатка вигаданого герцога)",
    "totemic token": "тотемний знак",
    "traveler's clothes": "одяг мандрівника",
    "traveler’s clothes": "одяг мандрівника",
    "trinket recovered from a dig site": "дрібничка, знайдена на розкопках",
    "trophy from an animal you killed": "трофей із убитої вами тварини",
    "trophy taken from a fallen enemy (a dagger, broken blade, or piece of a banner)": "трофей, узятий у полеглого ворога (кинджал, зламаний клинок або шматок прапора)",
    "two-person tent": "намет на двох",
    "uniform in the style of your unit and indicative of your rank": "однострій у стилі вашого підрозділу, що вказує на ваше звання",
    "uniform of your company (traveler’s clothes in quality)": "однострій вашого загону (за якістю — одяг мандрівника)",
    "vestments": "церковне облачення",
    "well-loved carpenter's tools": "улюблені столярні інструменти",
    "wine": "вино",
    "winter blanket": "зимова ковдра",
    "wooden case containing a map to a ruin": "деревʼяний футляр із мапою до руїн",
    "writing kit (small pouch with a quill, ink, folded parchment, and a small penknife)": "письмове приладдя (малий гаманець із пером, чорнилом, складеним пергаментом і малим складаним ножем)",
}


def normalise(text: str) -> str:
    return re.sub(r"[’ʼ'`]", "'", text.strip().casefold())


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def main() -> int:
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    lookup = {normalise(key): value for key, value in UK.items()}
    translated: list[dict[str, str]] = []
    missing: list[str] = []
    for row in rows:
        value = lookup.get(normalise(row["phrase_en"]))
        if value is None:
            missing.append(row["phrase_en"])
            continue
        translated.append({"id": row["id"], "text_uk": value})

    if missing:
        print("БЕЗ ПЕРЕКЛАДУ:", *missing, sep="\n  ")
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(translated, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"фраз: {len(translated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

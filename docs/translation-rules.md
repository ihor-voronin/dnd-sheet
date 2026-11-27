# Правила перекладу

Єдине джерело для всього проєкту: екран (`frontend/src`), сервер і експорт
(`backend/src`), переклади корпусу (`content/translations/`). Тест
`backend/tests/api/test_terminology.py` ловить повернення до старих варіантів.

## Як показувати

1. **Усе українською.** Пояснення, підказки, помилки, тексти правил.
2. **Назви ігрових сутностей і ключові терміни — «Українська (English)».**
   Класи, підкласи, види, передісторії, уміння, закляття, риси, предмети,
   вибори класу (бойові стилі, виклики, маневри…), назви розділів правил:
   `Містичний розряд (Eldritch Blast)`, `Чаклун (Warlock)`,
   `Рятівні кидки (Saving Throws)`.
3. **У даних — лише українська.** `name_uk` у `content/translations/` і в
   словниках фронтенду не містить дужок: англійську додає інтерфейс
   (`withEnglish` у `uk.ts`, `with_english` в `uk_text.py`).
4. **Немає перекладу — показуємо оригінал**, а не вигадку. Додати переклад
   у відповідний шар, а не в компонент.
5. Регістр — як у реченні: «Кислотна стріла Мелфа», не «Кислотна Стріла Мелфа».
   Власні імена — з великої.
6. Апостроф — типографський `’` у даних (у коді порівняння нормалізує `’ʼ'`).

## Де живе переклад

| Що | Шар | Звідки бере екран |
|---|---|---|
| Уміння класів і підкласів | `content/translations/classes`, `subclasses` | `name_uk`/`text_uk` з API |
| Види, передісторії | `content/translations/species`, `backgrounds` | з API + `uk.ts` |
| Закляття (назви) | `content/translations/spells/names.json` | `uk-spells.ts` (`scripts/spells_uk_names.py`) |
| Риси (назви) | `content/translations/feats/names.json` | `uk-feats.ts` |
| Вибори класу | `content/translations/optional-features` | `name_uk` з API |
| Предмети | `content/translations/items` | `uk-items.ts` |
| Класи, види, підкласи для експорту | `content/translations/terms` (`scripts/terms_uk_export.py` з `uk.ts`) | — |

## Канонічні терміни

Розбіжності, які вже виправлено в коді (ліворуч — як більше **не** пишемо):

| Було | Канонічно | English |
|---|---|---|
| порятунок, кидок порятунку | рятівний кидок | saving throw |
| Складність, ОС, опір закляттям | КС (клас складності) | DC, spell save DC |
| шкода | урон | damage |
| перешкода | завада | disadvantage |
| фокус (як cantrip) | заговір | cantrip |
| слот | комірка закляття | spell slot |
| хіт-дайс, кубик хітів | кість хітів (мн. кістки хітів) | Hit Die / Hit Dice |
| довгий відпочинок | тривалий відпочинок | long rest |
| втома | виснаження | exhaustion |
| експертність | експертиза | expertise |
| таємні втаємничення | містичні виклики | Eldritch Invocations |
| дар пакту, пакт клинка | дар угоди, угода клинка | Pact Boon, Pact of the Blade |
| прийоми майстра битви | маневри | Maneuvers |
| Пів-ельф, Піврослик, Тіфлінг, Голіаф | Півельф, Напіврослик, Тіфлінґ, Ґоліат | |

## Здібності (ability scores)

| English | Українською |
|---|---|
| Strength | Сила |
| Dexterity | Спритність |
| Constitution | Статура |
| Intelligence | Інтелект |
| Wisdom | Мудрість |
| Charisma | Харизма |

## Основні терміни

| English | Українською |
|---|---|
| ability score | оцінка здібності / характеристика |
| ability check | перевірка здібності |
| saving throw | рятівний кидок (не «порятунок») |
| proficiency / proficient | володіння / володієте |
| proficiency bonus | бонус майстерності |
| skill | навичка |
| tool | інструмент |
| armor / weapon / shield | броня / зброя / щит |
| hit points | хіти |
| temporary hit points | тимчасові хіти |
| damage | урон (не «шкода») |
| resistance / vulnerability / immunity | опір / уразливість / імунітет |
| attack roll | кидок атаки |
| damage roll | кидок урону |
| saving throw DC | КС рятівного кидка |
| difficulty class (DC) | КС (клас складності) |
| advantage / disadvantage | перевага / завада |
| action / bonus action / reaction | дія / бонусна дія / реакція |
| turn / round | хід / раунд |
| initiative | ініціатива |
| speed / walking speed | швидкість / швидкість ходьби |
| feet | футів (скорочення: фт) |
| long rest / short rest | тривалий відпочинок / короткий відпочинок |
| level / character level | рівень / рівень персонажа |
| cantrip / spell / spell slot | заговір / закляття / комірка закляття |
| spellcasting ability | здібність чарування |
| darkvision | темний зір |
| blindsight | сліпий зір |
| tremorsense | чуття вібрацій |
| creature type | тип істоти |
| Humanoid | гуманоїд |
| Fey | фей |
| Fiend | диявол (тип істоти; патрон чаклуна — «Диявол») |
| Celestial | небожитель |
| Construct | конструкт |
| Undead | нежить |
| Ooze | слиз |
| Giant | велетень |
| Beast | звір |
| Plant | рослина |
| Dragon | дракон |
| Elemental | елементаль |
| Monstrosity | монстр |
| Aberration | аберація |
| size: Tiny/Small/Medium/Large | крихітний/малий/середній/великий |
| invisible / hidden | невидимий / схований |
| prone | збитий з ніг |
| frightened | переляканий |
| charmed | зачарований |
| poisoned | отруєний |
| grappled / restrained | схоплений / стриманий |
| incapacitated | недієздатний |
| stunned / paralyzed / blinded / deafened | приголомшений / паралізований / засліплений / оглухлий |
| exhaustion | виснаження |
| concentration | концентрація |
| telepathy / telepathic | телепатія / телепатичний |
| climb / swim / fly speed | швидкість лазіння / плавання / польоту |
| light / heavy armor | легка / важка броня |
| finesse / two-handed / versatile | фехтувальна / дворучна / універсальна |
| natural weapon | природна зброя |
| unarmed strike | удар без зброї |
| magic missile | магічна стріла |
| trance | транс |
| fey ancestry | фейська спадковість |
| shapechanger | перевертень (shapechanger) |
| mimicry | наслідування |
| grapple | схопити |
| shove | штовхнути |
| cover | укриття |
| dim light / bright light / darkness | тьмяне світло / яскраве світло / темрява |
| cantrip known | відомий заговір |

## Назви, які лишаються англійською в дужках

У назві вміння головне слово — українською, оригінал — у дужках (це додає
інтерфейс, у файлі `name_uk` — **лише українська назва**, без дужок):

- Darkvision → Темний зір
- Celestial Resistance → Небесний опір
- Healing Hands → Цілющі руки
- Light Bearer → Носій світла
- Ability Score Increase → Підвищення характеристик
- Age → Вік
- Size → Розмір
- Speed → Швидкість
- Languages → Мови
- Creature Type → Тип істоти
- Alignment → Світогляд
- Hare-Trigger → Заяча реакція
- Leporine Senses → Заячі чуття
- Lucky Footwork → Щасливі ноги
- Rabbit Hop → Заячий стрибок

## Власні назви й транслітерація

- Harengon → харегон; Aasimar → аазімар; Genasi → ґеназі; Shifter → перевертень
  (shifter); Warforged → бойовий кований; Firbolg → фірболґ; Goliath → ґоліат;
  Tabaxi → табаксі; Kenku → кенку; Tortle → черепахолюд; Loxodon → локсодон;
  Grung → ґрунґ; Triton → тритон; Dragonborn → драконороджений;
  Half-Elf → півельф; Half-Orc → піворк; Tiefling → тіфлінґ;
  Dwarf → дворф; Elf → ельф; Halfling → напіврослик; Gnome → гном;
  Mordenkainen → Морденкайнен; Feywild → Фейвайлд; Shadowfell → Тіньовий
  Проміжок; Underdark → Підзем'я; Chaos → Хаос; Mulhorand → Мулгоранд
- Апостроф у тексті — типографський `’` (як у корпусі: «зв’язок»).

## Правила стилю

1. Звертання — на «ви» («ви можете», «ваша швидкість»), не «ти».
2. Зберігай **усі** числа, кубики (`1d6`, `2d4+2`), позначки markdown
   (`*курсив*`, `**жирний**`, `| таблиці |`, `-` списки) без змін.
3. Не додавай і не прибирай змісту: переклад — 1:1, без «покращень».
4. Терміни з таблиці вище — обовʼязкові; новий термін — перекладай
   послідовно в межах файлу.
5. Розмір тексту: абзаци, як в оригіналі (порожній рядок між абзацами).

/** Українські підписи для екранів візарда й листа.
 *
 * Це не переклад контенту книг: назви характеристик, навичок і кроків уже
 * закріплені в глосарії (content/glossary.uk.yml) і в `sheets.domain.labels`,
 * тому тут ті самі слова, щоб екран і PDF не розходились.
 */

export const ABILITY_LABELS: Record<string, string> = {
  str: "Сила",
  dex: "Спритність",
  con: "Статура",
  int: "Інтелект",
  wis: "Мудрість",
  cha: "Харизма",
};

export const ABILITY_SHORT: Record<string, string> = {
  str: "СИЛ",
  dex: "СПР",
  con: "СТА",
  int: "ІНТ",
  wis: "МУД",
  cha: "ХАР",
};

export const SKILL_LABELS: Record<string, string> = {
  athletics: "Атлетика",
  acrobatics: "Акробатика",
  sleight_of_hand: "Спритність рук",
  stealth: "Скритність",
  arcana: "Магія",
  history: "Історія",
  investigation: "Розслідування",
  nature: "Природа",
  religion: "Релігія",
  animal_handling: "Поводження з тваринами",
  insight: "Проникливість",
  medicine: "Медицина",
  perception: "Спостережливість",
  survival: "Виживання",
  deception: "Обман",
  intimidation: "Залякування",
  performance: "Виступ",
  persuasion: "Переконання",
};

export const SKILL_ABILITY: Record<string, string> = {
  athletics: "str",
  acrobatics: "dex",
  sleight_of_hand: "dex",
  stealth: "dex",
  arcana: "int",
  history: "int",
  investigation: "int",
  nature: "int",
  religion: "int",
  animal_handling: "wis",
  insight: "wis",
  medicine: "wis",
  perception: "wis",
  survival: "wis",
  deception: "cha",
  intimidation: "cha",
  performance: "cha",
  persuasion: "cha",
};

export const STEP_LABELS: Record<string, string> = {
  species: "Вид",
  class: "Клас",
  abilities: "Характеристики",
  background: "Передісторія",
  equipment: "Спорядження",
  spells: "Закляття",
};

export const STEP_ORDER = [
  "species",
  "class",
  "abilities",
  "background",
  "equipment",
  "spells",
] as const;

export const SIZE_LABELS: Record<string, string> = {
  tiny: "крихітний",
  small: "малий",
  medium: "середній",
  large: "великий",
  huge: "величезний",
  gargantuan: "гігантський",
};

export const ALIGNMENT_LABELS: Record<string, string> = {
  "lawful good": "законно-добрий",
  "neutral good": "нейтрально-добрий",
  "chaotic good": "хаотично-добрий",
  "lawful neutral": "законно-нейтральний",
  neutral: "нейтральний",
  "chaotic neutral": "хаотично-нейтральний",
  "lawful evil": "законно-злий",
  "neutral evil": "нейтрально-злий",
  "chaotic evil": "хаотично-злий",
};

export const PROFICIENCY_LABELS: Record<string, string> = {
  skill: "навички",
  saving_throw: "кидки порятунку",
  armor: "броня",
  weapon: "зброя",
  tool: "інструменти",
  language: "мови",
};

export const ITEM_KIND_LABELS: Record<string, string> = {
  armor: "броня",
  shield: "щит",
  weapon: "зброя",
  gear: "речі",
  tool: "інструмент",
  pack: "набір",
  magic: "магічне",
};

export const METHOD_LABELS: Record<string, string> = {
  standard_array: "Стандартний набір",
  point_buy: "Розподіл очок",
  rolls: "Кидки 4d6",
  manual: "Вручну",
};

export const ABILITY_GENITIVE: Record<string, string> = {
  str: "Сили",
  dex: "Спритності",
  con: "Статури",
  int: "Інтелекту",
  wis: "Мудрості",
  cha: "Харизми",
};

export function abilityLabel(code: string): string {
  return ABILITY_LABELS[code] ?? code;
}

/** Родовий відмінок для «від Мудрості»: підпис уже з великої літери. */
export function abilityGenitive(code: string): string {
  return ABILITY_GENITIVE[code] ?? abilityLabel(code);
}

export const LANGUAGE_LABELS: Record<string, string> = {
  common: "спільна",
  elvish: "ельфійська",
  dwarvish: "дворфська",
  infernal: "пекельна",
  celestial: "небесна",
  draconic: "драконяча",
  gnomish: "гномівська",
  goblin: "гоблінська",
  halfling: "півросликів",
  orc: "ороча",
  abyssal: "безодні",
  sylvan: "лісова",
  undercommon: "підземна",
  primordial: "первісна",
  giant: "велетнів",
  "deep speech": "глибока мова",
};

export const PROFICIENCY_VALUE_LABELS: Record<string, string> = {
  light: "легка броня",
  medium: "середня броня",
  heavy: "важка броня",
  shield: "щити",
  simple: "проста зброя",
  martial: "воєнна зброя",
};

export const TOOL_LABELS: Record<string, string> = {
  "thieves' tools": "злодійські інструменти",
  "vehicles (land)": "транспорт (наземний)",
  "vehicles (water)": "транспорт (водний)",
  "cartographer's tools": "інструменти картографа",
  "navigator's tools": "інструменти навігатора",
  "smith's tools": "інструменти коваля",
  "tinker's tools": "інструменти майстра",
  "carpenter's tools": "інструменти теслі",
  "mason's tools": "інструменти муляра",
  "jeweler's tools": "інструменти ювеліра",
  "potter's tools": "інструменти гончара",
  "weaver's tools": "інструменти ткача",
  "woodcarver's tools": "інструменти різьбяра",
  "leatherworker's tools": "інструменти кожумʼяки",
  "glassblower's tools": "інструменти склодува",
  "cobbler's tools": "інструменти шевця",
  "alchemist's supplies": "приладдя алхіміка",
  "brewer's supplies": "приладдя пивовара",
  "calligrapher's supplies": "приладдя каліграфа",
  "painter's supplies": "приладдя художника",
  "cook's utensils": "кухонне приладдя",
  "disguise kit": "набір для маскування",
  "forgery kit": "набір для підробок",
  "herbalism kit": "набір травника",
  "poisoner's kit": "набір отруйника",
  "gaming set": "ігровий набір",
  "musical instrument": "музичний інструмент",
};

export const DAMAGE_TYPE_LABELS: Record<string, string> = {
  acid: "кислота",
  bludgeoning: "дробляча",
  cold: "холод",
  fire: "вогонь",
  force: "сила",
  lightning: "блискавка",
  necrotic: "некротична",
  piercing: "колюча",
  poison: "отрута",
  psychic: "психічна",
  radiant: "промениста",
  slashing: "рубляча",
  thunder: "грім",
};

export const SCHOOL_LABELS: Record<string, string> = {
  abjuration: "захисна",
  conjuration: "виклик",
  divination: "віщування",
  enchantment: "чари",
  evocation: "втілення",
  illusion: "ілюзія",
  necromancy: "некромантія",
  transmutation: "перетворення",
};

export function schoolLabel(code: string): string {
  return SCHOOL_LABELS[code] ?? code;
}

export function damageTypeLabel(code: string): string {
  return DAMAGE_TYPE_LABELS[code] ?? code;
}

/** Час, дистанція й тривалість закляття приходять з довідника англійською. */
function unitsLabel(text: string): string {
  return text
    .replace(/\bbonus action\b/gi, "бонусна дія")
    .replace(/\bactions\b/gi, "дії")
    .replace(/\baction\b/gi, "дія")
    .replace(/\breaction\b/gi, "реакція")
    .replace(/\bminutes?\b/gi, "хв.")
    .replace(/\bhours?\b/gi, "год.")
    .replace(/\bseconds?\b/gi, "с")
    .replace(/\brounds?\b/gi, "раунд")
    .replace(/\bfeet\b/gi, "фт")
    .replace(/\bfoot\b/gi, "фт")
    .replace(/\breach\b/gi, "досяжність")
    .replace(/\bmiles?\b/gi, "миля")
    .replace(/\bSelf\b/g, "на себе")
    .replace(/\bTouch\b/g, "дотик")
    .replace(/\bSight\b/g, "видиме")
    .replace(/\bUnlimited\b/g, "без обмежень")
    .replace(/\bInstantaneous\b/g, "миттєво")
    .replace(/\bConcentration\b/g, "концентрація")
    .replace(/\bup to\b/gi, "до")
    .replace(/\bcone\b/gi, "конус")
    .replace(/\bsphere\b/gi, "сфера")
    .replace(/\bcube\b/gi, "куб")
    .replace(/\bcylinder\b/gi, "циліндр")
    .replace(/\bline\b/gi, "лінія")
    .replace(/\bSpecial\b/g, "особлива");
}

/** «1 reaction, which you take…» — на аркуші потрібна лише перша частина. */
export function castingTimeLabel(raw?: string | null): string {
  if (!raw) return "";
  return unitsLabel(raw.split(",")[0].trim());
}

export function rangeLabel(raw?: string | null): string {
  return raw ? unitsLabel(raw.trim()) : "";
}

export function durationLabel(raw?: string | null): string {
  return raw ? unitsLabel(raw.trim()) : "";
}

/** Ключ підкласу з домену («phb-2014/subclass/the-fiend») → людська назва. */
export function subclassLabel(key: string): string {
  const tail = key.split("/").pop() ?? key;
  return tail
    .split(/[-_]/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Людська назва значення володіння: навичка, порятунок, мова або тип броні. */
export function proficiencyValue(kind: string, value: string): string {
  if (kind === "skill") return skillLabel(value);
  if (kind === "saving_throw") return abilityLabel(value);
  if (kind === "language") return LANGUAGE_LABELS[value] ?? value;
  if (kind === "tool") return TOOL_LABELS[value] ?? value;
  return PROFICIENCY_VALUE_LABELS[value] ?? value;
}

export function skillLabel(code: string): string {
  return SKILL_LABELS[code] ?? code;
}

export function modifierLabel(value: number): string {
  return value >= 0 ? `+${value}` : String(value);
}

export function abilityModifier(total: number): number {
  return Math.floor((total - 10) / 2);
}

/** Опис класу для новачка: роль, складність і основні характеристики.
 *
 * Основні характеристики — з розділу «Quick Build» кожного класу (PHB,
 * гл. 3): перша — головна, друга — бажана. `standard` — рекомендований
 * розклад стандартного набору 15/14/13/12/10/8 для кнопки «Розкласти за
 * класом» (порядок: str, dex, con, int, wis, cha).
 */
export interface ClassGuide {
  saves: string[];
  role: string;
  complexity: "простий" | "середній" | "складний";
  primary: string[];
  standard: Record<string, number>;
}

export const CLASS_GUIDE: Record<string, ClassGuide> = {
  barbarian: { saves: ["str","con"], role: "ближній бій, витривалість", complexity: "простий", primary: ["str", "con"],
    standard: { str: 15, dex: 13, con: 14, int: 8, wis: 12, cha: 10 } },
  bard: { saves: ["dex","cha"], role: "підтримка, магія, спілкування", complexity: "середній", primary: ["cha", "dex"],
    standard: { str: 8, dex: 14, con: 13, int: 10, wis: 12, cha: 15 } },
  cleric: { saves: ["wis","cha"], role: "лікування, підтримка, божественна магія", complexity: "середній", primary: ["wis", "con"],
    standard: { str: 13, dex: 10, con: 14, int: 8, wis: 15, cha: 12 } },
  druid: { saves: ["int","wis"], role: "магія природи, перевтілення", complexity: "складний", primary: ["wis", "con"],
    standard: { str: 8, dex: 13, con: 14, int: 12, wis: 15, cha: 10 } },
  fighter: { saves: ["str","con"], role: "ближній або дальній бій, броня", complexity: "простий", primary: ["str", "con"],
    standard: { str: 15, dex: 13, con: 14, int: 8, wis: 12, cha: 10 } },
  monk: { saves: ["str","dex"], role: "рукопашний бій, рухливість", complexity: "середній", primary: ["dex", "wis"],
    standard: { str: 10, dex: 15, con: 13, int: 8, wis: 14, cha: 12 } },
  paladin: { saves: ["wis","cha"], role: "ближній бій, захист, лікування", complexity: "середній", primary: ["str", "cha"],
    standard: { str: 15, dex: 8, con: 13, int: 10, wis: 12, cha: 14 } },
  ranger: { saves: ["str","dex"], role: "дальній бій, розвідка, природа", complexity: "середній", primary: ["dex", "wis"],
    standard: { str: 10, dex: 15, con: 13, int: 8, wis: 14, cha: 12 } },
  rogue: { saves: ["dex","int"], role: "скритність, навички, точні удари", complexity: "простий", primary: ["dex", "int"],
    standard: { str: 8, dex: 15, con: 13, int: 14, wis: 12, cha: 10 } },
  sorcerer: { saves: ["con","cha"], role: "бойова магія, вроджена сила", complexity: "середній", primary: ["cha", "con"],
    standard: { str: 8, dex: 13, con: 14, int: 10, wis: 12, cha: 15 } },
  warlock: { saves: ["wis","cha"], role: "магія пакту, заговори", complexity: "середній", primary: ["cha", "con"],
    standard: { str: 8, dex: 13, con: 14, int: 12, wis: 10, cha: 15 } },
  wizard: { saves: ["int","wis"], role: "найширша магія, контроль", complexity: "складний", primary: ["int", "con"],
    standard: { str: 8, dex: 13, con: 14, int: 15, wis: 12, cha: 10 } },
  artificer: { saves: ["con","int"], role: "винахідник, магічні предмети", complexity: "складний", primary: ["int", "con"],
    standard: { str: 8, dex: 13, con: 14, int: 15, wis: 12, cha: 10 } },
};

export function classGuide(key: string | null | undefined): ClassGuide | undefined {
  if (!key) return undefined;
  const slug = key.toLowerCase().split("/").pop() ?? key;
  return CLASS_GUIDE[slug];
}

/** Світогляд: одне речення, щоб вибір мав сенс. */
export const ALIGNMENT_HINTS: Record<string, string> = {
  "lawful good": "чинить правильно і шанує порядок, обіцянки, закон",
  "neutral good": "робить добро, не привʼязуючись ні до правил, ні до бунту",
  "chaotic good": "робить добро за власним сумлінням, правила — не головне",
  "lawful neutral": "живе за кодексом, традицією чи наказом",
  neutral: "уникає крайнощів, діє за обставинами",
  "chaotic neutral": "цінує свободу понад усе, непередбачуваний",
  "lawful evil": "бере своє методично, в межах власного кодексу",
  "neutral evil": "думає лише про себе, без принципів",
  "chaotic evil": "руйнує і ламає заради власних примх",
};

/** Коди книг, які найчастіше бачить гравець, — людськими назвами. */
export const SOURCE_SHORT: Record<string, string> = {
  "phb-2014": "Книга гравця",
  "basic-rules-2014": "Базові правила",
  "dmg-2014": "Книга майстра",
  tcoe: "Таша",
  xge: "Ксанатар",
  scag: "Узбережжя Мечів",
  egtw: "Ексендрія",
  erftlw: "Еберон",
  ggtr: "Равніка",
  motm: "Мордекайнен (народи)",
  mtof: "Мордекайнен (вороги)",
  vgtm: "Воло",
  ftod: "Скарбниця драконів",
  "ps-amonkhet": "Амонхет",
  "ps-kaladesh": "Каладеш",
  "ps-ixalan": "Іксалан",
  "ps-innistrad": "Іннистрад",
  "ps-zendikar": "Зендікар",
  "ps-dominaria": "Домінарія",
  sacoc: "Стриксгейвен",
  sato: "Спеллджаммер",
  ai: "Acquisitions Inc.",
};

export function sourceLabel(code: string | null | undefined): string {
  if (!code) return "";
  return SOURCE_SHORT[code] ?? code.toUpperCase();
}

/** Ціна наступного +1 у розподілі очок (PHB, p. 13). */
export function nextPointCost(score: number, costs: Record<string, number>): number | null {
  const now = costs[String(score)];
  const next = costs[String(score + 1)];
  if (now === undefined || next === undefined) return null;
  return next - now;
}

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
  point_buy: "Point buy",
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

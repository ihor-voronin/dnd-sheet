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

export function abilityLabel(code: string): string {
  return ABILITY_LABELS[code] ?? code;
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

/** Людська назва значення володіння: навичка, порятунок, мова або тип броні. */
export function proficiencyValue(kind: string, value: string): string {
  if (kind === "skill") return skillLabel(value);
  if (kind === "saving_throw") return abilityLabel(value);
  if (kind === "language") return LANGUAGE_LABELS[value] ?? value;
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

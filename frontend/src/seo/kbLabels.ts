/**
 * Українські назви й підписи для серверних сторінок довідника (`/kb/...`).
 *
 * Сторінки довідника малює бекенд (Jinja), а частина перекладу — назви видів,
 * класів і предметів, підписи навичок, глосарій — живе тут, у словниках
 * застосунку. Щоб не тримати дві копії, збірка (`scripts/export-kb-labels.mjs`)
 * кладе цей обʼєкт у `dist/kb-labels.json`, а бекенд читає його звідти.
 * Ключі словників — як у `uk.ts`: малими літерами, апостроф «'».
 */
import { ITEMS, ITEM_SRD, SPECIES_UK, TERMS } from "../features/character/uk";
import { FEAT_NAMES } from "../features/character/uk-feats";
import { ITEM_NAMES } from "../features/character/uk-items";
import { GLOSSARY } from "../glossary";
import {
  ABILITY_GENITIVE,
  ABILITY_LABELS,
  ABILITY_SHORT,
  CLASS_GUIDE,
  DAMAGE_TYPE_LABELS,
  LANGUAGE_LABELS,
  PROFICIENCY_VALUE_LABELS,
  SCHOOL_LABELS,
  SIZE_LABELS,
  SKILL_LABELS,
  SOURCE_SHORT,
  TOOL_LABELS,
} from "../labels";

export const KB_LABELS_VERSION = 1;

export function kbLabels() {
  return {
    version: KB_LABELS_VERSION,
    abilities: ABILITY_LABELS,
    ability_genitive: ABILITY_GENITIVE,
    ability_short: ABILITY_SHORT,
    skills: SKILL_LABELS,
    sizes: SIZE_LABELS,
    languages: LANGUAGE_LABELS,
    tools: TOOL_LABELS,
    proficiency_values: PROFICIENCY_VALUE_LABELS,
    damage_types: DAMAGE_TYPE_LABELS,
    schools: SCHOOL_LABELS,
    sources: SOURCE_SHORT,
    class_guide: CLASS_GUIDE,
    glossary: GLOSSARY,
    species: SPECIES_UK,
    terms: TERMS,
    // Той самий порядок, що й у `ukItem`: звірене з SRD важить більше за великий словник.
    items: { ...ITEMS, ...ITEM_NAMES, ...ITEM_SRD },
    feats: FEAT_NAMES,
  };
}

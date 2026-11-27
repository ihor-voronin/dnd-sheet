/** Типи відповідей API візарда й листа.
 *
 * Домен спілкується англійськими ключами; тут лише форма, а не правила.
 * `options` кожного кроку — те, з чого гравець обирає, `answers` — те, що вже
 * обрано. Обидві структури приходять у формі, яку приймає `PUT` кроку.
 */

export interface EntryBrief {
  id: string;
  source_id: string;
  category: string;
  name_en: string;
  name_uk: string | null;
  display_name?: string;
  data: Record<string, unknown>;
}

export interface AbilityChoice {
  count: number;
  amount: number;
  from: string[];
}

/** Уміння виду: оригінал книги й переклад, якщо він уже є. */
export interface TraitView {
  name_en: string;
  text: string;
  name_uk?: string;
  text_uk?: string;
}

export interface SpeciesView {
  key: string;
  name_en: string;
  source_id: string;
  subrace_of: string | null;
  size: string;
  speed: number;
  ability_bonuses: Record<string, number>;
  ability_choice: AbilityChoice | null;
  skill_proficiencies: string[];
  skill_any: number;
  weapon_proficiencies: string[];
  tool_proficiencies: string[];
  tools_any: number;
  languages: string[];
  languages_any_standard: number;
  darkvision: number;
  resistances: string[];
  ability_unresolved: boolean;
  shared_cantrips?: string[];
  cantrip_choice?: { from_class: string; count: number } | null;
  granted_spells?: { name: string; level: number; min_level: number }[];
  /** Особливості з книги: назва й текст (мова — `text_lang`). */
  traits?: TraitView[];
  description?: string;
  /** Український переклад опису (порожньо, якщо перекладу ще немає). */
  description_uk?: string;
  /** Мова тексту книги: uk / en / ru. */
  text_lang?: string | null;
  /** Звідки взято текст, якщо власного запису немає (підраса в тексті батька). */
  text_from?: string | null;
  /** Підраса обовʼязкова: без неї вид не має всіх чисел. */
  subspecies_required?: boolean;
  subspecies?: SpeciesView[];
}

export interface GrantedSpellOption {
  name_en: string;
  level: number;
  source: string;
  prepared: boolean;
}

export interface SpellcastingMechanics {
  ability: string;
  progression: string | null;
  prepares: boolean;
}

export interface SubclassGrants {
  prepared: string[];
  expanded: string[];
}

export interface SubclassView {
  id: string;
  name_en: string;
  /** Українська назва підкласу — з шару перекладу (не з TERMS за id). */
  name_uk?: string | null;
  /** Книга, з якої підклас: потрібна, коли назви повторюються (PHB/PSA). */
  source_id?: string;
  grants?: SubclassGrants;
}

export interface ClassView {
  key: string;
  name_en: string;
  hit_die: number;
  saving_throws: string[];
  skill_choices: { count: number; from: string[] }[];
  skill_any: number;
  skill_limit: number;
  skill_options: string[];
  armor_training: string[];
  weapon_training: string[];
  tool_training: string[];
  spellcasting: SpellcastingMechanics | null;
  cantrips_at_level_1: number;
  spells_known_at_level_1: number | null;
  subclass: { title: string; level: number; options: SubclassView[] } | null;
  features: { name_en: string; level: number; name_uk?: string }[];
  /** Опис класу з книги. */
  description?: string;
  /** Опис класу українською — машинна чернетка, оригінал вище. */
  description_uk?: string;
  /** Текст умінь, які клас дає на 1 рівні (і базових розділів книги). */
  feature_texts?: {
    name_en: string;
    level: number;
    text: string;
    name_uk?: string;
    text_uk?: string;
  }[];
}

export interface BackgroundView {
  key: string;
  name_en: string;
  source_id: string;
  skill_proficiencies: string[];
  tool_proficiencies: string[];
  skill_any: number;
  tools_any: number;
  languages_any_standard: number;
  feature_en: string | null;
  /** Власна передісторія: текст пише гравець, правила вибору стандартні. */
  custom?: boolean;
  /** Опис і текст риси з книги. */
  description?: string;
  feature_text?: string;
  /** Український переклад — машинна чернетка, оригінал вище. */
  description_uk?: string | null;
  feature_uk?: string | null;
  feature_text_uk?: string | null;
  /** Спорядження з рядка `Equipment:`; choices — варіанти вибору книги. */
  equipment?: {
    text: string;
    choices: string[];
    text_uk?: string;
    choices_uk?: string[];
  }[];
  money?: { gp?: number };
}

export interface AbilitiesOptions {
  methods: string[];
  standard_array: number[];
  point_buy: {
    budget: number;
    costs: Record<string, number>;
    min: number;
    max: number;
  };
  species_bonuses: Record<string, number>;
  hint?: string;
}

export interface ClassSkillsOption {
  key: string;
  limit: number;
  options: string[];
  any: boolean;
}

export interface SpeciesSkillsOption {
  key: string;
  fixed: string[];
  any: number;
  languages_any: number;
  tools_any: number;
}

export interface BackgroundOptions {
  backgrounds: BackgroundView[];
  alignments: string[];
  class_skills: ClassSkillsOption | null;
  species_skills: SpeciesSkillsOption | null;
}

export interface EquipmentOptions {
  items_url: string;
  hint?: string;
  class?: { key: string; armor_training: string[]; weapon_training: string[] };
}

export interface CastingView {
  class_key: string;
  name_en: string;
  ability: string | null;
  prepares: boolean;
  cantrips_limit: number;
  spells_known_limit: number | null;
  prepared_limit: number | null;
  source: string;
}

export interface SpellsOptions {
  casting: CastingView | null;
  cantrips?: EntryBrief[];
  spells?: EntryBrief[];
  granted?: GrantedSpellOption[];
  expanded?: string[];
  hint?: string;
}

// --- чернетка -------------------------------------------------------------

export interface StepStatus {
  step: string;
  complete: boolean;
  unlocked: boolean;
  optional: boolean;
}

export interface PickPayload {
  kind: string;
  value: string;
  source: { kind: string; key: string };
}

export interface ItemPayload {
  name_en: string;
  kind: string;
  quantity?: number;
  weight_lb?: number;
  equipped?: boolean;
  attuned?: boolean;
  entry_id?: string | null;
  armor_base?: number | null;
  dex_cap?: number | null;
  notes?: string | null;
  damage?: string | null;
}

export interface MoneyPayload {
  pp: number;
  gp: number;
  ep: number;
  sp: number;
  cp: number;
}

export interface SpellPayload {
  name_en: string;
  level: number;
  class_key: string;
  entry_id?: string | null;
  prepared?: boolean;
  always_prepared?: boolean;
}

export interface SheetSpell {
  name_en: string;
  level: number;
  class_key: string | null;
  entry_id: string | null;
  prepared: boolean;
  always_prepared: boolean;
  /** class | species | subclass | feat | fighting-style | invocation */
  source: string;
  /** Власне закляття: у довіднику його немає, текст дав гравець. */
  custom?: boolean;
  /** Як чарується поза класом або що змінює виклик (Болісний розряд). */
  note?: string;
  /** Короткі дані з довідника — для вкладки «Дії». */
  casting_time?: string;
  range?: string;
  duration?: string;
  components?: string;
  concentration?: boolean;
  ritual?: boolean;
  school?: string;
  description?: string;
  at_higher_levels?: string;
  damage?: { dice: string; type: string } | null;
  save?: string | null;
  attack_roll?: boolean;
}

export interface BackgroundDetails {
  key: string;
  name_en: string;
  source_id: string;
  feature_en: string | null;
  feature_text: string;
  description: string;
  equipment: string;
  skills: string[];
  tools: string[];
  languages: string[];
  skill_any: number;
  tools_any: number;
  languages_any: number;
  /** Український переклад — машинна чернетка, оригінал вище. */
  name_uk?: string | null;
  feature_uk?: string | null;
  feature_text_uk?: string | null;
  description_uk?: string | null;
  equipment_uk?: string | null;
}

export interface SheetFeature {
  name_en: string;
  level: number;
  class_key: string;
  class_name: string;
  source?: "class" | "subclass";
  subclass_name?: string | null;
  /** Українська назва підкласу для підпису на листі. */
  subclass_name_uk?: string | null;
  description?: string;
  /** Українські назва й текст правила — з `content/translations/classes/`. */
  name_uk?: string | null;
  text_uk?: string | null;
}

export interface SheetFeatureResource {
  key: string;
  name_en: string;
  /** Українська назва вміння (Rage → Лють), якщо переклад є. */
  name_uk?: string | null;
  class_key: string;
  class_name: string;
  level: number;
  total: number;
  used: number;
  recharge: "short" | "long";
  action: "action" | "bonus" | "reaction" | "other";
}

export interface RestReport {
  kind: "short" | "long";
  hp_before: number;
  hp_after: number;
  temporary: number;
  hit_dice_before: number;
  hit_dice_after: number;
  slots_before: number;
  slots_after: number;
  features_reset: string[];
  exhaustion_before: number;
  exhaustion_after: number;
}

export interface SheetItem {
  name_en: string;
  kind: string;
  quantity: number;
  weight_lb: number;
  equipped: boolean;
  attuned: boolean;
  /** Запис довідника, з якого предмет узяли: звідти ж беремо опис. */
  entry_id?: string | null;
  armor_base: number | null;
  dex_cap: number | null;
  notes: string | null;
  damage: string | null;
}

export interface SpeciesAnswers {
  name: string;
  species_key: string | null;
  subspecies_key: string | null;
  ability_choices: string[];
  /** Правила 2022: +2 і +1 або три +1 (для видів без фіксованих бонусів). */
  ability_spread: Record<string, number>;
  spell_choices: string[];
}

export interface ClassAnswers {
  class_key: string | null;
  subclass_key: string | null;
}

export interface AbilitiesAnswers {
  method: string | null;
  scores: Record<string, number>;
  rolls: number[];
}

export interface CustomBackgroundItem {
  name_en: string;
  quantity: number;
}

export interface CustomBackgroundPayload {
  name: string;
  description: string;
  feature_name: string;
  feature_text: string;
  /** Предмети обрані з каталогу (фільтри й властивості — як в інвентарі). */
  items: CustomBackgroundItem[];
  equipment: string;
  money_gp: number;
}

export interface BackgroundAnswers {
  background_key: string | null;
  custom_background?: CustomBackgroundPayload | null;
  alignment: string | null;
  picks: PickPayload[];
}

export interface EquipmentAnswers {
  items: ItemPayload[];
  money: MoneyPayload;
  submitted: boolean;
}

export interface SpellsAnswers {
  spells: SpellPayload[];
}

export interface DraftAnswers {
  species: SpeciesAnswers;
  class: ClassAnswers;
  abilities: AbilitiesAnswers;
  background: BackgroundAnswers;
  equipment: EquipmentAnswers;
  spells: SpellsAnswers;
}

export interface DraftView {
  id: string;
  revision: number;
  name: string;
  answers: DraftAnswers;
  steps: StepStatus[];
  next_step: string | null;
  ready_to_finish: boolean;
}

export interface StepView<TOptions = unknown> {
  draft: DraftView;
  step: string;
  locked: boolean;
  complete: boolean;
  answers: Record<string, unknown>;
  options: TOptions;
  errors: string[];
}

// --- лист -----------------------------------------------------------------

export interface SheetAbility {
  base: number;
  bonus: number;
  total: number;
  modifier: number;
}

export interface SheetCharacter {
  id: string;
  name: string;
  total_level: number;
  alignment: string | null;
  species: { key: string; name_en: string; subspecies: string | null } | null;
  background: { key: string; name_en: string } | null;
  classes: {
    key: string;
    name_en: string;
    level: number;
    subclass: string | null;
    hit_die: number;
    /** Клас узято всупереч вимогам мультикласу (правило дому). */
    requirements_ignored?: boolean;
  }[];
  /** Що саме обійшли: клас і його вимоги («INT 13»). */
  multiclass_waivers?: { class_key: string; requirements: string[] }[];
  version: number;
}

export interface SheetSpellcasting {
  caster_level: number;
  slots: {
    by_level: Record<string, number>;
    pact: { slots: number; level: number } | null;
    highest_level: number;
  };
  classes: {
    key: string;
    name_en: string;
    ability: string;
    level: number;
    save_dc: number;
    attack_bonus: number;
    cantrips_limit: number;
    spells_known_limit: number | null;
    prepared_limit: number | null;
    prepares: boolean;
    /** Найвищий рівень закляття цього класу на його рівні. */
    max_spell_level: number;
  }[];
}

export interface SheetViewPayload {
  character: SheetCharacter;
  abilities: Record<string, SheetAbility>;
  proficiency_bonus: number;
  saving_throws: Record<string, { value: number; proficient: boolean; disadvantage?: boolean }>;
  /** Броня/щит без володіння: завада на СИЛ/СПР, чарувати не можна. */
  armor_untrained?: string[];
  skills: Record<string, { value: number; proficient: boolean; expertise?: boolean; disadvantage?: boolean }>;
  /** Експертиза: скільки дали рівні, що обрано, з чого можна обрати. */
  expertise?: { slots: number; chosen: string[]; options: string[] };
  /** Бойовий стиль, втаємничення, метамагія, прийоми… (ключ «клас:група»). */
  class_choices?: ClassChoiceGroup[];
  armor_class: { value: number; parts: { label: string; value: number }[]; notes?: string[] };
  /** Риса виду на 1 рівні (варіантна людина, власна лінія); null — вид не дає. */
  species_feat?: {
    chosen: string | null;
    ability: string | null;
    feat_abilities: Record<string, string[]>;
  } | null;
  initiative: number;
  speed: number;
  passive_perception: number;
  passive_investigation?: number;
  passive_insight?: number;
  darkvision: number;
  blindsight?: number;
  resistances: string[];
  hit_points: {
    maximum: number;
    current: number;
    temporary: number;
    bloodied: boolean;
    parts: { label: string; value: number }[];
  };
  hit_dice: Record<string, number>;
  spellcasting: SheetSpellcasting;
  spells: SheetSpell[];
  resources: {
    slots: Record<string, { total: number; used: number }>;
    pact: { total: number; used: number } | null;
    hit_dice: Record<string, { total: number; used: number }>;
  };
  state: {
    death_saves: { successes: number; failures: number };
    inspiration: boolean;
    exhaustion: number;
    overrides: Record<string, number>;
    notes: Record<string, string>;
  };
  overridden: string[];
  features: SheetFeature[];
  /** Вибрані риси з текстом: показуємо разом з уміннями. */
  feat_details?: {
    key: string;
    name_en: string;
    name_uk?: string | null;
    source_id?: string;
    description: string;
  }[];
  feature_resources: SheetFeatureResource[];
  background_details: BackgroundDetails | null;
  attacks: {
    name_en: string;
    attack_bonus: number;
    damage: string;
    range: string;
    ability: string;
    notes: string;
    equipped: boolean;
    /** weapon — зброя з інвентаря; unarmed — удар без зброї й природна зброя; spell — Shillelagh. */
    kind?: "weapon" | "unarmed" | "spell";
  }[];
  attacks_per_action: number;
  proficiencies: { kind: string; value: string; source: { kind: string; key: string } }[];
  carrying: { capacity: number; weight: number };
  inventory: {
    money: Record<string, number>;
    items: SheetItem[];
  };
  modifiers: {
    kind: string;
    value: number;
    key: string | null;
    note: string | null;
    source: { kind: string; key: string };
  }[];
  feats: string[];
  warnings: string[];
}

export interface FinishedCharacter {
  character_id: string;
  sheet: SheetViewPayload;
}

// --- підвищення рівня -----------------------------------------------------

export interface LevelUpSlotRow {
  level: number;
  before: number;
  after: number;
}

export interface LevelUpSubclassOption {
  id: string;
  name_en: string;
  name_uk: string | null;
  /** Усі вміння підкласу з рівнями: що він дає зараз і далі. */
  features: LevelUpSubclassFeature[];
}

export interface LevelUpSubclassFeature {
  name_en: string;
  level: number;
  /** Вміння саме того рівня, який обирають цим підвищенням. */
  new?: boolean;
  name_uk?: string;
  /** Текст правила: оригінал книги (`text`) і переклад, якщо є (`text_uk`). */
  text?: string;
  text_uk?: string;
}

export interface LevelUpSubclass {
  title: string | null;
  level: number;
  required: boolean;
  current: string | null;
  options: LevelUpSubclassOption[];
}

export interface LevelUpLimits {
  cantrips: { before: number; after: number };
  spells_known: { before: number | null; after: number | null };
  prepared: { before: number | null; after: number | null };
}

export interface LevelUpPlan {
  class_key: string;
  class_name: string;
  is_new_class: boolean;
  current_level: number;
  new_level: number;
  total_level_before: number;
  total_level_after: number;
  hit_die: number;
  constitution_modifier: number;
  hp: { average: number; best_roll: number };
  features: { name_en: string; level: number; name_uk?: string; text?: string; text_uk?: string }[];
  subclass: LevelUpSubclass | null;
  subclass_features: {
    name_en: string;
    level?: number;
    description: string;
    name_uk?: string;
    text_uk?: string;
    subclass_name?: string;
  }[];
  asi: { slots: number; taken: number; pending: boolean };
  proficiency_bonus: { before: number; after: number };
  limits: LevelUpLimits;
  slots: LevelUpSlotRow[];
  pact: { before: [number, number] | null; after: [number, number] | null };
  caster_level: { before: number; after: number };
  max_spell_level: number;
  resources_added: { key: string; name_en: string; name_uk?: string }[];
  allowed: boolean;
  blocked_reason: string | null;
  requirements: string[];
  /** Новий клас барда/слідопита/плута дає одну навичку (PHB, p. 164). */
  skill_options?: string[];
  /** Бард при мультикласі: один музичний інструмент. */
  tool_options?: string[];
}

export interface LevelUpView {
  character_id: string;
  name: string;
  version: number;
  total_level: number;
  max_level: number;
  can_level_up: boolean;
  plans: LevelUpPlan[];
  /** Риса → характеристики, одну з яких вона підвищує на 1. */
  feat_abilities?: Record<string, string[]>;
}

export interface LevelUpReport {
  class_key: string;
  class_name: string;
  is_new_class: boolean;
  from_level: number;
  to_level: number;
  total_level_before: number;
  total_level_after: number;
  hp_max_before: number;
  hp_max_after: number;
  hp_current_before: number;
  hp_current_after: number;
  proficiency_bonus_before: number;
  proficiency_bonus_after: number;
  features: string[];
  subclass_key: string | null;
  ability_increases: [string, number][];
  feat_key: string | null;
  slots: LevelUpSlotRow[];
  spells_added: string[];
  resources_added: string[];
  /** Рівень узято без вимог мультикласу — лист це покаже. */
  requirements_ignored: boolean;
  ignored_requirements: string[];
}

export interface ClassSpell {
  id: string;
  name_en: string;
  name_uk: string | null;
  data: Record<string, unknown>;
}

export interface FeatEntry {
  id: string;
  name_en: string;
  name_uk: string | null;
  source_id: string;
}

export type ClassChoiceGroup = {
  key: string;
  class_key: string;
  group: string;
  /** Хто дав вибір, якщо не клас: риса чи бойовий стиль. */
  origin?: { kind: "feat" | "style"; key: string; name_uk: string } | null;
  slots: number;
  chosen: string[];
  options: {
    name_en: string;
    name_uk?: string | null;
    text_en: string;
    text_uk?: string | null;
    prerequisite?: string | null;
    source?: string;
    /** Чого бракує (рівня, дару угоди, закляття); null — доступно. */
    locked?: string | null;
    school?: string | null;
  }[];
};

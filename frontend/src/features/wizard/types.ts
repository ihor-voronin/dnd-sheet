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
  features: { name_en: string; level: number }[];
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
  source: string;
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
}

export interface SheetFeature {
  name_en: string;
  level: number;
  class_key: string;
  class_name: string;
  source?: "class" | "subclass";
  subclass_name?: string | null;
  description?: string;
}

export interface SheetFeatureResource {
  key: string;
  name_en: string;
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

export interface BackgroundAnswers {
  background_key: string | null;
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
  classes: { key: string; name_en: string; level: number; subclass: string | null; hit_die: number }[];
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
  }[];
}

export interface SheetViewPayload {
  character: SheetCharacter;
  abilities: Record<string, SheetAbility>;
  proficiency_bonus: number;
  saving_throws: Record<string, { value: number; proficient: boolean }>;
  skills: Record<string, { value: number; proficient: boolean }>;
  armor_class: { value: number; parts: { label: string; value: number }[] };
  initiative: number;
  speed: number;
  passive_perception: number;
  darkvision: number;
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
  /** Назви вмінь, які цей підклас дає саме на новому рівні. */
  features: string[];
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
  features: { name_en: string; level: number }[];
  subclass: LevelUpSubclass | null;
  subclass_features: { name_en: string; description: string }[];
  asi: { slots: number; taken: number; pending: boolean };
  proficiency_bonus: { before: number; after: number };
  limits: LevelUpLimits;
  slots: LevelUpSlotRow[];
  pact: { before: [number, number] | null; after: [number, number] | null };
  caster_level: { before: number; after: number };
  max_spell_level: number;
  resources_added: { key: string; name_en: string }[];
  allowed: boolean;
  blocked_reason: string | null;
  requirements: string[];
}

export interface LevelUpView {
  character_id: string;
  name: string;
  version: number;
  total_level: number;
  max_level: number;
  can_level_up: boolean;
  plans: LevelUpPlan[];
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

/** Кроки візарда: кожен — форма, що повертає payload для `PUT` кроку.
 *
 * Правила тут не перевіряються: сервер — єдина інстанція. Компонент лише
 * показує, що дозволено (`options`), збирає вибір і показує помилку, яку
 * сервер повернув. Тому кнопка «Далі» ніколи не «вгадує» валідність.
 */

import { useEffect, useRef, useState } from "react";

import {
  ABILITY_SHORT,
  ALIGNMENT_LABELS,
  DAMAGE_TYPE_LABELS,
  ITEM_KIND_LABELS,
  METHOD_LABELS,
  SIZE_LABELS,
  SKILL_LABELS,
  abilityLabel,
  abilityModifier,
  modifierLabel,
  proficiencyValue,
  skillLabel,
  subclassLabel,
} from "../../labels";
import type {
  AbilitiesOptions,
  BackgroundAnswers,
  BackgroundOptions,
  BackgroundView,
  ClassAnswers,
  ClassView,
  EntryBrief,
  EquipmentAnswers,
  ItemPayload,
  MoneyPayload,
  PickPayload,
  SpeciesAnswers,
  SpeciesView,
  SpellsOptions,
  SpellsAnswers,
  SpellPayload,
} from "./types";
import { searchItems } from "../../api";
import type { ItemSearchResult } from "../../api";
import { RuleText } from "../character/panels";
import { bodyFromEntry } from "../character/inventory";
import {
  featureLabel,
  featureText,
  itemLabel,
  speciesLabel,
  spellLabel,
  termLabel,
  ukSubclass,
  withEnglish,
} from "../character/uk";

export interface StepProps<TOptions> {
  answers: Record<string, unknown>;
  options: TOptions;
  busy: boolean;
  onSubmit: (payload: Record<string, unknown>) => void;
}

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"] as const;
const ALL_SKILLS = Object.keys(SKILL_LABELS);

function bonusesText(bonuses: Record<string, number>): string {
  const parts = Object.entries(bonuses)
    .filter(([, amount]) => amount !== 0)
    .map(([ability, amount]) => `${modifierLabel(amount)} ${ABILITY_SHORT[ability] ?? ability}`);
  return parts.length ? parts.join(", ") : "без бонусів";
}

// ---------------------------------------------------------------------------
// 1. вид
// ---------------------------------------------------------------------------

export function SpeciesStep({
  answers,
  options,
  busy,
  onSubmit,
}: StepProps<{ species: SpeciesView[]; class_cantrips?: Record<string, EntryBrief[]> }>) {
  const initial = answers as unknown as SpeciesAnswers;
  const [name, setName] = useState(initial.name ?? "");
  const [speciesKey, setSpeciesKey] = useState(initial.species_key ?? "");
  const [subspeciesKey, setSubspeciesKey] = useState(initial.subspecies_key ?? "");
  const [choices, setChoices] = useState<string[]>(initial.ability_choices ?? []);
  const [spellChoices, setSpellChoices] = useState<string[]>(initial.spell_choices ?? []);
  // Список видів згортається, щойно вид обрано: на його місці — картка виду.
  const [gridOpen, setGridOpen] = useState(!initial.species_key);
  const summaryRef = useRef<HTMLDivElement | null>(null);

  const selected = options.species.find((item) => item.key === speciesKey);
  const children = selected?.subspecies ?? [];
  const previousSubspecies = useRef(subspeciesKey);
  useEffect(() => {
    if (previousSubspecies.current === subspeciesKey) return;
    previousSubspecies.current = subspeciesKey;
    setSpellChoices([]);
  }, [subspeciesKey]);
  const effective = children.find((item) => item.key === subspeciesKey) ?? selected;
  // Підраса обовʼязкова, коли вид віддає їй частину чисел (ельф, дворф…).
  // Сервер перевіряє те саме — тут лише не даємо натиснути «Далі» дарма.
  const subspeciesMissing = Boolean(
    selected?.subspecies_required && children.length && !subspeciesKey,
  );
  const choice = effective?.ability_choice ?? null;
  const cantripChoice = effective?.cantrip_choice ?? null;
  const cantripPool = cantripChoice
    ? options.class_cantrips?.[cantripChoice.from_class] ?? []
    : [];
  const grantedCantrips = effective?.shared_cantrips ?? [];
  const grantedSpells = effective?.granted_spells ?? [];

  // Скидання підрас і вибору — лише коли гравець справді змінив вид,
  // а не коли крок перемальовано з уже збереженою відповіддю.
  const previousSpecies = useRef(speciesKey);
  useEffect(() => {
    if (previousSpecies.current === speciesKey) return;
    previousSpecies.current = speciesKey;
    setSubspeciesKey("");
    setChoices([]);
    setSpellChoices([]);
  }, [speciesKey]);

  function toggleChoice(ability: string) {
    if (!choice) return;
    setChoices((current) => {
      if (current.includes(ability)) return current.filter((item) => item !== ability);
      if (current.length >= choice.count) return current;
      return [...current, ability];
    });
  }

  function pickSpecies(key: string) {
    setSpeciesKey(key);
    setGridOpen(false);
    // Список згортається — інакше око лишається на порожньому місці.
    requestAnimationFrame(() =>
      summaryRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }),
    );
  }

  return (
    <div className="wizard-step">
      <div className="field-row">
        <label className="field">
          <span>Імʼя персонажа</span>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="напр. Дарія Залізний Крок" />
        </label>
      </div>

      {selected ? (
        <div ref={summaryRef}>
          <section className="wizard-block species-card">
            <header className="species-card__head">
              <h3>{speciesLabel(selected.name_en)}</h3>
              <button
                type="button"
                className="link-button"
                onClick={() => setGridOpen((open) => !open)}
              >
                {gridOpen ? "Згорнути список видів" : "Змінити вид"}
              </button>
            </header>

            {children.length ? (
              <div className="species-card__subs">
                <h4>
                  Підраса{selected.subspecies_required ? " (обовʼязково)" : ""}
                </h4>
                <div className="chip-row">
                  {children.map((child) => (
                    <button
                      key={child.key}
                      type="button"
                      className={`chip chip--row ${child.key === subspeciesKey ? "chip--active" : ""}`}
                      aria-label={child.name_en}
                      onClick={() => setSubspeciesKey(child.key)}
                    >
                      <span>{speciesLabel(child.name_en)}</span>
                      <span className="meta">{bonusesText(child.ability_bonuses)}</span>
                    </button>
                  ))}
                </div>
                {subspeciesMissing ? (
                  <p className="hint hint--warn">
                    {selected.name_en}: цей вид дає частину чисел підрасі — оберіть її, інакше
                    персонаж не матиме повних бонусів. Далі без підраси не пустить і сервер.
                  </p>
                ) : null}
              </div>
            ) : null}

            <SpeciesSummary base={selected} effective={effective ?? selected} />
          </section>
        </div>
      ) : (
        <p className="hint">Оберіть вид — і тут зʼявиться все, що він дає.</p>
      )}

      {gridOpen ? (
        <div className="choice-grid species-grid">
          {options.species.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`choice ${item.key === speciesKey ? "choice--active" : ""}`}
              aria-label={item.name_en}
              onClick={() => pickSpecies(item.key)}
            >
              <strong>{speciesLabel(item.name_en)}</strong>
              <span className="choice-meta">
                {SIZE_LABELS[item.size] ?? item.size} · {item.speed} фт
              </span>
              <span className="choice-meta">{bonusesText(item.ability_bonuses)}</span>
              {item.darkvision ? <span className="choice-meta">темний зір {item.darkvision}</span> : null}
              {item.subspecies?.length ? (
                <span className="choice-meta">підраси: {item.subspecies.length}</span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}

      {choice ? (
        <section className="wizard-block">
          <h3>Бонуси на вибір</h3>
          <p className="hint">
            {effective ? speciesLabel(effective.name_en) : ""}: оберіть {choice.count} здібності,
            кожна отримає {modifierLabel(choice.amount)}. Обрано {choices.length} з {choice.count}.
          </p>
          <div className="chip-row">
            {choice.from.map((ability) => (
              <button
                key={ability}
                type="button"
                className={`chip ${choices.includes(ability) ? "chip--active" : ""}`}
                onClick={() => toggleChoice(ability)}
              >
                {abilityLabel(ability)}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {grantedCantrips.length || grantedSpells.length ? (
        <p className="hint">
          {grantedCantrips.length
            ? `Вид дає заговори: ${grantedCantrips.join(", ")}.`
            : ""}
          {grantedSpells.length
            ? ` Уроджені закляття з 1 рівня: ${grantedSpells.map((spell) => spell.name).join(", ")}.`
            : ""}
        </p>
      ) : null}

      {cantripChoice ? (
        <section className="wizard-block">
          <h3>Заговір від виду</h3>
          <p className="hint">
            {effective ? speciesLabel(effective.name_en) : ""}: оберіть {cantripChoice.count} заговір
            зі списку {
              cantripChoice.from_class === "wizard" ? "візарда" : cantripChoice.from_class
            }. Обрано {spellChoices.length} з {cantripChoice.count}.
          </p>
          <div className="chip-row">
            {cantripPool.map((entry) => (
              <button
                key={entry.id}
                type="button"
                className={`chip ${spellChoices.includes(entry.name_en) ? "chip--active" : ""}`}
                onClick={() =>
                  setSpellChoices((current) => {
                    if (current.includes(entry.name_en)) {
                      return current.filter((item) => item !== entry.name_en);
                    }
                    if (cantripChoice.count > 0 && current.length >= cantripChoice.count) {
                      return current;
                    }
                    return [...current, entry.name_en];
                  })
                }
              >
                {entry.name_en}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <button
        type="button"
        className="button button--primary"
        disabled={
          busy ||
          !name.trim() ||
          !speciesKey ||
          subspeciesMissing ||
          Boolean(choice && choices.length !== choice.count) ||
          Boolean(cantripChoice && spellChoices.length !== cantripChoice.count)
        }
        onClick={() =>
          onSubmit({
            name: name.trim(),
            species_key: speciesKey,
            subspecies_key: subspeciesKey || null,
            ability_choices: choices,
            spell_choices: spellChoices,
          })
        }
      >
        Далі: клас
      </button>
    </div>
  );
}

/** Картка виду: підраса, «що дає», «як виглядає» й особливості — згори. */
function SpeciesSummary({ base, effective }: { base: SpeciesView; effective: SpeciesView }) {
  const isSub = effective.key !== base.key;
  const facts = speciesFacts(effective);
  const hasText = Boolean(base.description) || (base.traits?.length ?? 0) > 0;

  return (
    <div className="species-card__body">
      <p className="species-card__facts">
        {SIZE_LABELS[effective.size] ?? effective.size} · {effective.speed} фт ·{" "}
        {bonusesText(effective.ability_bonuses)}
        {facts.length ? ` · ${facts.join(" · ")}` : ""}
      </p>

      {!hasText && !isSub ? (
        <p className="hint hint--warn">
          У корпусі немає тексту цього виду — показано лише числа з правил.
        </p>
      ) : null}

      {base.description ? (
        <details className="reckoning species-description">
          <summary>Як виглядає (з книги)</summary>
          <RuleText text={base.description} />
        </details>
      ) : null}

      {isSub && effective.description ? (
        <details className="reckoning species-description" open>
          <summary>Опис підраси</summary>
          <RuleText text={effective.description} />
        </details>
      ) : null}

      {base.traits?.length ? (
        <TraitList
          title={isSub ? `Спільні особливості: ${speciesLabel(base.name_en)}` : "Особливості"}
          traits={base.traits}
        />
      ) : null}

      {isSub && effective.traits?.length ? (
        <TraitList title="Додає підраса" traits={effective.traits} />
      ) : null}

      {hasText && base.text_lang && base.text_lang !== "uk" ? (
        <p className="hint">
          Текст книги {base.text_lang === "ru" ? "російською" : "англійською"} — українського
          перекладу описів видів у корпусі немає.
        </p>
      ) : null}
    </div>
  );
}

function TraitList({
  title,
  traits,
}: {
  title: string;
  traits: { name_en: string; text: string }[];
}) {
  return (
    <>
      <h4 className="species-card__h4">{title}</h4>
      <ul className="species-traits">
        {traits.map((trait) => (
          <li key={trait.name_en}>
            <details className="reckoning">
              <summary>{trait.name_en}</summary>
              <RuleText text={trait.text} />
            </details>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Числа виду: навички, зброя, мови, опір тощо. */
function speciesFacts(item: SpeciesView): string[] {
  const facts: string[] = [];
  if (item.skill_proficiencies.length) {
    facts.push(
      `навички: ${item.skill_proficiencies.map((skill) => skillLabel(skill)).join(", ")}`,
    );
  }
  if (item.skill_any) facts.push(`навичок на вибір: ${item.skill_any}`);
  if (item.weapon_proficiencies.length) {
    facts.push(`зброя: ${item.weapon_proficiencies.map((weapon) => termLabel(weapon)).join(", ")}`);
  }
  if (item.tool_proficiencies.length) {
    facts.push(`інструменти: ${item.tool_proficiencies.map((tool) => termLabel(tool)).join(", ")}`);
  }
  if (item.tools_any) facts.push(`інструментів на вибір: ${item.tools_any}`);
  if (item.languages.length) {
    facts.push(`мови: ${item.languages.map((language) => termLabel(language)).join(", ")}`);
  }
  if (item.languages_any_standard) {
    facts.push(`мов на вибір: ${item.languages_any_standard}`);
  }
  if (item.darkvision) facts.push(`темний зір: ${item.darkvision} фт`);
  if (item.resistances.length) {
    facts.push(`опір: ${item.resistances.map((damage) => damageLabel(damage)).join(", ")}`);
  }
  if (item.ability_unresolved) {
    facts.push("бонуси характеристик — за правилами 2022 (вільний розподіл)");
  }
  return facts;
}

function damageLabel(value: string): string {
  return DAMAGE_TYPE_LABELS[value] ?? termLabel(value);
}

// ---------------------------------------------------------------------------
// 2. клас
// ---------------------------------------------------------------------------

export function ClassStep({ answers, options, busy, onSubmit }: StepProps<{ classes: ClassView[]; hint?: string }>) {
  const initial = answers as unknown as ClassAnswers;
  const [classKey, setClassKey] = useState(initial.class_key ?? "");
  const [subclassKey, setSubclassKey] = useState(initial.subclass_key ?? "");
  // Список класів згортається після вибору — картка класу стає згори.
  const [gridOpen, setGridOpen] = useState(!initial.class_key);
  const cardRef = useRef<HTMLDivElement | null>(null);

  const selected = options.classes.find((item) => item.key === classKey);
  const needsSubclass = Boolean(
    selected?.subclass && selected.subclass.level === 1 && selected.subclass.options.length,
  );
  // «Knowledge Domain» є і в PHB, і в Plane Shift — однакова назва, різні
  // книги. Показуємо джерело лише тоді, коли назви справді повторюються.
  const repeatedSubclasses = new Set(
    (selected?.subclass?.options ?? [])
      .map((option) => option.name_en)
      .filter((name, index, all) => all.indexOf(name) !== index),
  );

  const previousClass = useRef(classKey);
  useEffect(() => {
    if (previousClass.current === classKey) return;
    previousClass.current = classKey;
    setSubclassKey("");
  }, [classKey]);

  function pickClass(key: string) {
    setClassKey(key);
    setGridOpen(false);
    requestAnimationFrame(() =>
      cardRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }),
    );
  }

  const grants = (() => {
    if (!selected?.subclass || !subclassKey) return null;
    const option = selected.subclass.options.find((item) => item.id === subclassKey);
    if (!option?.grants) return null;
    return option.grants.prepared.length || option.grants.expanded.length ? option.grants : null;
  })();

  return (
    <div className="wizard-step">
      {selected ? (
        <div ref={cardRef}>
          <section className="wizard-block species-card class-card">
            <header className="species-card__head">
              <h3>{termLabel(selected.name_en)}</h3>
              <button
                type="button"
                className="link-button"
                onClick={() => setGridOpen((open) => !open)}
              >
                {gridOpen ? "Згорнути список класів" : "Змінити клас"}
              </button>
            </header>

            {needsSubclass && selected.subclass ? (
              <div className="species-card__subs">
                <h4>
                  {withEnglish(
                    subclassLabel(selected.subclass.title),
                    ukSubclass(selected.subclass.title),
                  )}{" "}
                  — обовʼязково на 1 рівні
                </h4>
                <div className="chip-row">
                  {selected.subclass.options.map((entry) => (
                    <button
                      key={entry.id}
                      type="button"
                      className={`chip ${subclassKey === entry.id ? "chip--active" : ""}`}
                      onClick={() => setSubclassKey(entry.id)}
                    >
                      {withEnglish(subclassLabel(entry.name_en), ukSubclass(entry.id))}
                      {repeatedSubclasses.has(entry.name_en) ? (
                        <span className="meta"> · {entry.source_id}</span>
                      ) : null}
                    </button>
                  ))}
                </div>
                {!subclassKey ? (
                  <p className="hint hint--warn">
                    {termLabel(selected.name_en)} обирає{" "}
                    {withEnglish(
                      subclassLabel(selected.subclass.title),
                      ukSubclass(selected.subclass.title),
                    )}{" "}
                    уже на 1 рівні — без нього «Далі» не пустить.
                  </p>
                ) : null}
              </div>
            ) : null}

            <p className="species-card__facts">{classFacts(selected)}</p>

            {selected.description ? (
              <details className="reckoning species-description" open>
                <summary>Опис класу (з книги)</summary>
                <RuleText text={selected.description} />
              </details>
            ) : (
              <p className="hint hint--warn">
                У корпусі немає тексту цього класу — показано лише числа з правил.
              </p>
            )}

            {selected.feature_texts?.length ? (
              <>
                <h4 className="species-card__h4">Уміння 1 рівня</h4>
                <ul className="species-traits">
                  {selected.feature_texts.map((feature) => (
                    <li key={feature.name_en}>
                      <details className="reckoning" open={feature.name_en === "Hit Points"}>
                        <summary>{featureLabel(feature.name_en)}</summary>
                        <RuleText text={featureText(feature.name_en, feature.text)} />
                      </details>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {selected.features.length ? (
              <details className="reckoning">
                <summary>Усі вміння класу за рівнями</summary>
                <ul className="plain-list">
                  {selected.features.map((feature) => (
                    <li key={`${feature.level}-${feature.name_en}`}>
                      {feature.level} рівень · {featureLabel(feature.name_en)}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}

            {selected.description || selected.feature_texts?.length ? (
              <p className="hint">
                Опис класу — мовою книги (англійською); назви й описи вмінь, які є в
                глосарії, показані українською з англійською в дужках.
              </p>
            ) : null}

            {grants ? (
              <p className="hint">
                {grants.prepared.length
                  ? `Завжди підготовлені: ${grants.prepared.map((name) => spellLabel(name)).join(", ")}.`
                  : ""}
                {grants.expanded.length
                  ? ` Розширений список: ${grants.expanded.map((name) => spellLabel(name)).join(", ")}.`
                  : ""}
              </p>
            ) : null}
          </section>
        </div>
      ) : (
        <p className="hint">Оберіть клас — і тут зʼявиться все, що він дає.</p>
      )}

      {gridOpen ? (
        <div className="choice-grid species-grid">
          {options.classes.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`choice ${item.key === classKey ? "choice--active" : ""}`}
              aria-label={item.name_en}
              onClick={() => pickClass(item.key)}
            >
              <strong>{termLabel(item.name_en)}</strong>
              <span className="choice-meta">
                хіт-дайс d{item.hit_die} · навички: {item.skill_limit} з{" "}
                {item.skill_options.length}
              </span>
              <span className="choice-meta">
                порятунки: {item.saving_throws.map(abilityLabel).join(", ")}
              </span>
              {item.spellcasting ? (
                <span className="choice-meta">
                  чарує від {abilityLabel(item.spellcasting.ability)}
                  {item.spellcasting.prepares ? " · готує" : " · знає"}
                </span>
              ) : (
                <span className="choice-meta">без заклять на 1 рівні</span>
              )}
              {item.subclass ? (
                <span className="choice-meta">
                  {withEnglish(
                    subclassLabel(item.subclass.title),
                    ukSubclass(item.subclass.title),
                  )}{" "}
                  — з {item.subclass.level} рівня
                </span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}

      <button
        type="button"
        className="button button--primary"
        disabled={busy || !classKey || (needsSubclass && !subclassKey)}
        onClick={() => onSubmit({ class_key: classKey, subclass_key: subclassKey || null })}
      >
        Далі: характеристики
      </button>
    </div>
  );
}

/** Що дає передісторія — числами й українськими словами. */
function backgroundFacts(item: BackgroundView): string {
  const parts: string[] = [];
  if (item.skill_proficiencies.length) {
    parts.push(`навички: ${item.skill_proficiencies.map(skillLabel).join(", ")}`);
  }
  if (item.skill_any) parts.push(`навичок на вибір: ${item.skill_any}`);
  if (item.tool_proficiencies.length) {
    parts.push(
      `інструменти: ${item.tool_proficiencies.map((tool) => proficiencyValue("tool", tool)).join(", ")}`,
    );
  }
  if (item.tools_any) parts.push(`інструментів на вибір: ${item.tools_any}`);
  if (item.languages_any_standard) parts.push(`мов на вибір: ${item.languages_any_standard}`);
  if (item.feature_en) parts.push(`риса: ${featureLabel(item.feature_en)}`);
  if (part_money(item)) parts.push(`гроші: ${part_money(item)}`);
  return parts.length ? parts.join(" · ") : "без чисел — лише опис";
}

function part_money(item: BackgroundView): string {
  const gp = item.money?.gp ?? 0;
  return gp ? `${gp} зм` : "";
}

/** Що клас дає на 1 рівні — числами, українськими словами. */
function classFacts(item: ClassView): string {
  const parts: string[] = [`хіт-дайс d${item.hit_die}`];
  parts.push(`порятунки: ${item.saving_throws.map(abilityLabel).join(", ")}`);

  const skills = item.skill_options.map(skillLabel);
  if (skills.length || item.skill_limit) {
    const from = skills.length ? ` — ${skills.join(", ")}` : " — будь-які";
    parts.push(`навички: ${item.skill_limit} зі списку (${skills.length})${from}`);
  }
  if (item.skill_any) parts.push(`+ ${item.skill_any} з будь-яких`);
  if (item.armor_training.length) {
    parts.push(
      `броня: ${item.armor_training.map((value) => proficiencyValue("armor", value)).join(", ")}`,
    );
  }
  if (item.weapon_training.length) {
    parts.push(
      `зброя: ${item.weapon_training.map((value) => proficiencyValue("weapon", value)).join(", ")}`,
    );
  }
  if (item.tool_training.length) {
    parts.push(
      `інструменти: ${item.tool_training.map((value) => proficiencyValue("tool", value)).join(", ")}`,
    );
  }
  if (item.spellcasting) {
    parts.push(
      `чарує від ${abilityLabel(item.spellcasting.ability)} · ${
        item.spellcasting.prepares ? "готує закляття" : "знає закляття"
      }`,
    );
    if (item.cantrips_at_level_1) parts.push(`заговорів на 1 рівні: ${item.cantrips_at_level_1}`);
    if (item.spells_known_at_level_1) {
      parts.push(`заклять на 1 рівні: ${item.spells_known_at_level_1}`);
    }
  } else {
    parts.push("на 1 рівні не чарує");
  }
  return parts.join(" · ");
}

// ---------------------------------------------------------------------------
// 3. характеристики
// ---------------------------------------------------------------------------

export function AbilitiesStep({ answers, options, busy, onSubmit }: StepProps<AbilitiesOptions>) {
  const initial = answers as unknown as { method: string | null; scores: Record<string, number>; rolls: number[] };
  const [method, setMethod] = useState(initial.method ?? "standard_array");
  const [scores, setScores] = useState<Record<string, number>>(() => {
    if (initial.scores && Object.keys(initial.scores).length) return { ...initial.scores };
    // Стандартний набір не має «значень за замовчуванням»: спершу всі шість
    // не призначені, і гравець розкладає числа сам.
    if ((initial.method ?? "standard_array") === "standard_array") {
      return Object.fromEntries(ABILITIES.map((ability) => [ability, 0]));
    }
    return Object.fromEntries(ABILITIES.map((ability) => [ability, 10]));
  });

  const spent = Object.values(scores).reduce(
    (total, score) => total + (options.point_buy.costs[String(score)] ?? 0),
    0,
  );
  const remaining = options.point_buy.budget - spent;
  const bonuses = options.species_bonuses ?? {};

  function setScore(ability: string, value: number) {
    setScores((current) => ({ ...current, [ability]: value }));
  }

  /** Число з набору вже стоїть в іншій характеристиці — його не показуємо. */
  function usedElsewhere(value: number, ability: string): boolean {
    return ABILITIES.some((other) => other !== ability && scores[other] === value);
  }

  function pickMethod(next: string) {
    setMethod(next);
    if (next === "standard_array") {
      const values = Object.values(scores);
      const same =
        values.length === ABILITIES.length &&
        JSON.stringify([...values].sort((left, right) => left - right)) ===
          JSON.stringify([...options.standard_array].sort((left, right) => left - right));
      if (!same) setScores(Object.fromEntries(ABILITIES.map((ability) => [ability, 0])));
    } else {
      // Назад у point buy/ручний: порожні клітинки заповнюємо числом за
      // замовчуванням, інакше в запиті буде нуль і сервер відмовить.
      setScores((current) => {
        const filled: Record<string, number> = {};
        for (const ability of ABILITIES) {
          filled[ability] = current[ability] || (next === "point_buy" ? 8 : 10);
        }
        return filled;
      });
    }
  }

  const unassigned = method === "standard_array" && ABILITIES.filter((a) => !scores[a]).length;
  const invalidStandard =
    method === "standard_array" &&
    JSON.stringify([...Object.values(scores)].sort((left, right) => left - right)) !==
      JSON.stringify([...options.standard_array].sort((left, right) => left - right));
  const invalidPointBuy = method === "point_buy" && remaining < 0;

  return (
    <div className="wizard-step">
      <div className="chip-row">
        {options.methods.map((item) => (
          <button
            key={item}
            type="button"
            className={`chip ${method === item ? "chip--active" : ""}`}
            onClick={() => pickMethod(item)}
          >
            {METHOD_LABELS[item] ?? item}
          </button>
        ))}
      </div>

      {method === "standard_array" ? (
        <p className="hint">
          Набір {options.standard_array.join(", ")} — кожне число рівно один раз: обрані
          значення зникають зі списків інших характеристик.
          {unassigned ? ` Залишилось розставити: ${unassigned}.` : ""}
        </p>
      ) : null}
      {method === "point_buy" ? (
        <p className="hint">
          Бюджет {options.point_buy.budget} очок, оцінки {options.point_buy.min}–{options.point_buy.max}. Лишилось{" "}
          <strong>{remaining}</strong>.
        </p>
      ) : null}
      {method === "rolls" ? (
        <p className="hint">Введіть шість кидків 4d6 без найменшого — куди хочете, туди й ставте.</p>
      ) : null}
      {method === "manual" ? <p className="hint">Ручні значення 3–20, якщо майстер дозволив.</p> : null}

      <table className="ability-table">
        <thead>
          <tr>
            <th>Характеристика</th>
            <th>База</th>
            <th>Вид</th>
            <th>Разом</th>
            <th>Модифікатор</th>
          </tr>
        </thead>
        <tbody>
          {ABILITIES.map((ability) => {
            const base = scores[ability] ?? 10;
            const bonus = bonuses[ability] ?? 0;
            const total = base + bonus;
            // Порожня клітинка стандартного набору — це не «1 з бонусом виду»,
            // тому «Разом» і модифікатор теж порожні.
            const empty = method === "standard_array" && !base;
            return (
              <tr key={ability}>
                <th scope="row">{abilityLabel(ability)}</th>
                <td>
                  {method === "standard_array" ? (
                    <select
                      value={base || ""}
                      onChange={(event) => setScore(ability, Number(event.target.value) || 0)}
                    >
                      <option value="">—</option>
                      {options.standard_array
                        .filter((value) => value === base || !usedElsewhere(value, ability))
                        .map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                    </select>
                  ) : (
                    <input
                      type="number"
                      value={base}
                      min={method === "point_buy" ? options.point_buy.min : 3}
                      max={method === "point_buy" ? options.point_buy.max : 20}
                      onChange={(event) => setScore(ability, Number(event.target.value))}
                    />
                  )}
                </td>
                <td>{bonus ? modifierLabel(bonus) : "—"}</td>
                <td>
                  <strong>{empty ? "—" : total}</strong>
                </td>
                <td>{empty ? "—" : modifierLabel(abilityModifier(total))}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {invalidStandard ? <p className="hint hint--warn">Кожне число набору має бути використане рівно раз.</p> : null}
      {invalidPointBuy ? <p className="hint hint--warn">Витрачено більше, ніж {options.point_buy.budget} очок.</p> : null}

      <button
        type="button"
        className="button button--primary"
        disabled={busy || invalidStandard || invalidPointBuy}
        onClick={() =>
          onSubmit({
            method,
            scores,
            rolls: method === "rolls" ? ABILITIES.map((ability) => scores[ability]) : [],
          })
        }
      >
        Далі: передісторія
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. передісторія й володіння
// ---------------------------------------------------------------------------

export function BackgroundStep({ answers, options, busy, onSubmit }: StepProps<BackgroundOptions>) {
  const initial = answers as unknown as BackgroundAnswers;
  const [backgroundKey, setBackgroundKey] = useState(initial.background_key ?? "");
  const [alignment, setAlignment] = useState(initial.alignment ?? "");
  const picks = initial.picks ?? [];
  const [classSkills, setClassSkills] = useState<string[]>(
    picks.filter((pick) => pick.source.kind === "class").map((pick) => pick.value),
  );
  const [speciesSkills, setSpeciesSkills] = useState<string[]>(
    picks.filter((pick) => pick.source.kind === "species" && pick.kind === "skill").map((pick) => pick.value),
  );
  const [speciesLanguages, setSpeciesLanguages] = useState<string[]>(
    picks.filter((pick) => pick.source.kind === "species" && pick.kind === "language").map((pick) => pick.value),
  );
  const [backgroundLanguages, setBackgroundLanguages] = useState<string[]>(
    picks.filter((pick) => pick.source.kind === "background" && pick.kind === "language").map((pick) => pick.value),
  );

  const background: BackgroundView | undefined = options.backgrounds.find((item) => item.key === backgroundKey);
  const classSkillsOption = options.class_skills;
  const speciesSkillsOption = options.species_skills;

  function toggle(list: string[], value: string, limit: number): string[] {
    if (list.includes(value)) return list.filter((item) => item !== value);
    if (limit > 0 && list.length >= limit) return list;
    return [...list, value];
  }

  const picked: PickPayload[] = [];
  if (classSkillsOption) {
    for (const skill of classSkills) {
      picked.push({ kind: "skill", value: skill, source: { kind: "class", key: classSkillsOption.key } });
    }
  }
  if (speciesSkillsOption) {
    for (const skill of speciesSkills) {
      picked.push({ kind: "skill", value: skill, source: { kind: "species", key: speciesSkillsOption.key } });
    }
    for (const language of speciesLanguages) {
      picked.push({ kind: "language", value: language, source: { kind: "species", key: speciesSkillsOption.key } });
    }
  }
  if (background) {
    for (const language of backgroundLanguages) {
      picked.push({ kind: "language", value: language, source: { kind: "background", key: background.key } });
    }
  }

  const classSkillsReady = !classSkillsOption || classSkills.length === classSkillsOption.limit;
  const speciesSkillsReady =
    !speciesSkillsOption || speciesSkills.length === speciesSkillsOption.any;

  return (
    <div className="wizard-step">
      <label className="field">
        <span>Передісторія</span>
        <select value={backgroundKey} onChange={(event) => setBackgroundKey(event.target.value)}>
          <option value="">— оберіть —</option>
          {options.backgrounds.map((item) => (
            <option key={item.key} value={item.key}>
              {termLabel(item.name_en)}
            </option>
          ))}
        </select>
      </label>

      {background ? (
        <section className="wizard-block species-card">
          <header className="species-card__head">
            <h3>{termLabel(background.name_en)}</h3>
          </header>

          <p className="species-card__facts">{backgroundFacts(background)}</p>

          {background.description ? (
            <details className="reckoning species-description" open>
              <summary>Опис передісторії (з книги)</summary>
              <RuleText text={background.description} />
            </details>
          ) : null}

          {background.feature_en ? (
            <details className="reckoning">
              <summary>
                Риса: {featureLabel(background.feature_en)}
                {background.feature_text ? "" : " (тексту в корпусі немає)"}
              </summary>
              {background.feature_text ? (
                <RuleText text={featureText(background.feature_en, background.feature_text)} />
              ) : null}
            </details>
          ) : null}

          {background.equipment?.length ? (
            <>
              <h4 className="species-card__h4">Спорядження передісторії</h4>
              <ul className="plain-list">
                {background.equipment.map((row) => (
                  <li key={row.text}>
                    {itemLabel(row.text)}
                    {row.choices.length > 1 ? (
                      <span className="meta"> (вибір: {row.choices.map((c) => itemLabel(c)).join(" / ")})</span>
                    ) : null}
                  </li>
                ))}
              </ul>
              <p className="hint">
                Ці предмети додадуться на кроці «Спорядження» — з вибором там, де книга його
                пропонує.
              </p>
            </>
          ) : null}
        </section>
      ) : (
        <p className="hint">Оберіть передісторію — і тут зʼявиться її опис, риса й спорядження.</p>
      )}

      <label className="field">
        <span>Світогляд (необовʼязково)</span>
        <select value={alignment} onChange={(event) => setAlignment(event.target.value)}>
          <option value="">— не обрано —</option>
          {options.alignments.map((item) => (
            <option key={item} value={item}>
              {ALIGNMENT_LABELS[item] ?? item}
            </option>
          ))}
        </select>
      </label>

      {classSkillsOption ? (
        <section className="wizard-block">
          <h3>
            Навички класу — {classSkills.length} з {classSkillsOption.limit}
          </h3>
          <div className="chip-row">
            {(classSkillsOption.any ? ALL_SKILLS : classSkillsOption.options).map((skill) => (
              <button
                key={skill}
                type="button"
                className={`chip ${classSkills.includes(skill) ? "chip--active" : ""}`}
                onClick={() => setClassSkills((list) => toggle(list, skill, classSkillsOption.limit))}
              >
                {skillLabel(skill)}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {speciesSkillsOption && speciesSkillsOption.any > 0 ? (
        <section className="wizard-block">
          <h3>
            Навички виду — {speciesSkills.length} з {speciesSkillsOption.any}
          </h3>
          <div className="chip-row">
            {ALL_SKILLS.map((skill) => (
              <button
                key={skill}
                type="button"
                className={`chip ${speciesSkills.includes(skill) ? "chip--active" : ""}`}
                onClick={() => setSpeciesSkills((list) => toggle(list, skill, speciesSkillsOption.any))}
              >
                {skillLabel(skill)}
              </button>
            ))}
          </div>
          {speciesSkillsOption.fixed.length ? (
            <p className="hint">
              Вид уже дає: {speciesSkillsOption.fixed.map(skillLabel).join(", ")}.
            </p>
          ) : null}
        </section>
      ) : null}

      {speciesSkillsOption && speciesSkillsOption.languages_any > 0 ? (
        <LanguagePicker
          title={`Мови виду (${speciesLanguages.length} з ${speciesSkillsOption.languages_any})`}
          values={speciesLanguages}
          onChange={setSpeciesLanguages}
          limit={speciesSkillsOption.languages_any}
        />
      ) : null}

      {background && background.languages_any_standard > 0 ? (
        <LanguagePicker
          title={`Мови передісторії (${backgroundLanguages.length} з ${background.languages_any_standard})`}
          values={backgroundLanguages}
          onChange={setBackgroundLanguages}
          limit={background.languages_any_standard}
        />
      ) : null}

      {!classSkillsReady ? (
        <p className="hint hint--warn">Клас вимагає рівно {classSkillsOption?.limit} навичок.</p>
      ) : null}
      {!speciesSkillsReady ? (
        <p className="hint hint--warn">Вид вимагає рівно {speciesSkillsOption?.any} навичок.</p>
      ) : null}

      <button
        type="button"
        className="button button--primary"
        disabled={busy || !backgroundKey || !classSkillsReady || !speciesSkillsReady}
        onClick={() =>
          onSubmit({
            background_key: backgroundKey,
            alignment: alignment || null,
            picks: picked,
          })
        }
      >
        Далі: спорядження
      </button>
    </div>
  );
}

function LanguagePicker({
  title,
  values,
  onChange,
  limit,
}: {
  title: string;
  values: string[];
  onChange: (values: string[]) => void;
  limit: number;
}) {
  const [draft, setDraft] = useState("");
  return (
    <section className="wizard-block">
      <h3>{title}</h3>
      <div className="inline-row">
        <input
          value={draft}
          placeholder="напр. elvish"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            const value = draft.trim().toLowerCase();
            if (!value || values.includes(value) || values.length >= limit) return;
            onChange([...values, value]);
            setDraft("");
          }}
        />
        <button
          type="button"
          className="button"
          onClick={() => {
            const value = draft.trim().toLowerCase();
            if (!value || values.includes(value) || values.length >= limit) return;
            onChange([...values, value]);
            setDraft("");
          }}
        >
          Додати
        </button>
      </div>
      <div className="chip-row">
        {values.map((value) => (
          <button key={value} type="button" className="chip chip--active" onClick={() => onChange(values.filter((item) => item !== value))}>
            {value} ✕
          </button>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// 5. спорядження
// ---------------------------------------------------------------------------

const EMPTY_MONEY: MoneyPayload = { pp: 0, gp: 0, ep: 0, sp: 0, cp: 0 };

/** Позначка в нотатках: предмет прийшов із передісторії (а не з довідника). */
const BACKGROUND_MARK = "від передісторії";

const COIN_LABELS: Record<string, string> = {
  pp: "пл (платина)",
  gp: "зм (золото)",
  ep: "ел (електрум)",
  sp: "см (срібло)",
  cp: "мд (мідь)",
};

export function EquipmentStep({
  answers,
  options,
  busy,
  onSubmit,
}: StepProps<{
  items_url: string;
  hint?: string;
  class?: { key: string };
  background?: {
    key: string;
    name_en: string;
    equipment: { text: string; choices: string[] }[];
    money: { gp?: number };
  } | null;
}>) {
  const initial = answers as unknown as EquipmentAnswers;
  const [items, setItems] = useState<ItemPayload[]>(initial.items ?? []);
  const [money, setMoney] = useState<MoneyPayload>({ ...EMPTY_MONEY, ...(initial.money ?? {}) });
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ItemSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("gear");
  const [weight, setWeight] = useState(0);
  const [armorBase, setArmorBase] = useState(12);
  const [dexCap, setDexCap] = useState<number | "">("");
  const [equipped, setEquipped] = useState(false);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [bgApplied, setBgApplied] = useState(false);
  const appliedOnce = useRef(false);

  const background = options.background ?? null;

  // Спорядження передісторії додається саме: раніше його треба було вписувати
  // руками, хоч у книзі воно вже є. Позначка в нотатках показує, що предмет
  // прийшов із передісторії, і не дає додати його вдруге.
  useEffect(() => {
    if (!background || appliedOnce.current) return;
    appliedOnce.current = true;
    if (items.some((item) => (item.notes ?? "").startsWith(BACKGROUND_MARK))) {
      setBgApplied(true);
      return;
    }
    void addFromBackground();
  }, []);

  async function resolveItem(text: string, marker: string): Promise<ItemPayload> {
    const found = await searchItems(text, 12)
      .then((payload) => {
        // Пошук підрядковий: на «bone dice» першим іде «Pair of engraved bone
        // dice (Brazen Coalition)». Беремо найкоротшу назву, що містить
        // запит, — це найближче до того, що написано в книзі.
        const wanted = text.toLocaleLowerCase();
        const matches = payload.items.filter((item) =>
          item.name_en.toLocaleLowerCase().includes(wanted),
        );
        const pool = matches.length ? matches : payload.items;
        return [...pool].sort((left, right) => left.name_en.length - right.name_en.length)[0];
      })
      .catch(() => undefined);
    if (!found) {
      return {
        name_en: text,
        kind: "gear",
        quantity: 1,
        weight_lb: 0,
        equipped: false,
        notes: marker,
      };
    }
    const body = bodyFromEntry(found);
    // Якщо в довіднику лише «Pair of engraved bone dice (Brazen Coalition)»,
    // у листі лишаємо назву з книги — вагу й тип беремо з довідника, а
    // посилання на чужий запис прибираємо (назва й запис мають збігатися).
    const tooVerbose = found.name_en.length > text.length + 12;
    return {
      ...body,
      name_en: tooVerbose ? text : body.name_en,
      entry_id: tooVerbose ? null : body.entry_id,
      quantity: 1,
      equipped: false,
      notes: marker,
    };
  }

  async function addFromBackground() {
    if (!background) return;
    const bodies: ItemPayload[] = [];
    for (const [index, row] of background.equipment.entries()) {
      const pick = chosen[row.text] ?? row.text;
      bodies.push(await resolveItem(pick, `${BACKGROUND_MARK}:${index}`));
    }
    setItems((current) => [...current, ...bodies]);
    const gold = background.money?.gp ?? 0;
    if (gold) setMoney((current) => ({ ...current, gp: current.gp + gold }));
    setBgApplied(true);
  }

  /** Зміна варіанта («bone dice» → «deck of cards») замінює вже доданий предмет. */
  async function pickChoice(index: number, value: string) {
    if (!background) return;
    const row = background.equipment[index];
    setChosen((current) => ({ ...current, [row.text]: value }));
    const marker = `${BACKGROUND_MARK}:${index}`;
    const present = items.some((item) => item.notes === marker);
    if (!present) return;
    const body = await resolveItem(value, marker);
    setItems((current) =>
      current.map((item) =>
        item.notes === marker
          ? { ...body, quantity: item.quantity ?? 1, equipped: item.equipped ?? false }
          : item,
      ),
    );
  }

  async function search() {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const payload = await searchItems(query.trim());
      setResults(payload.items);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function addFromCatalog(entry: ItemSearchResult) {
    setItems((current) => [...current, { ...bodyFromEntry(entry), quantity: 1 }]);
  }

  function addItem() {
    if (!name.trim()) return;
    const item: ItemPayload = {
      name_en: name.trim(),
      kind,
      quantity: 1,
      weight_lb: weight,
      equipped,
    };
    if (kind === "armor") {
      item.armor_base = armorBase;
      item.dex_cap = dexCap === "" ? null : dexCap;
    }
    setItems((current) => [...current, item]);
    setName("");
    setWeight(0);
    setEquipped(false);
  }

  function submit() {
    // Позначка «від передісторії:N» потрібна лише в цьому кроці (щоб замінити
    // предмет при зміні варіанта); на листі вона читається як нотатка.
    const cleaned = items.map((item) =>
      (item.notes ?? "").startsWith(BACKGROUND_MARK)
        ? { ...item, notes: BACKGROUND_MARK }
        : item,
    );
    onSubmit({ items: cleaned, money });
  }

  return (
    <div className="wizard-step">
      {background ? (
        <section className="wizard-block species-card">
          <header className="species-card__head">
            <h3>Спорядження передісторії: {termLabel(background.name_en)}</h3>
            {bgApplied ? <span className="meta">додано до інвентаря</span> : null}
          </header>
          <ul className="plain-list">
            {background.equipment.map((row, index) => (
              <li key={row.text}>
                {row.choices.length > 1 ? (
                  <select
                    className="select"
                    value={chosen[row.text] ?? row.text}
                    onChange={(event) => void pickChoice(index, event.target.value)}
                  >
                    {row.choices.map((choice) => (
                      <option key={choice} value={choice}>
                        {itemLabel(choice)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span>{itemLabel(row.text)}</span>
                )}
                <span className="meta"> · з книги</span>
              </li>
            ))}
          </ul>
          {(background.money?.gp ?? 0) > 0 ? (
            <p className="hint">Гроші з передісторії: {background.money?.gp} зм — уже в гаманці.</p>
          ) : null}
          {!bgApplied ? (
            <button type="button" className="button" onClick={() => void addFromBackground()}>
              Додати спорядження передісторії
            </button>
          ) : null}
        </section>
      ) : null}

      <section className="wizard-block">
        <h3>Додати предмет із довідника</h3>
        <div className="inline-row">
          <input
            value={query}
            placeholder="напр. chain mail"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void search();
              }
            }}
          />
          <button type="button" className="button" onClick={() => void search()} disabled={searching}>
            {searching ? "Шукаємо…" : "Знайти"}
          </button>
        </div>
        {results.length ? (
          <div className="chip-row">
            {results.map((entry) => (
              <button
                key={entry.id}
                type="button"
                className="chip"
                onClick={() => addFromCatalog(entry)}
                title="Додати в інвентар"
              >
                + {itemLabel(entry.name_en)}
              </button>
            ))}
          </div>
        ) : null}
        <p className="hint">
          Клік додає предмет у інвентар; вагу, броню й тип взято з довідника.
        </p>
      </section>

      <details className="wizard-block reckoning">
        <summary>Свій предмет (немає в довіднику)</summary>
        <div className="field-row">
          <label className="field">
            <span>Назва</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="field field--small">
            <span>Тип</span>
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {Object.entries(ITEM_KIND_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field field--small">
            <span>Вага, фнт</span>
            <input type="number" value={weight} min={0} onChange={(event) => setWeight(Number(event.target.value))} />
          </label>
          {kind === "armor" ? (
            <>
              <label className="field field--small">
                <span>Базовий КЗ</span>
                <input type="number" value={armorBase} min={10} max={18} onChange={(event) => setArmorBase(Number(event.target.value))} />
              </label>
              <label className="field field--small">
                <span>Межа СПР</span>
                <input
                  type="number"
                  value={dexCap}
                  min={0}
                  placeholder="без межі"
                  onChange={(event) => setDexCap(event.target.value === "" ? "" : Number(event.target.value))}
                />
              </label>
            </>
          ) : null}
          <label className="field field--check">
            <input type="checkbox" checked={equipped} onChange={(event) => setEquipped(event.target.checked)} />
            <span>споряджено</span>
          </label>
        </div>
        <button type="button" className="button" onClick={addItem}>
          Додати предмет
        </button>
      </details>

      {items.length ? (
        <section className="wizard-block">
          <h3>Інвентар — {items.length}</h3>
          <ul className="plain-list">
            {items.map((item, index) => (
              <li key={`${item.name_en}-${index}`}>
                {itemLabel(item.name_en)} · {ITEM_KIND_LABELS[item.kind] ?? item.kind}
                {item.armor_base ? ` · КЗ ${item.armor_base}${item.dex_cap !== null && item.dex_cap !== undefined ? ` (СПР ≤ ${item.dex_cap})` : ""}` : ""}
                {item.weight_lb ? ` · ${item.weight_lb} фнт` : ""}
                {item.equipped ? " · споряджено" : ""}{" "}
                <button type="button" className="link-button" onClick={() => setItems(items.filter((_, position) => position !== index))}>
                  прибрати
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="wizard-block">
        <h3>Гроші</h3>
        <div className="field-row">
          {(["pp", "gp", "ep", "sp", "cp"] as const).map((coin) => (
            <label key={coin} className="field field--small">
              <span>{COIN_LABELS[coin]}</span>
              <input
                type="number"
                min={0}
                value={money[coin]}
                onChange={(event) => setMoney({ ...money, [coin]: Number(event.target.value) })}
              />
            </label>
          ))}
        </div>
      </section>

      {options.hint ? <p className="hint">{options.hint}</p> : null}

      <div className="button-row">
        <button type="button" className="button" disabled={busy} onClick={submit}>
          Пропустити
        </button>
        <button type="button" className="button button--primary" disabled={busy} onClick={submit}>
          Далі: закляття
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 6. закляття
// ---------------------------------------------------------------------------

export function SpellsStep({ answers, options, busy, onSubmit }: StepProps<SpellsOptions>) {
  const initial = answers as unknown as SpellsAnswers;
  const casting = options.casting;
  const [selected, setSelected] = useState<SpellPayload[]>(initial.spells ?? []);

  if (!casting) {
    return (
      <div className="wizard-step">
        <p className="hint">{options.hint ?? "Цей клас не чарує — крок можна пропустити."}</p>
        <button type="button" className="button button--primary" disabled={busy} onClick={() => onSubmit({ spells: [] })}>
          Далі
        </button>
      </div>
    );
  }

  const cantrips = selected.filter((spell) => spell.level === 0);
  const leveled = selected.filter((spell) => spell.level > 0);
  const preparedCount = leveled.filter((spell) => spell.prepared).length;
  const knownLimit = casting.spells_known_limit ?? casting.prepared_limit ?? 99;
  // Локальні копії: у замиканнях нижче TS не бачить, що `casting` уже не null.
  const castingClass = casting.class_key;
  const prepares = casting.prepares;
  const preparedLimit = casting.prepared_limit ?? 0;

  function toggle(entry: { id: string; name_en: string }, level: number, limit: number) {
    setSelected((current) => {
      const exists = current.find((spell) => spell.entry_id === entry.id);
      if (exists) return current.filter((spell) => spell.entry_id !== entry.id);
      const sameLevel = current.filter((spell) => spell.level === level);
      if (level === 0 && sameLevel.length >= limit) return current;
      if (level > 0 && sameLevel.length >= limit) return current;
      return [
        ...current,
        {
          name_en: entry.name_en,
          level,
          class_key: castingClass,
          entry_id: entry.id,
          prepared: prepares ? level > 0 && current.filter((spell) => spell.prepared).length === 0 : false,
        },
      ];
    });
  }

  function setPrepared(entryId: string, prepared: boolean) {
    if (prepared && preparedCount >= preparedLimit) return;
    setSelected((current) =>
      current.map((spell) => (spell.entry_id === entryId ? { ...spell, prepared } : spell)),
    );
  }

  return (
    <div className="wizard-step">
      <p className="hint">
        {casting.name_en}: чарує від {casting.ability ? abilityLabel(casting.ability) : "—"}
        {casting.prepares
          ? ` · готує до ${casting.prepared_limit} заклять`
          : ` · знає до ${casting.spells_known_limit ?? 0}`}
        . Заговорів: {cantrips.length} з {casting.cantrips_limit}.
      </p>

      <section className="wizard-block">
        <h3>Заговори ({cantrips.length} з {casting.cantrips_limit})</h3>
        <div className="spell-grid">
          {(options.cantrips ?? []).map((entry) => {
            const active = selected.some((spell) => spell.entry_id === entry.id);
            return (
              <button
                key={entry.id}
                type="button"
                className={`chip ${active ? "chip--active" : ""}`}
                onClick={() => toggle(entry, 0, casting.cantrips_limit)}
              >
                {entry.name_en}
              </button>
            );
          })}
        </div>
      </section>

      <section className="wizard-block">
        <h3>Закляття 1 рівня ({leveled.length} з {knownLimit})</h3>
        <div className="spell-grid">
          {(options.spells ?? []).map((entry) => {
            const active = selected.find((spell) => spell.entry_id === entry.id);
            return (
              <div key={entry.id} className={`chip chip--row ${active ? "chip--active" : ""}`}>
                <button type="button" className="link-button" onClick={() => toggle(entry, 1, knownLimit)}>
                  {entry.name_en}
                </button>
                {active && casting.prepares ? (
                  <label className="prepared">
                    <input
                      type="checkbox"
                      checked={Boolean(active.prepared)}
                      onChange={(event) => setPrepared(entry.id, event.target.checked)}
                    />
                    підготовлено
                  </label>
                ) : null}
              </div>
            );
          })}
        </div>
        {casting.prepares ? (
          <p className="hint">
            Підготовлено {preparedCount} з {casting.prepared_limit}.
          </p>
        ) : null}
      </section>

      <button type="button" className="button button--primary" disabled={busy} onClick={() => onSubmit({ spells: selected })}>
        Далі
      </button>
    </div>
  );
}



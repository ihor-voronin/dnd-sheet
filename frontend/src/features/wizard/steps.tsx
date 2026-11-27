/** Кроки візарда: кожен — форма, що повертає payload для `PUT` кроку.
 *
 * Правила тут не перевіряються: сервер — єдина інстанція. Компонент лише
 * показує, що дозволено (`options`), збирає вибір і показує помилку, яку
 * сервер повернув. Тому кнопка «Далі» ніколи не «вгадує» валідність.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

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
  TraitView,
} from "./types";
import {
  ALIGNMENT_HINTS,
  LANGUAGE_LABELS,
  TOOL_LABELS,
  SKILL_ABILITY,
  castingTimeLabel,
  classGuide,
  durationLabel,
  nextPointCost,
  rangeLabel,
  schoolLabel,
  sourceLabel,
} from "../../labels";
import { Term } from "../../components/Term";
import { fetchClassFeatures, fetchEntry, searchItems } from "../../api";
import type { ClassFeatureRow } from "../../api";
import { RuleText } from "../character/panels";
import {
  ItemCatalogBrowser,
  ItemFacts,
  bodyFromEntry,
} from "../character/inventory";
import { SubclassBrief } from "./SubclassBrief";
import { PACKS, startingEquipmentFor } from "./startingEquipment";
import type { StartingItem, StartingOption } from "./startingEquipment";
import {
  featureLabel,
  featureText,
  itemLabel,
  speciesLabel,
  spellLabel,
  spellText,
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
// спільні шматки кроків
// ---------------------------------------------------------------------------

/** Рядок «назва — значення»: числа виду, класу, передісторії. */
export type Fact = [label: ReactNode, value: ReactNode];

export function FactList({ facts }: { facts: Fact[] }) {
  if (!facts.length) return null;
  return (
    <dl className="facts">
      {facts.map(([label, value], index) => (
        <div key={index} className="facts__row">
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Пошук у довгому списку (69 видів, 94 передісторії, сотні заклять). */
function SearchField({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="search-field">
      <span className="visually-hidden">{placeholder}</span>
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function matches(needle: string, ...values: (string | null | undefined)[]): boolean {
  const query = needle.trim().toLocaleLowerCase();
  if (!query) return true;
  return values.some((value) => (value ?? "").toLocaleLowerCase().includes(query));
}

/** Закляття у виборі: назва, рівень, школа, час, дальність — і текст на розгортання.
 *
 * Раніше тут був лише чип із назвою, і гравець обирав навмання. Текст
 * читається з довідника лише при розгортанні (у списку класу — сотні заклять).
 */
function SpellOption({
  entry,
  level,
  active,
  disabled,
  onToggle,
  extra,
}: {
  entry: EntryBrief;
  level: number;
  active: boolean;
  disabled: boolean;
  onToggle: () => void;
  extra?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const data = entry.data as Record<string, unknown>;
  const school = typeof data.school === "string" ? schoolLabel(data.school) : "";
  const tags: string[] = [];
  if (data.concentration) tags.push("зосередження");
  if (data.ritual) tags.push("ритуал");

  useEffect(() => {
    if (!open || text !== null) return;
    let alive = true;
    void fetchEntry(entry.id)
      .then((full) => {
        if (alive) setText(full.text_uk || spellText(entry.name_en, full.text_en) || "");
      })
      .catch(() => {
        if (alive) setText("");
      });
    return () => {
      alive = false;
    };
  }, [open, text, entry.id, entry.name_en]);

  return (
    <li className={`option ${active ? "option--active" : ""}`}>
      <div className="option__head">
        <button
          type="button"
          className="option__pick"
          aria-pressed={active}
          disabled={disabled && !active}
          onClick={onToggle}
        >
          <span className="option__mark" aria-hidden="true">{active ? "✓" : ""}</span>
          <span className="option__name">{spellLabel(entry.name_en)}</span>
        </button>
        <span className="option__meta">
          {level === 0 ? "заговір" : `${level} рівень`}
          {school ? ` · ${school}` : ""}
          {data.casting_time ? ` · ${castingTimeLabel(String(data.casting_time))}` : ""}
          {data.range ? ` · ${rangeLabel(String(data.range))}` : ""}
          {data.duration ? ` · ${durationLabel(String(data.duration))}` : ""}
          {tags.length ? ` · ${tags.join(", ")}` : ""}
        </span>
        {extra}
      </div>
      <details className="option__details" onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary>Що робить</summary>
        {text === null ? <p className="meta">Читаємо опис…</p> : null}
        {text ? <RuleText text={text} /> : null}
        {text === "" ? <p className="meta">Опису в довіднику немає — подивіться в книзі.</p> : null}
      </details>
    </li>
  );
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
  // Правила 2022: вид без фіксованих бонусів — гравець розставляє сам.
  const initialSpread = initial.ability_spread ?? {};
  const spreadAbilities = Object.keys(initialSpread);
  const [spreadMode, setSpreadMode] = useState<"two" | "three">(
    spreadAbilities.length === 3 ? "three" : "two",
  );
  const [spreadPicks, setSpreadPicks] = useState<string[]>(
    spreadAbilities.length
      ? spreadAbilities
      : ["str", "dex"],
  );
  // Список видів згортається, щойно вид обрано: на його місці — картка виду.
  const [gridOpen, setGridOpen] = useState(!initial.species_key);
  const [speciesQuery, setSpeciesQuery] = useState("");
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
    // Вільний розподіл належить виду: інший вид — інший вибір.
    setSpreadMode("two");
    setSpreadPicks(["str", "dex"]);
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

  function changeSpreadMode(mode: "two" | "three") {
    setSpreadMode(mode);
    setSpreadPicks((current) => {
      const next = [...current];
      for (const fallback of ["str", "dex", "con"]) {
        if (next.length >= 3) break;
        if (!next.includes(fallback)) next.push(fallback);
      }
      return next;
    });
  }

  /** Розподіл для запиту; `null` — вибір ще недійсний. */
  function spreadPayload(): Record<string, number> | null {
    if (!effective?.ability_unresolved) return null;
    const slots = spreadMode === "three" ? 3 : 2;
    const picks = spreadPicks.slice(0, slots);
    if (picks.length < slots || new Set(picks).size !== picks.length) return null;
    const spread: Record<string, number> = {};
    if (spreadMode === "three") {
      for (const code of picks) spread[code] = 1;
    } else {
      spread[picks[0]] = 2;
      spread[picks[1]] = 1;
    }
    return spread;
  }

  const spreadReady = !effective?.ability_unresolved || spreadPayload() !== null;

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
                    Частину бонусів {speciesLabel(selected.name_en)} дає підраса — оберіть
                    її, щоб перейти далі.
                  </p>
                ) : null}
              </div>
            ) : null}

            {effective?.ability_unresolved ? (
              <div className="species-card__subs">
                <h4>
                  Бонуси характеристик — <Term k="rules_2022">за правилами 2022</Term>
                </h4>
                <p className="hint">
                  Цей вид не має фіксованих бонусів: розподіліть їх самі. Зазвичай +2
                  кладуть в основну характеристику класу.
                </p>
                <div className="chip-row">
                  <button
                    type="button"
                    className={`chip ${spreadMode === "two" ? "chip--active" : ""}`}
                    onClick={() => changeSpreadMode("two")}
                  >
                    +2 і +1
                  </button>
                  <button
                    type="button"
                    className={`chip ${spreadMode === "three" ? "chip--active" : ""}`}
                    onClick={() => changeSpreadMode("three")}
                  >
                    +1, +1 і +1
                  </button>
                </div>
                <div className="levelup-row">
                  {(spreadMode === "three" ? [0, 1, 2] : [0, 1]).map((slot) => (
                    <label key={slot} className="field field--small">
                      <span>{spreadMode === "three" ? "+1" : slot === 0 ? "+2" : "+1"}</span>
                      <select
                        value={spreadPicks[slot]}
                        onChange={(event) =>
                          setSpreadPicks((current) =>
                            current.map((value, index) =>
                              index === slot ? event.target.value : value,
                            ),
                          )
                        }
                      >
                        {ABILITIES.map((code) => (
                          <option
                            key={code}
                            value={code}
                            disabled={
                              code !== spreadPicks[slot] &&
                              spreadPicks
                                .slice(0, spreadMode === "three" ? 3 : 2)
                                .includes(code)
                            }
                          >
                            {abilityLabel(code)}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
                {!spreadReady ? (
                  <p className="hint hint--warn">
                    Оберіть {spreadMode === "three" ? "три різні характеристики по +1" : "дві різні характеристики: +2 і +1"}.
                  </p>
                ) : (
                  <p className="hint">
                    Разом +3 до характеристик — ці бонуси додадуться на кроці
                    «Характеристики» й на листі.
                  </p>
                )}
              </div>
            ) : null}

            <SpeciesSummary base={selected} effective={effective ?? selected} />
          </section>
        </div>
      ) : (
        <p className="hint">
          <Term k="species">Вид</Term> — народ вашого героя. Він дає бонуси
          характеристик, швидкість і особливі вміння. Не знаєте, з чого почати —
          людина, ельф, дворф і півросликів підходять будь-якому класу.
        </p>
      )}

      {gridOpen ? (
        <SearchField
          value={speciesQuery}
          onChange={setSpeciesQuery}
          placeholder="Пошук виду: «ельф», «tiefling»…"
        />
      ) : null}

      {gridOpen ? (
        <div className="choice-grid species-grid">
          {options.species
            .filter((item) => matches(speciesQuery, item.name_en, speciesLabel(item.name_en)))
            .map((item) => (
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
              {item.source_id && item.source_id !== "phb-2014" ? (
                <span className="choice-meta choice-meta--source">{sourceLabel(item.source_id)}</span>
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
            ? `Вид дає заговори: ${grantedCantrips.map(spellLabel).join(", ")} — вони не рахуються в ліміт класу.`
            : ""}
          {grantedSpells.length
            ? ` Уроджені закляття з 1 рівня: ${grantedSpells.map((spell) => spellLabel(spell.name)).join(", ")}.`
            : ""}
        </p>
      ) : null}

      {cantripChoice ? (
        <section className="wizard-block">
          <h3>Заговір від виду</h3>
          <p className="hint">
            {effective ? speciesLabel(effective.name_en) : ""}: оберіть {cantripChoice.count} заговір
            зі списку {
              cantripChoice.from_class === "wizard" ? "мага" : termLabel(cantripChoice.from_class)
            }. Обрано {spellChoices.length} з {cantripChoice.count}.{" "}
            <Term k="cantrip">Заговір</Term> можна творити скільки завгодно.
          </p>
          <ul className="option-list">
            {cantripPool.map((entry) => (
              <SpellOption
                key={entry.id}
                entry={entry}
                level={0}
                active={spellChoices.includes(entry.name_en)}
                disabled={cantripChoice.count > 0 && spellChoices.length >= cantripChoice.count}
                onToggle={() =>
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
              />
            ))}
          </ul>
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
          !spreadReady ||
          Boolean(choice && choices.length !== choice.count) ||
          Boolean(cantripChoice && spellChoices.length !== cantripChoice.count)
        }
        onClick={() =>
          onSubmit({
            name: name.trim(),
            species_key: speciesKey,
            subspecies_key: subspeciesKey || null,
            ability_choices: choices,
            ability_spread: spreadPayload() ?? {},
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
      <FactList facts={facts} />

      {!hasText && !isSub ? (
        <p className="hint hint--warn">
          У довіднику немає опису цього виду — показано лише числа з правил.
        </p>
      ) : null}

      {base.description ? (
        <details className="reckoning species-description">
          <summary>Як виглядає</summary>
          <RuleText text={base.description_uk || base.description} />
        </details>
      ) : null}

      {isSub && effective.description ? (
        <details className="reckoning species-description" open>
          <summary>Опис підраси</summary>
          <RuleText text={effective.description_uk || effective.description} />
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

      {hasText && !base.description_uk ? (
        <p className="hint">
          Частина тексту ще не перекладена — показано оригінал книги англійською.
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
  traits: TraitView[];
}) {
  return (
    <>
      <h4 className="species-card__h4">{title}</h4>
      <ul className="species-traits">
        {traits.map((trait) => (
          <li key={trait.name_en}>
            <details className="reckoning">
              <summary>
                {trait.name_uk
                  ? withEnglish(trait.name_en, trait.name_uk)
                  : trait.name_en}
              </summary>
              <RuleText text={trait.text_uk || trait.text} />
            </details>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Числа виду: розмір, швидкість, бонуси, навички, мови, опір. */
function speciesFacts(item: SpeciesView): Fact[] {
  const facts: Fact[] = [
    [<Term k="size">Розмір</Term>, SIZE_LABELS[item.size] ?? item.size],
    [<Term k="speed">Швидкість</Term>, `${item.speed} фт (≈ ${Math.round(item.speed * 0.3)} м)`],
    [
      <Term k="ability">Характеристики</Term>,
      item.ability_unresolved ? "розподіляєте самі (+2 і +1 або +1, +1, +1)" : bonusesText(item.ability_bonuses),
    ],
  ];
  if (item.darkvision) facts.push([<Term k="darkvision">Темний зір</Term>, `${item.darkvision} фт`]);
  if (item.skill_proficiencies.length || item.skill_any) {
    const fixed = item.skill_proficiencies.map((skill) => skillLabel(skill)).join(", ");
    const any = item.skill_any ? `${fixed ? " + " : ""}${item.skill_any} на вибір` : "";
    facts.push([<Term k="skill">Навички</Term>, fixed + any]);
  }
  if (item.weapon_proficiencies.length) {
    facts.push(["Зброя", item.weapon_proficiencies.map((weapon) => termLabel(weapon)).join(", ")]);
  }
  if (item.tool_proficiencies.length || item.tools_any) {
    const fixed = item.tool_proficiencies.map((tool) => termLabel(tool)).join(", ");
    const any = item.tools_any ? `${fixed ? " + " : ""}${item.tools_any} на вибір` : "";
    facts.push(["Інструменти", fixed + any]);
  }
  if (item.languages.length || item.languages_any_standard) {
    const fixed = item.languages.map((language) => LANGUAGE_LABELS[language] ?? termLabel(language)).join(", ");
    const any = item.languages_any_standard
      ? `${fixed ? " + " : ""}${item.languages_any_standard} на вибір`
      : "";
    facts.push([<Term k="language">Мови</Term>, fixed + any]);
  }
  if (item.resistances.length) {
    facts.push([
      <Term k="resistance">Опір</Term>,
      item.resistances.map((damage) => damageLabel(damage)).join(", "),
    ]);
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
  // Тексти всіх умінь класу вантажаться окремо — лише коли гравець розгорнув
  // список. У 13 класів це кілька сотень кілобайт, у кроці вони зайві.
  const [allOpen, setAllOpen] = useState(false);
  const [allRows, setAllRows] = useState<ClassFeatureRow[] | "loading" | null>(null);

  const selected = options.classes.find((item) => item.key === classKey);
  // Поки тексти не завантажені — назви й рівні з кроку (без описів).
  const featureRows: ClassFeatureRow[] = Array.isArray(allRows)
    ? allRows
    : (selected?.features ?? []);
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

  // Розгорнули «Усі вміння класу за рівнями» — читаємо тексти (один раз на
  // клас; при зміні класу скидаємо, бо це вже інші вміння).
  useEffect(() => {
    if (!allOpen || !classKey) return;
    let alive = true;
    setAllRows("loading");
    void fetchClassFeatures(classKey)
      .then((payload) => {
        if (alive) setAllRows(payload.features);
      })
      .catch(() => {
        if (alive) setAllRows(null);
      });
    return () => {
      alive = false;
    };
  }, [allOpen, classKey]);

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
                      {withEnglish(subclassLabel(entry.name_en), entry.name_uk ?? ukSubclass(entry.id))}
                      {repeatedSubclasses.has(entry.name_en) ? (
                        <span className="meta"> · {sourceLabel(entry.source_id)}</span>
                      ) : null}
                    </button>
                  ))}
                </div>
                {subclassKey ? (
                  <SubclassBrief subclassKey={subclassKey} highlightLevel={1} />
                ) : null}
                {!subclassKey ? (
                  <p className="hint hint--warn">
                    {termLabel(selected.name_en)} обирає{" "}
                    {withEnglish(
                      subclassLabel(selected.subclass.title),
                      ukSubclass(selected.subclass.title),
                    )}{" "}
                    уже на 1 рівні. <Term k="subclass">Підклас</Term> визначає, які вміння
                    ви отримаєте далі, — оберіть один, щоб продовжити.
                  </p>
                ) : null}
              </div>
            ) : null}

            {classGuide(selected.key) ? (
              <p className="class-card__guide">
                {classGuide(selected.key)?.role} · складність: {classGuide(selected.key)?.complexity}
              </p>
            ) : null}
            <FactList facts={classFacts(selected)} />

            {selected.description ? (
              <details className="reckoning species-description" open>
                <summary>Опис класу</summary>
                <RuleText text={selected.description_uk || selected.description} />
              </details>
            ) : (
              <p className="hint hint--warn">
                У довіднику немає опису цього класу — показано лише числа з правил.
              </p>
            )}

            {selected.feature_texts?.length ? (
              <>
                <h4 className="species-card__h4">Уміння 1 рівня</h4>
                <ul className="species-traits">
                  {selected.feature_texts.map((feature) => (
                    <li key={feature.name_en}>
                      <details className="reckoning" open={feature.name_en === "Hit Points"}>
                        <summary>{featureLabel(feature.name_en, feature.name_uk)}</summary>
                        <RuleText
                          text={featureText(feature.name_en, feature.text, feature.text_uk)}
                        />
                      </details>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {selected.features.length ? (
              <details
                className="reckoning"
                onToggle={(event) => setAllOpen(event.currentTarget.open)}
              >
                <summary>Усі вміння класу за рівнями</summary>
                {allRows === "loading" ? (
                  <p className="meta">Читаємо тексти вмінь…</p>
                ) : null}
                <ul className="plain-list">
                  {(Array.isArray(allRows) ? allRows : featureRows).map((feature) => (
                    <li key={`${feature.level}-${feature.name_en}`}>
                      <details className="reckoning">
                        <summary>
                          {feature.level} рівень ·{" "}
                          {featureLabel(feature.name_en, feature.name_uk)}
                        </summary>
                        {feature.text_uk || feature.text ? (
                          <RuleText text={feature.text_uk || feature.text || ""} />
                        ) : (
                          <p className="hint">
                            Опису цього вміння в довіднику немає — подивіться в книзі
                            гравця, розділ класу.
                          </p>
                        )}
                      </details>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}

            {selected.description || selected.feature_texts?.length ? (
              <p className="hint hint--quiet">
                Переклад — чернетка: числа й кубики звірені з книгою, стиль ще
                вичитується. Оригінальні назви — в дужках.
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
        <p className="hint">
          Клас — головне рішення: він визначає, що ваш герой робить у бою і поза ним.
          Для першої гри найпростіші — воїн, варвар і плут; жрець — якщо хочете
          лікувати й підтримувати.
        </p>
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
              {classGuide(item.key) ? (
                <span className="choice-meta choice-meta--lead">
                  {classGuide(item.key)?.role}
                </span>
              ) : null}
              {classGuide(item.key) ? (
                <span className="choice-meta">
                  складність: {classGuide(item.key)?.complexity} · основне:{" "}
                  {classGuide(item.key)?.primary.map(abilityLabel).join(", ")}
                </span>
              ) : null}
              <span className="choice-meta">
                хіти на 1 рівні: {item.hit_die} + Статура
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

/** Що дає передісторія — назва й значення. */
function backgroundFacts(item: BackgroundView): Fact[] {
  const facts: Fact[] = [];
  if (item.skill_proficiencies.length || item.skill_any) {
    const fixed = item.skill_proficiencies.map(skillLabel).join(", ");
    facts.push([
      <Term k="skill">Навички</Term>,
      fixed + (item.skill_any ? `${fixed ? " + " : ""}${item.skill_any} на вибір` : ""),
    ]);
  }
  if (item.tool_proficiencies.length || item.tools_any) {
    const fixed = item.tool_proficiencies.map((tool) => proficiencyValue("tool", tool)).join(", ");
    facts.push([
      "Інструменти",
      fixed + (item.tools_any ? `${fixed ? " + " : ""}${item.tools_any} на вибір` : ""),
    ]);
  }
  if (item.languages_any_standard) {
    facts.push([<Term k="language">Мови</Term>, `${item.languages_any_standard} на вибір`]);
  }
  if (item.feature_en) {
    facts.push([<Term k="background_feature">Риса</Term>, featureLabel(item.feature_en)]);
  }
  if (part_money(item)) facts.push(["Гроші", part_money(item)]);
  return facts;
}

function part_money(item: BackgroundView): string {
  const gp = item.money?.gp ?? 0;
  return gp ? `${gp} зм` : "";
}

/** Що клас дає на 1 рівні — назва й значення, терміни з поясненням. */
function classFacts(item: ClassView): Fact[] {
  const guide = classGuide(item.key);
  const facts: Fact[] = [];
  if (guide) {
    facts.push([
      <Term k="primary_ability">Основні характеристики</Term>,
      guide.primary.map(abilityLabel).join(", "),
    ]);
  }
  facts.push([
    <Term k="hit_die">Хіт-дайс</Term>,
    `d${item.hit_die} — на 1 рівні ${item.hit_die} + модифікатор Статури хітів`,
  ]);
  facts.push([
    <Term k="saving_throw">Порятунки</Term>,
    item.saving_throws.map(abilityLabel).join(", "),
  ]);
  const skills = item.skill_options.map(skillLabel);
  if (skills.length || item.skill_limit) {
    facts.push([
      <Term k="skill">Навички</Term>,
      `${item.skill_limit} на вибір ${skills.length ? `із: ${skills.join(", ")}` : "з будь-яких"}${
        item.skill_any ? ` + ${item.skill_any} з будь-яких` : ""
      }`,
    ]);
  }
  if (item.armor_training.length) {
    facts.push([
      <Term k="proficiency">Броня</Term>,
      item.armor_training.map((value) => proficiencyValue("armor", value)).join(", "),
    ]);
  } else {
    facts.push([<Term k="proficiency">Броня</Term>, "без броні"]);
  }
  if (item.weapon_training.length) {
    facts.push([
      "Зброя",
      item.weapon_training.map((value) => proficiencyValue("weapon", value)).join(", "),
    ]);
  }
  if (item.tool_training.length) {
    facts.push([
      "Інструменти",
      item.tool_training.map((value) => proficiencyValue("tool", value)).join(", "),
    ]);
  }
  if (item.spellcasting) {
    const mode = item.spellcasting.prepares ? (
      <Term k="prepared_spells">готує закляття</Term>
    ) : (
      <Term k="known_spells">знає закляття</Term>
    );
    facts.push([
      <Term k="spellcasting_ability">Чарування</Term>,
      <>
        від {abilityGenitiveLower(item.spellcasting.ability)}, {mode}
        {item.cantrips_at_level_1 ? `; заговорів на 1 рівні: ${item.cantrips_at_level_1}` : ""}
        {item.spells_known_at_level_1 ? `; заклять: ${item.spells_known_at_level_1}` : ""}
      </>,
    ]);
  } else {
    facts.push(["Чарування", "на 1 рівні не чарує"]);
  }
  return facts;
}

function abilityGenitiveLower(code: string): string {
  const map: Record<string, string> = {
    str: "Сили",
    dex: "Спритності",
    con: "Статури",
    int: "Інтелекту",
    wis: "Мудрості",
    cha: "Харизми",
  };
  return map[code] ?? abilityLabel(code);
}

// ---------------------------------------------------------------------------
// 3. характеристики
// ---------------------------------------------------------------------------

const ABILITY_ROLE: Record<string, string> = {
  str: "атаки й урон у ближньому бою, Атлетика, вантаж",
  dex: "КЗ без важкої броні, ініціатива, дальні й фехтувальні атаки, Скритність",
  con: "хіти на кожному рівні, зосередження на закляттях",
  int: "закляття мага, Магія, Історія, Розслідування",
  wis: "закляття жерця й друїда, Спостережливість, Проникливість",
  cha: "закляття барда, чаклуна, чародія й паладина; переконання й обман",
};

function rollAbility(): number {
  const dice = Array.from({ length: 4 }, () => 1 + Math.floor(Math.random() * 6));
  dice.sort((left, right) => left - right);
  return dice[1] + dice[2] + dice[3];
}

export function AbilitiesStep({
  answers,
  options,
  busy,
  onSubmit,
  classKey,
}: StepProps<AbilitiesOptions> & { classKey?: string | null }) {
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
  const [rolled, setRolled] = useState<number[]>([]);
  const guide = classGuide(classKey);

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
      // Назад у розподіл очок/ручний: порожні клітинки заповнюємо числом за
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

  /** Розклад «як радить книга» — однаковий для набору й розподілу очок (обидва = 27 очок). */
  function applyGuide() {
    if (!guide) return;
    setScores({ ...guide.standard });
  }

  function rollAll() {
    const values = ABILITIES.map(() => rollAbility());
    setRolled(values);
  }

  const unassigned = method === "standard_array" && ABILITIES.filter((a) => !scores[a]).length;
  const invalidStandard =
    method === "standard_array" &&
    JSON.stringify([...Object.values(scores)].sort((left, right) => left - right)) !==
      JSON.stringify([...options.standard_array].sort((left, right) => left - right));
  const invalidPointBuy = method === "point_buy" && remaining < 0;
  const invalidRolls =
    method === "rolls" && ABILITIES.some((ability) => (scores[ability] ?? 0) < 3 || (scores[ability] ?? 0) > 18);

  return (
    <div className="wizard-step">
      <p className="lead">
        Шість <Term k="ability">характеристик</Term> описують героя. До кожного кидка в грі
        додається не саме число, а його <Term k="modifier">модифікатор</Term>.
        {guide ? (
          <>
            {" "}Для вашого класу найважливіші{" "}
            <strong>{guide.primary.map(abilityLabel).join(" і ")}</strong> — туди найбільші числа.
          </>
        ) : null}
      </p>

      <div className="chip-row" role="radiogroup" aria-label="Спосіб визначення">
        {options.methods.map((item) => (
          <button
            key={item}
            type="button"
            role="radio"
            aria-checked={method === item}
            className={`chip ${method === item ? "chip--active" : ""}`}
            onClick={() => pickMethod(item)}
          >
            {METHOD_LABELS[item] ?? item}
          </button>
        ))}
      </div>

      {method === "standard_array" ? (
        <p className="hint">
          <Term k="standard_array">Стандартний набір</Term> {options.standard_array.join(", ")} —
          кожне число рівно один раз; обране зникає зі списків інших характеристик.
          {unassigned ? ` Залишилось розставити: ${unassigned}.` : ""}
        </p>
      ) : null}
      {method === "point_buy" ? (
        <p className="hint">
          <Term k="point_buy">Розподіл очок</Term>: {options.point_buy.budget} очок, кожна
          характеристика від {options.point_buy.min} до {options.point_buy.max}. Лишилось{" "}
          <strong>{remaining}</strong>. Ціна наступного +1 — у колонці «Ще +1».
        </p>
      ) : null}
      {method === "rolls" ? (
        <div className="hint">
          <p>
            <Term k="rolls">Кидки 4d6</Term>: для кожної характеристики киньте чотири кубики d6,
            відкиньте найменший, складіть решту (від 3 до 18). Кидайте за столом або тут.
          </p>
          <div className="inline-row">
            <button type="button" className="button" onClick={rollAll}>
              Кинути шість разів
            </button>
            {rolled.length ? (
              <span>
                Ваші числа: <strong>{rolled.join(", ")}</strong> — впишіть їх у таблицю, куди
                хочете.
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
      {method === "manual" ? (
        <p className="hint">Будь-які числа від 3 до 20 — лише якщо так домовились із майстром.</p>
      ) : null}

      {guide && (method === "standard_array" || method === "point_buy") ? (
        <button type="button" className="button button--quiet" onClick={applyGuide}>
          Розкласти, як радить книга для класу
        </button>
      ) : null}

      <table className="ability-table">
        <thead>
          <tr>
            <th>Характеристика</th>
            <th>База</th>
            <th>Вид</th>
            <th>Разом</th>
            <th>
              <Term k="modifier">Модифікатор</Term>
            </th>
            {method === "point_buy" ? <th>Ще +1</th> : null}
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
            const primary = guide?.primary.includes(ability);
            const save = guide?.saves.includes(ability);
            const cost = nextPointCost(base, options.point_buy.costs);
            const skills = ALL_SKILLS.filter((skill) => SKILL_ABILITY[skill] === ability).map(skillLabel);
            return (
              <tr key={ability} className={primary ? "ability-row--primary" : undefined}>
                <th scope="row">
                  <span className="ability-name">{abilityLabel(ability)}</span>
                  {primary ? <span className="tag tag--key">основна для класу</span> : null}
                  {save ? <span className="tag">порятунок класу</span> : null}
                  <span className="ability-role">
                    {ABILITY_ROLE[ability]}
                    {skills.length ? ` · навички: ${skills.join(", ")}` : ""}
                  </span>
                </th>
                <td>
                  {method === "standard_array" ? (
                    <select
                      aria-label={`${abilityLabel(ability)}: значення`}
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
                      aria-label={`${abilityLabel(ability)}: значення`}
                      value={base}
                      min={method === "point_buy" ? options.point_buy.min : 3}
                      max={method === "point_buy" ? options.point_buy.max : method === "rolls" ? 18 : 20}
                      onChange={(event) => setScore(ability, Number(event.target.value))}
                    />
                  )}
                </td>
                <td>{bonus ? modifierLabel(bonus) : "—"}</td>
                <td>
                  <strong>{empty ? "—" : total}</strong>
                </td>
                <td className="ability-mod">
                  {empty ? "—" : <span className="hex-badge">{modifierLabel(abilityModifier(total))}</span>}
                </td>
                {method === "point_buy" ? (
                  <td className="meta">
                    {cost === null ? "максимум" : `${cost} ${cost === 1 ? "очко" : "очки"}`}
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>

      {invalidStandard && !unassigned ? (
        <p className="hint hint--warn">Кожне число набору має стояти рівно в одній характеристиці.</p>
      ) : null}
      {invalidPointBuy ? (
        <p className="hint hint--warn">
          Витрачено на {-remaining} {-remaining === 1 ? "очко" : "очок"} більше, ніж{" "}
          {options.point_buy.budget}. Зменште одну з характеристик.
        </p>
      ) : null}
      {invalidRolls ? (
        <p className="hint hint--warn">Кидок 4d6 дає від 3 до 18 — виправте числа поза цими межами.</p>
      ) : null}

      <button
        type="button"
        className="button button--primary"
        disabled={busy || invalidStandard || invalidPointBuy || invalidRolls}
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
  // Власна передісторія: текст гравця + стандартні 2 навички / 1 інструмент.
  const customInitial = initial.custom_background ?? null;
  const [customName, setCustomName] = useState(customInitial?.name ?? "");
  const [customDescription, setCustomDescription] = useState(customInitial?.description ?? "");
  const [customFeatureName, setCustomFeatureName] = useState(customInitial?.feature_name ?? "");
  const [customFeatureText, setCustomFeatureText] = useState(customInitial?.feature_text ?? "");
  const [customItems, setCustomItems] = useState<{ name_en: string; quantity: number }[]>(
    customInitial?.items ?? [],
  );
  const [customMoney, setCustomMoney] = useState(customInitial?.money_gp ?? 0);
  const [customSkills, setCustomSkills] = useState<string[]>(
    picks.filter((pick) => pick.source.kind === "background" && pick.kind === "skill").map((pick) => pick.value),
  );
  const [customTools, setCustomTools] = useState<string[]>(
    picks.filter((pick) => pick.source.kind === "background" && pick.kind === "tool").map((pick) => pick.value),
  );

  const background: BackgroundView | undefined = options.backgrounds.find((item) => item.key === backgroundKey);
  const [bgQuery, setBgQuery] = useState("");
  const [bgGridOpen, setBgGridOpen] = useState(!initial.background_key);
  // Навички, які вже є з інших джерел: їх не варто брати вдруге (PHB, p. 125).
  const ownedFromBackground = new Set(background?.custom ? customSkills : background?.skill_proficiencies ?? []);
  const ownedFromSpecies = new Set(options.species_skills?.fixed ?? []);
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
    for (const skill of background.custom ? customSkills : []) {
      picked.push({ kind: "skill", value: skill, source: { kind: "background", key: background.key } });
    }
    for (const tool of background.custom ? customTools : []) {
      picked.push({ kind: "tool", value: tool, source: { kind: "background", key: background.key } });
    }
    for (const language of backgroundLanguages) {
      picked.push({ kind: "language", value: language, source: { kind: "background", key: background.key } });
    }
  }

  const classSkillsReady = !classSkillsOption || classSkills.length === classSkillsOption.limit;
  const speciesSkillsReady =
    !speciesSkillsOption || speciesSkills.length === speciesSkillsOption.any;

  return (
    <div className="wizard-step">
      <p className="lead">
        <Term k="background">Передісторія</Term> — ким герой був до пригод. Вона дає дві
        навички, інструменти або мови, стартові речі й рису для гри поза боєм.
      </p>

      {background ? (
        <section className="wizard-block species-card">
          <header className="species-card__head">
            <h3>{termLabel(background.name_en)}</h3>
            <button
              type="button"
              className="link-button"
              onClick={() => setBgGridOpen((open) => !open)}
            >
              {bgGridOpen ? "Згорнути список" : "Змінити передісторію"}
            </button>
          </header>
          <FactList facts={backgroundFacts(background)} />

          {background.description ? (
            <details className="reckoning species-description" open>
              <summary>Опис передісторії</summary>
              <RuleText text={background.description_uk || background.description} />
            </details>
          ) : null}

          {background.feature_en ? (
            <details className="reckoning">
              <summary>
                <Term k="background_feature">Риса</Term>:{" "}
                {featureLabel(background.feature_en, background.feature_uk)}
                {background.feature_text ? "" : " (опису в довіднику немає)"}
              </summary>
              {background.feature_text ? (
                <RuleText
                  text={featureText(
                    background.feature_en,
                    background.feature_text,
                    background.feature_text_uk,
                  )}
                />
              ) : null}
            </details>
          ) : null}

          {background.equipment?.length ? (
            <>
              <h4 className="species-card__h4">Спорядження передісторії</h4>
              <ul className="plain-list">
                {background.equipment.map((row) => (
                  <li key={row.text}>
                    {row.text_uk || itemLabel(row.text)}
                    {row.choices.length > 1 ? (
                      <span className="meta">
                        {" "}
                        (вибір:{" "}
                        {(row.choices_uk ?? row.choices.map((c) => itemLabel(c))).join(
                          " / ",
                        )}
                        )
                      </span>
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
        <p className="hint">Оберіть передісторію зі списку — тут зʼявиться її опис, риса й спорядження.</p>
      )}

      {bgGridOpen ? (
        <>
          <SearchField
            value={bgQuery}
            onChange={setBgQuery}
            placeholder="Пошук: «солдат», «sage», «атлетика»…"
          />
          <div className="choice-grid species-grid">
            {options.backgrounds
              .filter((item) =>
                matches(
                  bgQuery,
                  item.name_en,
                  termLabel(item.name_en),
                  item.skill_proficiencies.map(skillLabel).join(" "),
                ),
              )
              .map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`choice ${item.key === backgroundKey ? "choice--active" : ""}`}
                  aria-label={item.name_en}
                  onClick={() => {
                    setBackgroundKey(item.key);
                    setBgGridOpen(false);
                  }}
                >
                  <strong>{item.custom ? "Власна передісторія" : termLabel(item.name_en)}</strong>
                  <span className="choice-meta">
                    {item.custom
                      ? "напишіть свою: 2 навички, інструмент, мова"
                      : item.skill_proficiencies.length
                        ? item.skill_proficiencies.map(skillLabel).join(", ")
                        : "навички на вибір"}
                  </span>
                  {item.source_id && item.source_id !== "phb-2014" && !item.custom ? (
                    <span className="choice-meta choice-meta--source">{sourceLabel(item.source_id)}</span>
                  ) : null}
                </button>
              ))}
          </div>
        </>
      ) : null}

      <label className="field">
        <span>
          <Term k="alignment">Світогляд</Term> (необовʼязково)
        </span>
        <select value={alignment} onChange={(event) => setAlignment(event.target.value)}>
          <option value="">— не обрано —</option>
          {options.alignments.map((item) => (
            <option key={item} value={item}>
              {ALIGNMENT_LABELS[item] ?? item}
            </option>
          ))}
        </select>
        {alignment && ALIGNMENT_HINTS[alignment] ? (
          <span className="field__hint">{ALIGNMENT_HINTS[alignment]}</span>
        ) : null}
      </label>

      {classSkillsOption ? (
        <section className="wizard-block">
          <h3>
            <Term k="skill">Навички</Term> класу — {classSkills.length} з {classSkillsOption.limit}
          </h3>
          <p className="hint">
            Навичка додає бонус майстерності (+2) до перевірок. У дужках — характеристика,
            від якої вона залежить: обирайте ті, де у вас високе число.
          </p>
          <div className="chip-row">
            {(classSkillsOption.any ? ALL_SKILLS : classSkillsOption.options).map((skill) => {
              const owned = ownedFromBackground.has(skill) || ownedFromSpecies.has(skill);
              return (
                <button
                  key={skill}
                  type="button"
                  disabled={owned && !classSkills.includes(skill)}
                  title={owned ? "Уже є від передісторії або виду" : undefined}
                  className={`chip ${classSkills.includes(skill) ? "chip--active" : ""}`}
                  onClick={() => setClassSkills((list) => toggle(list, skill, classSkillsOption.limit))}
                >
                  {skillLabel(skill)}{" "}
                  <span className="chip__sub">({ABILITY_SHORT[SKILL_ABILITY[skill]] ?? ""})</span>
                  {owned ? <span className="chip__sub"> · уже є</span> : null}
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      {speciesSkillsOption && speciesSkillsOption.any > 0 ? (
        <section className="wizard-block">
          <h3>
            Навички виду — {speciesSkills.length} з {speciesSkillsOption.any}
          </h3>
          <div className="chip-row">
            {ALL_SKILLS.map((skill) => {
              const owned =
                ownedFromBackground.has(skill) || ownedFromSpecies.has(skill) || classSkills.includes(skill);
              return (
                <button
                  key={skill}
                  type="button"
                  disabled={owned && !speciesSkills.includes(skill)}
                  className={`chip ${speciesSkills.includes(skill) ? "chip--active" : ""}`}
                  onClick={() => setSpeciesSkills((list) => toggle(list, skill, speciesSkillsOption.any))}
                >
                  {skillLabel(skill)}{" "}
                  <span className="chip__sub">({ABILITY_SHORT[SKILL_ABILITY[skill]] ?? ""})</span>
                  {owned ? <span className="chip__sub"> · уже є</span> : null}
                </button>
              );
            })}
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

      {background?.custom ? (
        <section className="wizard-block">
          <h3>Власна передісторія</h3>
          <p className="hint">
            Напишіть свою передісторію: назву, опис, рису й спорядження. Правила
            вибору стандартні — дві навички, один інструмент, одна мова.
          </p>
          <label className="field">
            <span>Назва *</span>
            <input
              value={customName}
              placeholder="напр. Син гільдії ковалів"
              onChange={(event) => setCustomName(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Опис</span>
            <textarea
              rows={4}
              value={customDescription}
              placeholder="Звідки ви, що вас сформувало…"
              onChange={(event) => setCustomDescription(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Назва риси</span>
            <input
              value={customFeatureName}
              placeholder="напр. Звʼязки в гільдії"
              onChange={(event) => setCustomFeatureName(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Що дає риса</span>
            <textarea
              rows={3}
              value={customFeatureText}
              placeholder="напр. Ви можете зупинитися в будь-якій кузні гільдії…"
              onChange={(event) => setCustomFeatureText(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Гроші, зм</span>
            <input
              type="number"
              min={0}
              value={customMoney}
              onChange={(event) => setCustomMoney(Math.max(0, Number(event.target.value) || 0))}
            />
          </label>

          <h4 className="species-card__h4">
            Спорядження передісторії ({customItems.reduce((sum, item) => sum + item.quantity, 0)})
          </h4>
          <p className="hint">
            Той самий каталог, що й на листі: фільтри за типом, магічністю й
            книгою, пошук, у рядку — тип, ціна й вага. Обрані предмети додадуться
            в інвентар.
          </p>
          <ItemCatalogBrowser
            onAdd={async (entry) => {
              setCustomItems((current) => {
                const same = current.findIndex((item) => item.name_en === entry.name_en);
                if (same >= 0) {
                  return current.map((item, index) =>
                    index === same ? { ...item, quantity: item.quantity + 1 } : item,
                  );
                }
                return [...current, { name_en: entry.name_en, quantity: 1 }];
              });
              return true;
            }}
          />
          {customItems.length ? (
            <ul className="plain-list">
              {customItems.map((item) => (
                <li key={item.name_en}>
                  {itemLabel(item.name_en)}
                  {item.quantity > 1 ? <span className="meta"> ×{item.quantity}</span> : null}{" "}
                  <button
                    type="button"
                    className="link-button"
                    onClick={() =>
                      setCustomItems((current) =>
                        current.filter((row) => row.name_en !== item.name_en),
                      )
                    }
                  >
                    прибрати
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">Нічого не обрано — можна додати з каталогу вище.</p>
          )}

          <h4 className="species-card__h4">
            Навички передісторії ({customSkills.length} з 2)
          </h4>
          <div className="chip-row">
            {ALL_SKILLS.map((skill) => (
              <button
                key={skill}
                type="button"
                className={`chip ${customSkills.includes(skill) ? "chip--active" : ""}`}
                onClick={() => setCustomSkills((current) => toggle(current, skill, 2))}
              >
                {skillLabel(skill)}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {background?.custom ? (
        <LanguagePicker
          title={`Інструменти передісторії (${customTools.length} з 1)`}
          values={customTools}
          onChange={setCustomTools}
          limit={1}
          placeholder="напр. злодійські інструменти"
          suggestions={TOOL_LABELS}
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
        <p className="hint hint--warn">
          Оберіть навички класу: потрібно {classSkillsOption?.limit}, обрано {classSkills.length}.
        </p>
      ) : null}
      {!speciesSkillsReady ? (
        <p className="hint hint--warn">
          Оберіть навички від виду: потрібно {speciesSkillsOption?.any}, обрано {speciesSkills.length}.
        </p>
      ) : null}

      {background?.custom && !customName.trim() ? (
        <p className="hint hint--warn">Для власної передісторії потрібна назва.</p>
      ) : null}

      <button
        type="button"
        className="button button--primary"
        disabled={
          busy ||
          !backgroundKey ||
          !classSkillsReady ||
          !speciesSkillsReady ||
          Boolean(background?.custom && !customName.trim())
        }
        onClick={() =>
          onSubmit({
            background_key: backgroundKey,
            alignment: alignment || null,
            picks: picked,
            custom_background: background?.custom
              ? {
                  name: customName.trim(),
                  description: customDescription.trim(),
                  feature_name: customFeatureName.trim(),
                  feature_text: customFeatureText.trim(),
                  items: customItems,
                  equipment: "",
                  money_gp: customMoney,
                }
              : null,
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
  placeholder = "напр. ельфійська",
  suggestions = LANGUAGE_LABELS,
}: {
  title: string;
  values: string[];
  onChange: (values: string[]) => void;
  limit: number;
  placeholder?: string;
  suggestions?: Record<string, string>;
}) {
  const [draft, setDraft] = useState("");
  const listId = useMemo(() => `list-${Math.random().toString(36).slice(2, 8)}`, []);
  /** «ельфійська» → «elvish»: сервер зберігає ключ книги. */
  function normalize(raw: string): string {
    const value = raw.trim().toLowerCase();
    const hit = Object.entries(suggestions).find(([, label]) => label.toLowerCase() === value);
    return hit ? hit[0] : value;
  }
  return (
    <section className="wizard-block">
      <h3>{title}</h3>
      <div className="inline-row">
        <input
          value={draft}
          list={listId}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            const value = normalize(draft);
            if (!value || values.includes(value) || values.length >= limit) return;
            onChange([...values, value]);
            setDraft("");
          }}
        />
        <button
          type="button"
          className="button"
          onClick={() => {
            const value = normalize(draft);
            if (!value || values.includes(value) || values.length >= limit) return;
            onChange([...values, value]);
            setDraft("");
          }}
        >
          Додати
        </button>
      </div>
      <datalist id={listId}>
        {Object.entries(suggestions)
          .filter(([key]) => !values.includes(key))
          .map(([key, label]) => (
            <option key={key} value={label} />
          ))}
      </datalist>
      <div className="chip-row">
        {values.map((value) => (
          <button
            key={value}
            type="button"
            className="chip chip--active"
            aria-label={`Прибрати ${suggestions[value] ?? value}`}
            onClick={() => onChange(values.filter((item) => item !== value))}
          >
            {suggestions[value] ?? value} ✕
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
/** Те саме для стартового спорядження класу. */
const CLASS_MARK = "від класу";

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
  classEquipment,
}: {
  /** Текст «Equipment» з глави класу — стартовий набір, який книга пропонує. */
  classEquipment?: string | null;
} & StepProps<{
  items_url: string;
  hint?: string;
  class?: { key: string; armor_training?: string[]; weapon_training?: string[] };
  background?: {
    key: string;
    name_en: string;
    equipment: {
      text: string;
      choices: string[];
      text_uk?: string;
      choices_uk?: string[];
    }[];
    money: { gp?: number };
  } | null;
}>) {
  const initial = answers as unknown as EquipmentAnswers;
  const [items, setItems] = useState<ItemPayload[]>(initial.items ?? []);
  const [money, setMoney] = useState<MoneyPayload>({ ...EMPTY_MONEY, ...(initial.money ?? {}) });
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
  const noArmorTraining = Boolean(options.class && !(options.class.armor_training ?? []).length);
  const armorWithoutTraining = noArmorTraining && items.some((item) => item.kind === "armor" && item.equipped);

  /** Українські назви предметів передісторії: у книзі це фрази («a trophy
   * taken from a fallen enemy»), яких немає в каталозі, тож словник предметів
   * їх не знає. */
  const backgroundNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const row of options.background?.equipment ?? []) {
      if (row.text_uk) map[row.text] = row.text_uk;
      row.choices.forEach((choice, position) => {
        const translated = row.choices_uk?.[position];
        if (translated) map[choice] = translated;
      });
    }
    return map;
  }, [options.background]);

  // Спорядження передісторії додається саме: раніше його треба було вписувати
  // руками, хоч у книзі воно вже є. Позначка в нотатках показує, що предмет
  // прийшов із передісторії, і не дає додати його вдруге.
  useEffect(() => {
    if (!background || appliedOnce.current) return;
    appliedOnce.current = true;
    // Ознака «вже додано» — не лише нотатка: у старих чернетках нотатки
    // губилися, і повторний вхід у крок додавав те саме спорядження вдруге.
    const names = new Set<string>();
    for (const row of background.equipment) {
      names.add(row.text);
      for (const choice of row.choices) names.add(choice);
    }
    const already = items.some(
      (item) => (item.notes ?? "").startsWith(BACKGROUND_MARK) || names.has(item.name_en),
    );
    if (already) {
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
        // Точна назва — завжди перша: «Leather» не має програти «Leather Cap».
        const exact = payload.items.find(
          (item) => item.name_en.toLocaleLowerCase().replace("’", "'") === wanted.replace("’", "'"),
        );
        if (exact) return exact;
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

  // --- стартове спорядження класу -------------------------------------
  const classRows = startingEquipmentFor(options.class?.key);
  const [classPick, setClassPick] = useState<number[]>(() => (classRows ?? []).map(() => 0));
  const classApplied = items.some((item) => (item.notes ?? "").startsWith(CLASS_MARK));

  /** Предмети одного варіанта: точна назва з довідника або набір як один предмет. */
  async function bodiesFor(option: StartingOption, marker: string): Promise<ItemPayload[]> {
    const bodies: ItemPayload[] = [];
    for (const entry of option.items) {
      if ("any" in entry) continue;
      if ("pack" in entry) {
        const packInfo = PACKS[entry.pack];
        bodies.push({
          name_en: packInfo.name_en,
          kind: "pack",
          quantity: 1,
          weight_lb: packInfo.weight,
          equipped: false,
          notes: `${marker} · вміст: ${packInfo.contents}`,
        });
        continue;
      }
      const body = await resolveItem(entry.name, marker);
      bodies.push({ ...body, quantity: entry.qty ?? 1 });
    }
    return bodies;
  }

  async function addFromClass() {
    if (!classRows) return;
    const bodies: ItemPayload[] = [];
    for (const [index, row] of classRows.entries()) {
      bodies.push(...(await bodiesFor(row[classPick[index]] ?? row[0], `${CLASS_MARK}:${index}`)));
    }
    // Броню класу одразу вдягаємо — інакше КЗ на листі лишиться 10 + СПР.
    let armorWorn = items.some((item) => item.kind === "armor" && item.equipped);
    for (const body of bodies) {
      if (body.kind === "armor" && !armorWorn && body.name_en !== "Shield") {
        body.equipped = true;
        armorWorn = true;
      }
    }
    setItems((current) => [...current, ...bodies]);
  }

  /** Інший варіант рядка після додавання — замінюємо предмети цього рядка. */
  async function pickClassOption(rowIndex: number, optionIndex: number) {
    if (!classRows) return;
    setClassPick((current) => current.map((value, index) => (index === rowIndex ? optionIndex : value)));
    const marker = `${CLASS_MARK}:${rowIndex}`;
    if (!items.some((item) => (item.notes ?? "").startsWith(marker))) return;
    const bodies = await bodiesFor(classRows[rowIndex][optionIndex], marker);
    setItems((current) => [
      ...current.filter((item) => !(item.notes ?? "").startsWith(marker)),
      ...bodies,
    ]);
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
    const cleaned = items.map((item) => {
      const notes = item.notes ?? "";
      if (notes.startsWith(BACKGROUND_MARK)) return { ...item, notes: BACKGROUND_MARK };
      // «від класу:2 · вміст: …» → «від класу · вміст: …»: номер рядка потрібен лише тут.
      if (notes.startsWith(CLASS_MARK)) return { ...item, notes: notes.replace(/^від класу:\d+/, CLASS_MARK) };
      return item;
    });
    onSubmit({ items: cleaned, money });
  }

  return (
    <div className="wizard-step">
      <p className="lead">
        Крок необовʼязковий: предмети можна додати й пізніше на листі. Але без зброї та
        броні герой у першому бою матиме лише кулаки і <Term k="armor_class">КЗ</Term> 10 +
        Спритність.
      </p>

      {classRows ? (
        <section className="wizard-block species-card">
          <header className="species-card__head">
            <h3>Стартове спорядження класу</h3>
            {classApplied ? <span className="meta">додано до інвентаря</span> : null}
          </header>
          <ol className="start-rows">
            {classRows.map((row, rowIndex) => (
              <li key={rowIndex}>
                {row.length > 1 ? (
                  <div className="chip-row" role="radiogroup" aria-label={`Вибір ${rowIndex + 1}`}>
                    {row.map((option, optionIndex) => (
                      <button
                        key={option.label}
                        type="button"
                        role="radio"
                        aria-checked={classPick[rowIndex] === optionIndex}
                        className={`chip ${classPick[rowIndex] === optionIndex ? "chip--active" : ""}`}
                        onClick={() => void pickClassOption(rowIndex, optionIndex)}
                      >
                        ({String.fromCharCode(97 + optionIndex)}) {option.label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <span>{row[0].label}</span>
                )}
                {(row[classPick[rowIndex]] ?? row[0]).items.some((entry: StartingItem) => "any" in entry) ? (
                  <p className="hint">
                    {(row[classPick[rowIndex]] ?? row[0]).items
                      .filter((entry): entry is { any: string } => "any" in entry)
                      .map((entry) => `«${entry.any}» оберіть у каталозі нижче`)
                      .join("; ")}
                    .
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
          {!classApplied ? (
            <button type="button" className="button button--primary" onClick={() => void addFromClass()}>
              Додати спорядження класу
            </button>
          ) : (
            <p className="hint">
              Змінили варіант — предмети цього рядка замінено. Броню вдягнено автоматично.
            </p>
          )}
          <p className="hint">
            Замість набору можна взяти стартове золото — домовтеся з майстром і впишіть суму в
            «Гроші».
          </p>
          {classEquipment ? (
            <details className="reckoning">
              <summary>Текст книги</summary>
              <RuleText text={classEquipment} />
            </details>
          ) : null}
        </section>
      ) : classEquipment ? (
        <section className="wizard-block species-card">
          <header className="species-card__head">
            <h3>Стартове спорядження класу</h3>
          </header>
          <RuleText text={classEquipment} />
          <p className="hint">Додайте ці предмети з каталогу нижче.</p>
        </section>
      ) : null}

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
                    {row.choices.map((choice, position) => (
                      <option key={choice} value={choice}>
                        {row.choices_uk?.[position] ?? itemLabel(choice)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span>{row.text_uk || itemLabel(row.text)}</span>
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
        <ItemCatalogBrowser
          onAdd={async (entry) => {
            setItems((current) => [...current, { ...bodyFromEntry(entry), quantity: 1 }]);
            return true;
          }}
        />
        <p className="hint">
          Ті самі фільтри, що й на листі: тип, магічність, книга, пошук. Клік
          «Додати» бере вагу, броню й тип із довідника.
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
                <span>
                  Базовий <Term k="armor_class">КЗ</Term>
                </span>
                <input type="number" value={armorBase} min={10} max={18} onChange={(event) => setArmorBase(Number(event.target.value))} />
              </label>
              <label className="field field--small">
                <span>
                  <Term k="dex_cap">Межа Спритності</Term>
                </span>
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
                {backgroundNames[item.name_en] ?? itemLabel(item.name_en)} ·{" "}
                {ITEM_KIND_LABELS[item.kind] ?? item.kind}
                {item.armor_base ? ` · КЗ ${item.armor_base}${item.dex_cap !== null && item.dex_cap !== undefined ? ` (СПР ≤ ${item.dex_cap})` : ""}` : ""}
                {item.weight_lb ? ` · ${item.weight_lb} фнт` : ""}
                {item.equipped ? " · споряджено" : ""}{" "}
                <button type="button" className="link-button" onClick={() => setItems(items.filter((_, position) => position !== index))}>
                  прибрати
                </button>
                <ItemFacts
                  nameEn={item.name_en}
                  entryId={item.entry_id ?? null}
                  kind={item.kind}
                  damage={item.damage ?? null}
                  armorBase={item.armor_base ?? null}
                  dexCap={item.dex_cap ?? null}
                  weightLb={item.weight_lb ?? 0}
                />
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

      {armorWithoutTraining ? (
        <p className="hint hint--warn">
          Ваш клас не володіє бронею: у ній герой має заваду на кидки Сили й Спритності і не
          може чарувати (PHB, p. 144). Зніміть позначку «споряджено» або оберіть інший предмет.
        </p>
      ) : null}

      <div className="button-row">
        <button type="button" className="button button--primary" disabled={busy} onClick={submit}>
          {items.length ? "Зберегти й далі" : "Далі без предметів"}
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
  const [query, setQuery] = useState("");

  if (!casting) {
    return (
      <div className="wizard-step">
        <p className="lead">
          {options.hint ?? "Ваш клас на 1 рівні не чарує — закляття обирати не потрібно."} Перевірте
          підсумок праворуч і створіть персонажа.
        </p>
        <button type="button" className="button button--primary" disabled={busy} onClick={() => onSubmit({ spells: [] })}>
          Створити персонажа
        </button>
      </div>
    );
  }

  const cantrips = selected.filter((spell) => spell.level === 0);
  const leveled = selected.filter((spell) => spell.level > 0);
  const preparedCount = leveled.filter((spell) => spell.prepared).length;
  // Маг записує в книгу 6 заклять 1 рівня (PHB, p. 114), а готує з них
  // Інтелект + рівень; у решти, хто готує, «відомих» як ліміту немає.
  const isWizardClass = casting.class_key === "wizard" || casting.class_key.endsWith("/wizard");
  const knownLimit = casting.spells_known_limit ?? (isWizardClass ? 6 : casting.prepared_limit ?? 99);
  // Локальні копії: у замиканнях нижче TS не бачить, що `casting` уже не null.
  const castingClass = casting.class_key;
  const prepares = casting.prepares;
  const preparedLimit = casting.prepared_limit ?? 0;
  const isWizard = castingClass === "wizard" || castingClass.endsWith("/wizard");

  function toggle(entry: { id: string; name_en: string }, level: number, limit: number) {
    setSelected((current) => {
      const exists = current.find((spell) => spell.entry_id === entry.id);
      if (exists) return current.filter((spell) => spell.entry_id !== entry.id);
      const sameLevel = current.filter((spell) => spell.level === level);
      if (sameLevel.length >= limit) return current;
      const preparedNow = current.filter((spell) => spell.prepared).length;
      return [
        ...current,
        {
          name_en: entry.name_en,
          level,
          class_key: castingClass,
          entry_id: entry.id,
          // Підготовлене — поки є місце в ліміті; далі гравець вирішує сам.
          prepared: prepares ? level > 0 && preparedNow < preparedLimit : false,
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

  const filter = (entry: EntryBrief) => matches(query, entry.name_en, spellLabel(entry.name_en));
  const cantripsFull = cantrips.length >= casting.cantrips_limit;
  const leveledFull = leveled.length >= knownLimit;

  return (
    <div className="wizard-step">
      <p className="lead">
        {termLabel(casting.name_en)} чарує від{" "}
        <Term k="spellcasting_ability">
          {casting.ability ? abilityGenitiveLower(casting.ability) : "—"}
        </Term>
        .{" "}
        {casting.prepares ? (
          <>
            Клас <Term k="prepared_spells">готує закляття</Term>: щодня після довгого
            відпочинку можна обрати інший набір — сьогоднішній вибір не остаточний.
          </>
        ) : (
          <>
            Клас <Term k="known_spells">знає закляття</Term>: обрані тут — ваші надовго,
            замінити одне можна лише з новим рівнем.
          </>
        )}
      </p>
      {isWizard ? (
        <p className="hint">
          <Term k="spellbook">Книга заклять мага</Term>: закляття 1 рівня, обрані тут, записані
          у вашій книзі; підготовлені — ті, що ви можете творити сьогодні.
        </p>
      ) : null}

      <SearchField value={query} onChange={setQuery} placeholder="Пошук закляття за назвою" />

      <section className="wizard-block">
        <h3>
          <Term k="cantrip">Заговори</Term> — {cantrips.length} з {casting.cantrips_limit}
        </h3>
        <p className="hint">Творяться без обмежень і не витрачають слотів.</p>
        <ul className="option-list">
          {(options.cantrips ?? []).filter(filter).map((entry) => (
            <SpellOption
              key={entry.id}
              entry={entry}
              level={0}
              active={selected.some((spell) => spell.entry_id === entry.id)}
              disabled={cantripsFull}
              onToggle={() => toggle(entry, 0, casting.cantrips_limit)}
            />
          ))}
        </ul>
      </section>

      <section className="wizard-block">
        <h3>
          Закляття 1 рівня — {leveled.length} з {knownLimit}
        </h3>
        <p className="hint">
          Кожне витрачає <Term k="spell_slot">слот</Term>; на 1 рівні їх 2 на день.
          {casting.prepares ? ` Підготовлено ${preparedCount} з ${casting.prepared_limit}.` : ""}
        </p>
        <ul className="option-list">
          {(options.spells ?? []).filter(filter).map((entry) => {
            const active = selected.find((spell) => spell.entry_id === entry.id);
            return (
              <SpellOption
                key={entry.id}
                entry={entry}
                level={1}
                active={Boolean(active)}
                disabled={leveledFull}
                onToggle={() => toggle(entry, 1, knownLimit)}
                extra={
                  active && casting.prepares ? (
                    <label className="prepared">
                      <input
                        type="checkbox"
                        checked={Boolean(active.prepared)}
                        disabled={!active.prepared && preparedCount >= preparedLimit}
                        onChange={(event) => setPrepared(entry.id, event.target.checked)}
                      />
                      підготовлено
                    </label>
                  ) : null
                }
              />
            );
          })}
        </ul>
      </section>

      {cantrips.length < casting.cantrips_limit || leveled.length < Math.min(knownLimit, 99) ? (
        <p className="hint hint--warn">
          Ще можна обрати: заговорів — {Math.max(0, casting.cantrips_limit - cantrips.length)}
          {knownLimit < 99 ? `, заклять — ${Math.max(0, knownLimit - leveled.length)}` : ""}. Можна
          створити й так, а дообрати на листі (вкладка «Закляття»).
        </p>
      ) : null}

      <button type="button" className="button button--primary" disabled={busy} onClick={() => onSubmit({ spells: selected })}>
        Створити персонажа
      </button>
    </div>
  );
}

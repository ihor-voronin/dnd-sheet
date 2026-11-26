/** Кроки візарда: кожен — форма, що повертає payload для `PUT` кроку.
 *
 * Правила тут не перевіряються: сервер — єдина інстанція. Компонент лише
 * показує, що дозволено (`options`), збирає вибір і показує помилку, яку
 * сервер повернув. Тому кнопка «Далі» ніколи не «вгадує» валідність.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import {
  ABILITY_SHORT,
  ALIGNMENT_LABELS,
  ITEM_KIND_LABELS,
  METHOD_LABELS,
  SIZE_LABELS,
  SKILL_LABELS,
  abilityLabel,
  abilityModifier,
  modifierLabel,
  skillLabel,
} from "../../labels";
import type {
  AbilitiesOptions,
  BackgroundAnswers,
  BackgroundOptions,
  BackgroundView,
  ClassAnswers,
  ClassView,
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

export function SpeciesStep({ answers, options, busy, onSubmit }: StepProps<{ species: SpeciesView[] }>) {
  const initial = answers as unknown as SpeciesAnswers;
  const [name, setName] = useState(initial.name ?? "");
  const [speciesKey, setSpeciesKey] = useState(initial.species_key ?? "");
  const [subspeciesKey, setSubspeciesKey] = useState(initial.subspecies_key ?? "");
  const [choices, setChoices] = useState<string[]>(initial.ability_choices ?? []);

  const selected = options.species.find((item) => item.key === speciesKey);
  const children = selected?.subspecies ?? [];
  const effective = children.find((item) => item.key === subspeciesKey) ?? selected;
  const choice = effective?.ability_choice ?? null;

  // Скидання підрас і вибору — лише коли гравець справді змінив вид,
  // а не коли крок перемальовано з уже збереженою відповіддю.
  const previousSpecies = useRef(speciesKey);
  useEffect(() => {
    if (previousSpecies.current === speciesKey) return;
    previousSpecies.current = speciesKey;
    setSubspeciesKey("");
    setChoices([]);
  }, [speciesKey]);

  function toggleChoice(ability: string) {
    if (!choice) return;
    setChoices((current) => {
      if (current.includes(ability)) return current.filter((item) => item !== ability);
      if (current.length >= choice.count) return current;
      return [...current, ability];
    });
  }

  return (
    <div className="wizard-step">
      <div className="field-row">
        <label className="field">
          <span>Імʼя персонажа</span>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="напр. Дарія Залізний Крок" />
        </label>
      </div>

      <div className="choice-grid">
        {options.species.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`choice ${item.key === speciesKey ? "choice--active" : ""}`}
            aria-label={item.name_en}
            onClick={() => setSpeciesKey(item.key)}
          >
            <strong>{item.name_en}</strong>
            <span className="choice-meta">{SIZE_LABELS[item.size] ?? item.size} · {item.speed} фт</span>
            <span className="choice-meta">{bonusesText(item.ability_bonuses)}</span>
            {item.darkvision ? <span className="choice-meta">темний зір {item.darkvision}</span> : null}
            {item.subspecies?.length ? (
              <span className="choice-meta">підраси: {item.subspecies.length}</span>
            ) : null}
          </button>
        ))}
      </div>

      {children.length ? (
        <section className="wizard-block">
          <h3>Підраса</h3>
          <p className="hint">Підраса додає свої числа до виду, не замінюючи їх.</p>
          <div className="choice-grid choice-grid--compact">
            {children.map((child) => (
              <button
                key={child.key}
                type="button"
                className={`choice ${child.key === subspeciesKey ? "choice--active" : ""}`}
                aria-label={child.name_en}
                onClick={() => setSubspeciesKey(child.key)}
              >
                <strong>{child.name_en}</strong>
                <span className="choice-meta">{bonusesText(child.ability_bonuses)}</span>
                <span className="choice-meta">{child.speed} фт{child.darkvision ? ` · темний зір ${child.darkvision}` : ""}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {choice ? (
        <section className="wizard-block">
          <h3>Бонуси на вибір</h3>
          <p className="hint">
            {effective?.name_en}: оберіть {choice.count} здібності, кожна отримає {modifierLabel(choice.amount)}.
            Обрано {choices.length} з {choice.count}.
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

      {effective ? (
        <p className="hint">
          Разом від виду: {bonusesText(effective.ability_bonuses)}
          {effective.languages.length ? ` · мови: ${effective.languages.join(", ")}` : ""}
          {effective.resistances.length ? ` · опір: ${effective.resistances.join(", ")}` : ""}
        </p>
      ) : null}

      <button
        type="button"
        className="button button--primary"
        disabled={busy || !name.trim() || !speciesKey || Boolean(choice && choices.length !== choice.count)}
        onClick={() =>
          onSubmit({
            name: name.trim(),
            species_key: speciesKey,
            subspecies_key: subspeciesKey || null,
            ability_choices: choices,
          })
        }
      >
        Далі: клас
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. клас
// ---------------------------------------------------------------------------

export function ClassStep({ answers, options, busy, onSubmit }: StepProps<{ classes: ClassView[]; hint?: string }>) {
  const initial = answers as unknown as ClassAnswers;
  const [classKey, setClassKey] = useState(initial.class_key ?? "");
  const [subclassKey, setSubclassKey] = useState(initial.subclass_key ?? "");
  const selected = options.classes.find((item) => item.key === classKey);
  const needsSubclass = Boolean(selected?.subclass && selected.subclass.level === 1 && selected.subclass.options.length);

  const previousClass = useRef(classKey);
  useEffect(() => {
    if (previousClass.current === classKey) return;
    previousClass.current = classKey;
    setSubclassKey("");
  }, [classKey]);

  return (
    <div className="wizard-step">
      <div className="choice-grid">
        {options.classes.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`choice ${item.key === classKey ? "choice--active" : ""}`}
            aria-label={item.name_en}
            onClick={() => setClassKey(item.key)}
          >
            <strong>{item.name_en}</strong>
            <span className="choice-meta">хіт-дайс d{item.hit_die} · майстерність: {item.skill_limit} навичок</span>
            <span className="choice-meta">порятунки: {item.saving_throws.map(abilityLabel).join(", ")}</span>
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
                {item.subclass.title} — з {item.subclass.level} рівня
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {selected ? (
        <section className="wizard-block">
          <h3>{selected.name_en}: що дає на 1 рівні</h3>
          <ul className="plain-list">
            <li>Хіт-дайс: d{selected.hit_die}</li>
            <li>Порятунки: {selected.saving_throws.map(abilityLabel).join(", ")}</li>
            <li>
              Навички: {selected.skill_limit}
              {selected.skill_options.length ? ` зі списку (${selected.skill_options.length})` : " (будь-які)"}
            </li>
            <li>
              Броня: {selected.armor_training.length ? selected.armor_training.join(", ") : "—"}; зброя:{" "}
              {selected.weapon_training.length ? selected.weapon_training.join(", ") : "—"}
            </li>
            {selected.features.length ? (
              <li>Уміння 1 рівня: {selected.features.map((feature) => feature.name_en).join(", ")}</li>
            ) : null}
          </ul>
        </section>
      ) : null}

      {needsSubclass && selected?.subclass ? (
        <label className="field">
          <span>{selected.subclass.title} (обовʼязково на 1 рівні)</span>
          <select value={subclassKey} onChange={(event) => setSubclassKey(event.target.value)}>
            <option value="">— оберіть —</option>
            {selected.subclass.options.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name_en}
              </option>
            ))}
          </select>
        </label>
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

// ---------------------------------------------------------------------------
// 3. характеристики
// ---------------------------------------------------------------------------

export function AbilitiesStep({ answers, options, busy, onSubmit }: StepProps<AbilitiesOptions>) {
  const initial = answers as unknown as { method: string | null; scores: Record<string, number>; rolls: number[] };
  const [method, setMethod] = useState(initial.method ?? "standard_array");
  const [scores, setScores] = useState<Record<string, number>>(() => {
    if (initial.scores && Object.keys(initial.scores).length) return { ...initial.scores };
    return Object.fromEntries(ABILITIES.map((ability) => [ability, 10]));
  });

  const used = useMemo(() => new Set(Object.values(scores)), [scores]);
  const spent = Object.values(scores).reduce(
    (total, score) => total + (options.point_buy.costs[String(score)] ?? 0),
    0,
  );
  const remaining = options.point_buy.budget - spent;
  const bonuses = options.species_bonuses ?? {};

  function setScore(ability: string, value: number) {
    setScores((current) => ({ ...current, [ability]: value }));
  }

  const invalidStandard =
    method === "standard_array" &&
    JSON.stringify([...Object.values(scores)].sort()) !== JSON.stringify([...options.standard_array].sort());
  const invalidPointBuy = method === "point_buy" && remaining < 0;

  return (
    <div className="wizard-step">
      <div className="chip-row">
        {options.methods.map((item) => (
          <button
            key={item}
            type="button"
            className={`chip ${method === item ? "chip--active" : ""}`}
            onClick={() => setMethod(item)}
          >
            {METHOD_LABELS[item] ?? item}
          </button>
        ))}
      </div>

      {method === "standard_array" ? (
        <p className="hint">Набір {options.standard_array.join(", ")} — кожне число рівно один раз.</p>
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
            return (
              <tr key={ability}>
                <th scope="row">{abilityLabel(ability)}</th>
                <td>
                  {method === "standard_array" ? (
                    <select value={base} onChange={(event) => setScore(ability, Number(event.target.value))}>
                      {options.standard_array.map((value) => (
                        <option key={value} value={value} disabled={used.has(value) && value !== base}>
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
                  <strong>{total}</strong>
                </td>
                <td>{modifierLabel(abilityModifier(total))}</td>
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
              {item.name_en}
            </option>
          ))}
        </select>
      </label>

      {background ? (
        <p className="hint">
          Дає: {background.skill_proficiencies.map(skillLabel).join(", ") || "—"}
          {background.tool_proficiencies.length ? ` · інструменти: ${background.tool_proficiencies.join(", ")}` : ""}
          {background.feature_en ? ` · риса: ${background.feature_en}` : ""}
        </p>
      ) : null}

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

export function EquipmentStep({ answers, options, busy, onSubmit }: StepProps<{ items_url: string; hint?: string; class?: { key: string } }>) {
  const initial = answers as unknown as EquipmentAnswers;
  const [items, setItems] = useState<ItemPayload[]>(initial.items ?? []);
  const [money, setMoney] = useState<MoneyPayload>({ ...EMPTY_MONEY, ...(initial.money ?? {}) });
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ id: string; name_en: string }[]>([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("gear");
  const [weight, setWeight] = useState(0);
  const [armorBase, setArmorBase] = useState(12);
  const [dexCap, setDexCap] = useState<number | "">("");
  const [equipped, setEquipped] = useState(false);

  async function search() {
    if (!query.trim()) return;
    try {
      const payload = await searchItems(query.trim());
      setResults(payload.items.map((item) => ({ id: item.id, name_en: item.name_en })));
    } catch {
      setResults([]);
    }
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

  return (
    <div className="wizard-step">
      <p className="hint">{options.hint}</p>

      <section className="wizard-block">
        <h3>Пошук у довіднику</h3>
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
          <button type="button" className="button" onClick={() => void search()}>
            Знайти
          </button>
        </div>
        {results.length ? (
          <div className="chip-row">
            {results.map((item) => (
              <button key={item.id} type="button" className="chip" onClick={() => setName(item.name_en)}>
                {item.name_en}
              </button>
            ))}
          </div>
        ) : null}
        <p className="hint">Назва з довідника лише підставляється: числа броні ви вводите самі.</p>
      </section>

      <section className="wizard-block">
        <h3>Додати предмет</h3>
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
      </section>

      {items.length ? (
        <section className="wizard-block">
          <h3>Інвентар</h3>
          <ul className="plain-list">
            {items.map((item, index) => (
              <li key={`${item.name_en}-${index}`}>
                {item.name_en} · {ITEM_KIND_LABELS[item.kind] ?? item.kind}
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
              <span>{coin}</span>
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

      <div className="button-row">
        <button type="button" className="button" disabled={busy} onClick={() => onSubmit({ items, money })}>
          Пропустити
        </button>
        <button type="button" className="button button--primary" disabled={busy} onClick={() => onSubmit({ items, money })}>
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

/** Підвищення рівня: один екран замість шести кроків візарда.
 *
 * Порядок як у книзі гравця (PHB, розділ «Leveling Up»): клас → хіти →
 * підклас (якщо цей рівень його дає) → покращення характеристик або риса →
 * закляття. Числа не рахуються тут: усе, що показує екран, прийшло з
 * сервера (`GET /level-up`), а «Підняти рівень» надсилає вибір і повертає
 * вже новий лист.
 *
 * Вибір класу — перше, що робить гравець, і саме він визначає решту полів:
 * у Воїна немає заклять, у мага немає «Другого дихання», а підклас може
 * зʼявитися на 1, 2, 3 або 10 рівні залежно від класу.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  fetchCharacter,
  fetchFeats,
  fetchLevelUp,
  levelUpCharacter,
} from "../../api";
import {
  ABILITY_LABELS,
  abilityGenitive,
  modifierLabel,
  subclassLabel,
} from "../../labels";
import type { LevelUpPlan, LevelUpReport, LevelUpView } from "../wizard/types";
import { SubclassBrief } from "../wizard/SubclassBrief";
import { RuleText } from "./panels";
import { featureLabel, termLabel, ukSubclass, withEnglish } from "./uk";

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"] as const;
type AbilityCode = (typeof ABILITIES)[number];

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function planTitle(plan: LevelUpPlan): string {
  if (plan.is_new_class) return `${termLabel(plan.class_name)} · новий клас`;
  return `${termLabel(plan.class_name)} ${plan.current_level} → ${plan.new_level}`;
}

/** Українське відмінювання: 1 покращення, 2 покращення, 5 покращень. */
function plural(count: number, one: string, few: string, many: string): string {
  const mod100 = count % 100;
  const mod10 = count % 10;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

/** Скільки нових заклять клас дає цим рівнем (окремо заговори й решта). */
function spellGain(plan: LevelUpPlan): { cantrips: number; leveled: number } {
  const cantrips = Math.max(0, plan.limits.cantrips.after - plan.limits.cantrips.before);
  const knownBefore = plan.limits.spells_known.before;
  const knownAfter = plan.limits.spells_known.after;
  if (knownBefore !== null && knownAfter !== null) {
    return { cantrips, leveled: Math.max(0, knownAfter - knownBefore) };
  }
  const preparedBefore = plan.limits.prepared.before;
  const preparedAfter = plan.limits.prepared.after;
  if (preparedBefore !== null && preparedAfter !== null) {
    return { cantrips, leveled: Math.max(0, preparedAfter - preparedBefore) };
  }
  return { cantrips, leveled: 0 };
}

export function LevelUpWizard({
  characterId,
  onDone,
  onCancel,
  onOpenSpells,
}: {
  characterId: string;
  onDone: (report: LevelUpReport) => void;
  onCancel: () => void;
  /** Перейти на лист, вкладка «Закляття»: там обирають нові закляття. */
  onOpenSpells?: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [classKey, setClassKey] = useState<string | null>(null);
  // Правило дому: вимоги мультикласу можна обійти, але лист це запамʼятає.
  const [ignoreRequirements, setIgnoreRequirements] = useState(false);
  const [hpMode, setHpMode] = useState<"average" | "roll">("average");
  const [hpRoll, setHpRoll] = useState(1);
  const [subclassKey, setSubclassKey] = useState<string | null>(null);
  const [asiMode, setAsiMode] = useState<"two" | "split" | "feat">("two");
  const [asiFirst, setAsiFirst] = useState<AbilityCode>("str");
  const [asiSecond, setAsiSecond] = useState<AbilityCode>("dex");
  const [featId, setFeatId] = useState<string | null>(null);

  const levelUp = useQuery({
    queryKey: ["level-up", characterId],
    queryFn: () => fetchLevelUp(characterId),
  });
  const sheet = useQuery({
    queryKey: ["character", characterId],
    queryFn: () => fetchCharacter(characterId),
  });

  const view: LevelUpView | undefined = levelUp.data;
  const plan = view?.plans.find((item) => item.class_key === classKey) ?? null;
  const gain = plan ? spellGain(plan) : { cantrips: 0, leveled: 0 };

  const feats = useQuery({
    queryKey: ["feats"],
    queryFn: fetchFeats,
    enabled: Boolean(plan?.asi.pending && asiMode === "feat"),
  });

  // Новий клас — нові вимоги: вибір, зроблений для іншого класу, скидаємо.
  useEffect(() => {
    setSubclassKey(null);
    setAsiMode("two");
    setFeatId(null);
    const first = plan?.subclass?.options[0]?.id ?? null;
    setSubclassKey(first);
    if (plan) setHpRoll(Math.max(1, plan.hp.average));
  }, [classKey, plan?.subclass?.options]);

  const totals = useMemo(() => {
    const ability = (code: string) => sheet.data?.sheet.abilities[code];
    return { ability };
  }, [sheet.data]);

  const hpGain = plan
    ? hpMode === "roll"
      ? Math.max(1, hpRoll + plan.constitution_modifier)
      : plan.hp.average
    : 0;

  function abilityOptions(skip?: AbilityCode) {
    return ABILITIES.filter((code) => code !== skip).map((code) => {
      const value = totals.ability(code);
      const room = value ? value.total < 20 : true;
      return { code, value, room };
    });
  }

  async function submit() {
    if (!plan || !view) return;
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        class_key: plan.class_key,
        version: view.version,
        hp:
          hpMode === "roll"
            ? { mode: "roll", roll: hpRoll }
            : { mode: "average" },
      };
      if (plan.subclass?.required && subclassKey) body.subclass_key = subclassKey;
      // Галочку надсилаємо лише тоді, коли вимог справді бракує: інакше
      // лист отримав би позначку «проігноровано» без причини.
      if (!plan.allowed) body.ignore_requirements = true;
      if (plan.asi.pending) {
        if (asiMode === "feat") {
          if (!featId) throw new Error("оберіть рису або покращення характеристик");
          body.feat_key = featId;
        } else if (asiMode === "two") {
          body.ability_increases = { [asiFirst]: 2 };
        } else {
          if (asiFirst === asiSecond) {
            throw new Error("для +1 і +1 оберіть дві різні характеристики");
          }
          body.ability_increases = { [asiFirst]: 1, [asiSecond]: 1 };
        }
      }
      const result = await levelUpCharacter(characterId, body);
      onDone(result.level_up);
    } catch (failure) {
      setError(messageOf(failure));
      setBusy(false);
    }
  }

  if (levelUp.isPending) return <p className="status">Читаємо рівні…</p>;
  if (levelUp.error) {
    return (
      <p className="status status--error">
        Не вдалося прочитати рівні: {messageOf(levelUp.error)}
      </p>
    );
  }
  if (!view) return null;

  if (!view.can_level_up) {
    return (
      <section className="wizard">
        <h1>Підвищення рівня</h1>
        <p className="hint">
          {view.name} на 20 рівні — це максимум правил 2014. Ростемо тільки
          досвідом у грі, а не рівнем.
        </p>
        <button type="button" className="button" onClick={onCancel}>
          ← До листа
        </button>
      </section>
    );
  }

  const existing = view.plans.filter((item) => !item.is_new_class);
  const fresh = view.plans.filter((item) => item.is_new_class);
  // Номери секцій рахуються, а не вписані: підклас і закляття бувають не в
  // кожного класу, і «3 → 5» виглядало б як збій.
  let step = 0;
  const nextStep = () => ++step;

  return (
    <section className="wizard levelup">
      <header className="wizard-header">
        <div>
          <h1>Підвищення рівня</h1>
          <p className="meta">
            {view.name} · рівень {view.total_level} → {view.total_level + 1} · правила 2014
          </p>
        </div>
      </header>

      {error ? <p className="status status--error">{error}</p> : null}

      <div className="wizard-body">
        <section className="wizard-block">
          <h3>{nextStep()}. Клас</h3>
          <div className="levelup-grid">
            {existing.map((item) => (
              <button
                key={item.class_key}
                type="button"
                className={`chip ${classKey === item.class_key ? "chip--active" : ""}`}
                onClick={() => setClassKey(item.class_key)}
              >
                {planTitle(item)}
              </button>
            ))}
          </div>
          <p className="hint">Новий клас — мультиклас; він вимагає 13 у ключовій характеристиці.</p>
          {fresh.some((item) => !item.allowed) ? (
            <span className="levelup-ignore">
              <input
                id="levelup-ignore-requirements"
                type="checkbox"
                checked={ignoreRequirements}
                onChange={(event) => {
                  const next = event.target.checked;
                  setIgnoreRequirements(next);
                  // Вимкнали галочку — недоступний клас більше не вибраний.
                  if (!next && plan && !plan.allowed) setClassKey(null);
                }}
              />
              <label htmlFor="levelup-ignore-requirements">
                ігнорувати вимоги мультикласу (правило дому)
              </label>
            </span>
          ) : null}
          <div className="levelup-grid">
            {fresh.map((item) => {
              const title = item.allowed
                ? planTitle(item)
                : `${termLabel(item.class_name)} — ${item.requirements.join(" / ")}`;
              return (
                <button
                  key={item.class_key}
                  type="button"
                  className={`chip ${classKey === item.class_key ? "chip--active" : ""}`}
                  title={item.blocked_reason ?? item.requirements.join(" / ")}
                  disabled={!item.allowed && !ignoreRequirements}
                  onClick={() => setClassKey(item.class_key)}
                >
                  {title}
                </button>
              );
            })}
          </div>
        </section>

        {plan ? (
          <>
            <section className="wizard-block">
              <h3>{nextStep()}. Хіти</h3>
              <p className="hint">
                Клас дає d{plan.hit_die}, Статура {modifierLabel(plan.constitution_modifier)}.
                Середнє за правилом «половина дайса + 1».
              </p>
              <div className="levelup-row">
                <label className="radio">
                  <input
                    type="radio"
                    checked={hpMode === "average"}
                    onChange={() => setHpMode("average")}
                  />
                  середнє: +{plan.hp.average}
                </label>
                <label className="radio">
                  <input
                    type="radio"
                    checked={hpMode === "roll"}
                    onChange={() => setHpMode("roll")}
                  />
                  кидок d{plan.hit_die}:
                </label>
                <input
                  type="number"
                  className="number"
                  min={1}
                  max={plan.hit_die}
                  value={hpRoll}
                  disabled={hpMode !== "roll"}
                  onChange={(event) =>
                    setHpRoll(Math.min(plan.hit_die, Math.max(1, Number(event.target.value))))
                  }
                />
                <span className="meta">разом +{hpGain} хітів</span>
              </div>
            </section>

            <section className="wizard-block">
              <h3>{nextStep()}. Нові вміння класу</h3>
              {plan.features.length ? (
                <ul className="plain-list">
                  {plan.features.map((item) => (
                    <li key={`${item.level}-${item.name_en}`}>
                      <details className="reckoning" open>
                        <summary>
                          {item.name_uk
                            ? withEnglish(item.name_en, item.name_uk)
                            : item.name_en}
                        </summary>
                        {item.text_uk || item.text ? (
                          <RuleText text={item.text_uk || item.text || ""} />
                        ) : (
                          <p className="hint">
                            Тексту цього вміння в корпусі немає — назва й рівень
                            є, пояснення шукайте в книзі.
                          </p>
                        )}
                      </details>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="hint">Цей рівень не додає нових умінь класу.</p>
              )}
            </section>

            {plan.subclass?.required ? (
              <section className="wizard-block">
                <h3>
                  {nextStep()}. {plan.subclass.title ? termLabel(plan.subclass.title) : "Підклас"}
                </h3>
                <p className="hint">
                  Цей рівень дає підклас. Його вміння зʼявляться на листі одразу.
                </p>
                <div className="levelup-grid">
                  {plan.subclass.options.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      className={`chip chip--column ${subclassKey === option.id ? "chip--active" : ""}`}
                      onClick={() => setSubclassKey(option.id)}
                    >
                      <span>
                        {withEnglish(
                          subclassLabel(option.name_en),
                          option.name_uk ?? ukSubclass(option.id),
                        )}
                      </span>
                      {option.features.some((item) => item.new) ? (
                        <span className="meta">
                          {option.features
                            .filter((item) => item.new)
                            .map((item) =>
                              item.name_uk
                                ? withEnglish(item.name_en, item.name_uk)
                                : item.name_en,
                            )
                            .join(" · ")}
                        </span>
                      ) : null}
                    </button>
                  ))}
                </div>

                {subclassKey ? (
                  <SubclassBrief
                    subclassKey={subclassKey}
                    highlightLevel={plan.new_level}
                  />
                ) : null}
              </section>
            ) : null}

            {plan.asi.pending ? (
              <section className="wizard-block">
                <h3>{nextStep()}. Покращення характеристик</h3>
                <p className="hint">
                  Рівні дали {plan.asi.slots} {plural(plan.asi.slots, "покращення", "покращення", "покращень")},
                  використано {plan.asi.taken}. Або +2 до однієї характеристики, або +1 до двох, або риса.
                </p>
                <div className="levelup-row">
                  <label className="radio">
                    <input
                      type="radio"
                      checked={asiMode === "two"}
                      onChange={() => setAsiMode("two")}
                    />
                    +2 до однієї
                  </label>
                  <label className="radio">
                    <input
                      type="radio"
                      checked={asiMode === "split"}
                      onChange={() => setAsiMode("split")}
                    />
                    +1 і +1
                  </label>
                  <label className="radio">
                    <input
                      type="radio"
                      checked={asiMode === "feat"}
                      onChange={() => setAsiMode("feat")}
                    />
                    риса замість
                  </label>
                </div>

                {asiMode !== "feat" ? (
                  <div className="levelup-row">
                    <select
                      className="select"
                      value={asiFirst}
                      onChange={(event) => setAsiFirst(event.target.value as AbilityCode)}
                    >
                      {abilityOptions(asiMode === "split" ? asiSecond : undefined).map((option) => (
                        <option key={option.code} value={option.code} disabled={!option.room}>
                          {ABILITY_LABELS[option.code]}
                          {option.value ? ` ${option.value.total}` : ""}
                          {option.room ? "" : " — межа 20"}
                        </option>
                      ))}
                    </select>
                    {asiMode === "split" ? (
                      <select
                        className="select"
                        value={asiSecond}
                        onChange={(event) => setAsiSecond(event.target.value as AbilityCode)}
                      >
                        {abilityOptions(asiFirst).map((option) => (
                          <option key={option.code} value={option.code} disabled={!option.room}>
                            {ABILITY_LABELS[option.code]}
                            {option.value ? ` ${option.value.total}` : ""}
                            {option.room ? "" : " — межа 20"}
                          </option>
                        ))}
                      </select>
                    ) : null}
                  </div>
                ) : (
                  <div className="levelup-feats">
                    {feats.isPending ? <p className="meta">Читаємо риси…</p> : null}
                    {feats.error ? (
                      <p className="status status--error">{messageOf(feats.error)}</p>
                    ) : null}
                    <div className="levelup-feat-list">
                      {(feats.data ?? []).map((feat) => (
                        <label key={feat.id} className={`chip chip--row ${featId === feat.id ? "chip--active" : ""}`}>
                          <input
                            type="radio"
                            name="feat"
                            checked={featId === feat.id}
                            onChange={() => setFeatId(feat.id)}
                          />
                          <span>{feat.name_uk || feat.name_en}</span>
                          <span className="meta">{feat.source_id}</span>
                        </label>
                      ))}
                    </div>
                    <p className="hint">
                      Числові ефекти риси (наприклад, +1 до характеристики) вписуються
                      в лист вручну — як виправлення поля.
                    </p>
                  </div>
                )}
              </section>
            ) : null}

            {plan.max_spell_level > 0 ? (
              <section className="wizard-block">
                <h3>{nextStep()}. Закляття — обираються на листі</h3>
                <p className="hint">
                  {gain.cantrips ? `Цей рівень дає заговорів: +${gain.cantrips}. ` : ""}
                  {gain.leveled ? `Заклять: +${gain.leveled}. ` : ""}
                  {gain.cantrips + gain.leveled
                    ? "Доступні рівні заклять — до "
                    : "Нових заклять цей рівень не додає. "}
                  {gain.cantrips + gain.leveled ? `${plan.max_spell_level}-го. ` : ""}
                  Тут ми їх не обираємо: після підвищення відкрийте{" "}
                  <strong>лист персонажа → вкладка «Закляття» → «Додати закляття»</strong>.
                  Там повний список класу з описами, фільтр за рівнем і позначка
                  «підготовлено» для класів, що готують закляття. Так ви бачите
                  всі варіанти й можете повернутися до вибору пізніше.
                </p>
                {onOpenSpells ? (
                  <button type="button" className="button" onClick={onOpenSpells}>
                    До заклять на листі
                  </button>
                ) : null}
              </section>
            ) : null}

            {plan.subclass_features.length ? (
              <section className="wizard-block">
                <h3>Нові вміння підкласу</h3>
                {plan.subclass_features.map((item) => (
                  <details key={item.name_en} className="reckoning">
                    <summary>
                      {item.name_uk
                        ? withEnglish(item.name_en, item.name_uk)
                        : featureLabel(item.name_en)}
                    </summary>
                    <RuleText text={item.text_uk || item.description} />
                  </details>
                ))}
              </section>
            ) : null}

            <section className="wizard-block levelup-summary">
              <h3>Що зміниться</h3>
              <ul className="levelup-list">
                <li>
                  рівень {plan.total_level_before} → {plan.total_level_after}
                  {plan.is_new_class ? " · новий клас" : ""}
                </li>
                {plan.allowed ? null : (
                  <li className="levelup-warning">
                    вимоги мультикласу проігноровано: {plan.requirements.join(" або ")} — на
                    листі буде позначка
                  </li>
                )}
                <li>
                  хіти: {sheet.data?.sheet.hit_points.maximum ?? "?"} →{" "}
                  {(sheet.data?.sheet.hit_points.maximum ?? 0) + hpGain}
                </li>
                {plan.proficiency_bonus.after !== plan.proficiency_bonus.before ? (
                  <li>
                    бонус майстерності {modifierLabel(plan.proficiency_bonus.before)} →{" "}
                    {modifierLabel(plan.proficiency_bonus.after)}
                  </li>
                ) : null}
                {plan.slots
                  .filter((row) => row.before !== row.after)
                  .map((row) => (
                    <li key={row.level}>
                      слоти {row.level} рівня: {row.before} → {row.after}
                    </li>
                  ))}
                {plan.pact.after ? (
                  <li>
                    Pact Magic: {plan.pact.before?.[0] ?? 0} → {plan.pact.after[0]} слотів{" "}
                    {plan.pact.after[1]} рівня
                  </li>
                ) : null}
                {plan.asi.pending ? (
                  <li>
                    {asiMode === "feat"
                      ? `риса: ${feats.data?.find((feat) => feat.id === featId)?.name_uk || featId || "не обрано"}`
                      : asiMode === "two"
                        ? `+2 до ${abilityGenitive(asiFirst)}`
                        : `+1 до ${abilityGenitive(asiFirst)} і +1 до ${abilityGenitive(asiSecond)}`}
                  </li>
                ) : null}
                {plan.features.length ? (
                  <li>
                    вміння: {plan.features
                      .map((item) => featureLabel(item.name_en, item.name_uk))
                      .join(", ")}
                  </li>
                ) : null}
                {plan.resources_added.length ? (
                  <li>
                    ресурси: {plan.resources_added
                      .map((item) => featureLabel(item.name_en, item.name_uk))
                      .join(", ")}
                  </li>
                ) : null}
              </ul>
              <button
                type="button"
                className="button button--primary"
                disabled={busy}
                onClick={() => void submit()}
              >
                {busy
                  ? "Зберігаємо…"
                  : plan.is_new_class
                    ? `Узяти 1 рівень: ${termLabel(plan.class_name)}`
                    : `Підняти до ${plan.new_level} ${plural(plan.new_level, "рівня", "рівня", "рівня")}`}
              </button>
            </section>
          </>
        ) : (
          <p className="hint">Оберіть клас — і покажемо, що дасть рівень.</p>
        )}
      </div>
    </section>
  );
}

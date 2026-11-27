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
  fetchClassSpells,
  fetchEntry,
  fetchFeats,
  fetchLevelUp,
  levelUpCharacter,
  prepareCharacterSpells,
} from "../../api";
import type { SheetMutation } from "../../api";
import type { FeatEntry } from "../wizard/types";
import { ActiveGloss, GlossProvider, Term } from "../../components/Term";
import {
  ABILITY_LABELS,
  abilityCodesUk,
  abilityGenitive,
  schoolLabel,
  abilityModifier,
  classGuide,
  modifierLabel,
  skillLabel,
  sourceLabel,
  subclassLabel,
} from "../../labels";
import type { LevelUpPlan, LevelUpReport, LevelUpView } from "../wizard/types";
import { SubclassBrief } from "../wizard/SubclassBrief";
import { RuleText } from "./panels";
import { SpellsPreparePanel } from "./spells";
import { featLabel, featureLabel, itemLabel, spellLabel, termLabel, ukSubclass, withEnglish } from "./uk";

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
  const [featAbility, setFeatAbility] = useState<string | null>(null);
  const [skill, setSkill] = useState<string | null>(null);
  const [tool, setTool] = useState<string | null>(null);
  const [replaceSpell, setReplaceSpell] = useState<{ from: string; to: string }>({ from: "", to: "" });
  const [newSpells, setNewSpells] = useState<string[]>([]);
  const [spellQuery, setSpellQuery] = useState("");
  // Рівень уже піднято, а клас готує закляття щодня: підготовка — тут же, не на листі.
  const [done, setDone] = useState<(SheetMutation & { report: LevelUpReport; classKey: string }) | null>(null);

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

  // Відомі закляття класу, які можна замінити одним новим (бард, чаклун, чародій…).
  const knownSpells =
    plan && !plan.is_new_class && plan.limits.spells_known.after !== null
      ? (sheet.data?.sheet.spells ?? []).filter(
          (spell) => spell.class_key === plan.class_key && spell.level > 0 && !spell.always_prepared,
        )
      : [];
  // Що обирається просто тут: заговори, відомі закляття (бард, чаклун…) і
  // 2 закляття в книгу мага (PHB, p. 114). Ті, хто готує, лише готують на листі.
  // Лише закляття, обрані класом: доменні й подібні (підклас) мають той самий
  // class_key, але в ліміти відомих не входять.
  const ownSpells = (sheet.data?.sheet.spells ?? []).filter(
    (spell) => spell.class_key === plan?.class_key && spell.source === "class",
  );
  const pickCantrips = gain.cantrips;
  const pickLeveled = !plan
    ? 0
    : plan.class_key === "wizard"
      ? plan.is_new_class
        ? 6
        : 2
      : plan.limits.spells_known.after !== null
        ? gain.leveled
        : 0;
  const classSpells = useQuery({
    queryKey: ["class-spells", plan?.class_key, plan?.max_spell_level],
    queryFn: () => fetchClassSpells(plan!.class_key, plan!.max_spell_level),
    enabled: Boolean(plan && (replaceSpell.from || pickCantrips + pickLeveled > 0)),
  });
  const learnable = (classSpells.data?.items ?? []).filter(
    (entry) =>
      Number(entry.data.level ?? 0) <= (plan?.max_spell_level ?? 0) &&
      !ownSpells.some((spell) => spell.name_en.toLowerCase() === entry.name_en.toLowerCase()),
  );
  const pickedOf = (cantrip: boolean) =>
    newSpells.filter((name) =>
      learnable.some((entry) => entry.name_en === name && (Number(entry.data.level ?? 0) === 0) === cantrip),
    );
  const replacements = (classSpells.data?.items ?? []).filter(
    (entry) =>
      Number(entry.data.level ?? 0) > 0 &&
      !knownSpells.some((spell) => spell.name_en.toLowerCase() === entry.name_en.toLowerCase()),
  );

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
    setSkill(null);
    setTool(null);
    setReplaceSpell({ from: "", to: "" });
    setNewSpells([]);
    // Підклас не обирається за гравця: раніше перший варіант ставав
    // «вибраним» сам, і його легко було не помітити.
    setSubclassKey(null);
    const guide = classGuide(classKey);
    if (guide) {
      setAsiFirst(guide.primary[0] as AbilityCode);
      setAsiSecond((guide.primary[1] ?? "con") as AbilityCode);
    }
    // Кидок — число на кубику, без Статури: її додаємо окремо.
    if (plan) setHpRoll(Math.max(1, Math.ceil(plan.hit_die / 2)));
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
      const step = asiMode === "two" ? 2 : 1;
      // Межа 20 — після покращення: 19 + 2 уже не можна, а 19 + 1 можна.
      const room = value ? value.total + step <= 20 : true;
      const after = value ? Math.min(20, value.total + step) : null;
      const change =
        value && after !== null
          ? ` ${value.total} → ${after} (${modifierLabel(value.modifier)} → ${modifierLabel(abilityModifier(after))})`
          : "";
      const key = classGuide(classKey)?.primary.includes(code);
      return { code, value, room, change, key };
    });
  }

  // Обрана характеристика впирається в 20 — перемикаємо на першу, де є місце,
  // інакше сервер відмовить, а гравець не зрозуміє чому.
  useEffect(() => {
    const options = abilityOptions(asiMode === "split" ? asiSecond : undefined);
    const current = options.find((option) => option.code === asiFirst);
    if (current && !current.room) {
      const next = options.find((option) => option.room);
      if (next) setAsiFirst(next.code);
    }
    if (asiMode === "split") {
      const second = abilityOptions(asiFirst).find((option) => option.code === asiSecond);
      if (second && !second.room) {
        const next = abilityOptions(asiFirst).find((option) => option.room);
        if (next) setAsiSecond(next.code);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asiMode, asiFirst, asiSecond, sheet.data]);

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
          if (featAbility) body.feat_ability = featAbility;
        } else if (asiMode === "two") {
          body.ability_increases = { [asiFirst]: 2 };
        } else {
          if (asiFirst === asiSecond) {
            throw new Error("для +1 і +1 оберіть дві різні характеристики");
          }
          body.ability_increases = { [asiFirst]: 1, [asiSecond]: 1 };
        }
      }
      if (plan.skill_options?.length) {
        if (!skill) throw new Error("оберіть навичку, яку дає новий клас");
        body.skill = skill;
      }
      const learned = learnable
        .filter((entry) => newSpells.includes(entry.name_en))
        .map((entry) => ({ name_en: entry.name_en, level: Number(entry.data.level ?? 0), entry_id: entry.id }));
      body.spells = learned;
      if (plan.tool_options?.length) {
        if (!tool) throw new Error("оберіть музичний інструмент, яким володітимете");
        body.tool = tool;
      }
      if (replaceSpell.from) {
        if (!replaceSpell.to.trim()) throw new Error("впишіть, яке закляття стає на місце забутого");
        body.replace_spell = replaceSpell.from;
        const entry = replacements.find((item) => item.name_en === replaceSpell.to);
        if (!entry) throw new Error("оберіть нове закляття зі списку класу");
        body.spells = [...learned, { name_en: entry.name_en, level: Number(entry.data.level ?? 1), entry_id: entry.id }];
      }
      const result = await levelUpCharacter(characterId, body);
      const prepares = result.sheet.spellcasting.classes.some(
        (item) => item.key === plan.class_key && item.prepares && item.prepared_limit !== null,
      );
      if (prepares) {
        setDone({ sheet: result.sheet, version: result.version, report: result.level_up, classKey: plan.class_key });
        setBusy(false);
      } else {
        onDone(result.level_up);
      }
    } catch (failure) {
      setError(humanError(messageOf(failure)));
      setBusy(false);
    }
  }

  if (done) {
    const casting = {
      ...done.sheet.spellcasting,
      classes: done.sheet.spellcasting.classes.filter((item) => item.key === done.classKey),
    };
    return (
      <div className="levelup">
        <section className="wizard-block">
          <h2>
            Рівень піднято: {termLabel(done.report.class_name)} {done.report.from_level} → {done.report.to_level}
          </h2>
          <p className="hint">
            Клас готує закляття щодня: оберіть набір на сьогодні тут або пізніше на листі,
            вкладка «Закляття». Ліміт уже враховує новий рівень.
          </p>
          <SpellsPreparePanel
            casting={casting}
            spells={done.sheet.spells}
            busy={busy}
            onSave={async (key, picks) => {
              setBusy(true);
              setError(null);
              try {
                const result = await prepareCharacterSpells(characterId, key, picks, done.version);
                setDone({ ...done, sheet: result.sheet, version: result.version });
                return true;
              } catch (failure) {
                setError(humanError(messageOf(failure)));
                return false;
              } finally {
                setBusy(false);
              }
            }}
          />
          {error ? (
            <p className="status status--error" role="alert">
              {error}
            </p>
          ) : null}
          <button type="button" className="button button--primary" onClick={() => onDone(done.report)}>
            До листа
          </button>
        </section>
      </div>
    );
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
    <GlossProvider>
    <section className="wizard levelup wizard--layout wizard--levelup">
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
                <span>{planTitle(item)}</span>
                <span className="chip__sub">{planPreview(item)}</span>
              </button>
            ))}
          </div>
          <p className="hint">
            Зазвичай рівень беруть у своєму класі. Новий клас — це{" "}
            <Term k="multiclass">мультиклас</Term>: потрібно 13 в основній характеристиці і
            старого, і нового класу, а новий клас дає лише частину володінь.
          </p>
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
                : `${termLabel(item.class_name)} — ${abilityCodesUk(item.requirements.join(" / "))}`;
              return (
                <button
                  key={item.class_key}
                  type="button"
                  className={`chip ${classKey === item.class_key ? "chip--active" : ""}`}
                  title={abilityCodesUk(item.blocked_reason ?? item.requirements.join(" / "))}
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
                Максимум <Term k="hit_points">хітів</Term> росте з кожним рівнем: результат{" "}
                <Term k="hit_die">кості хітів</Term> d{plan.hit_die} + модифікатор Статури (
                {modifierLabel(plan.constitution_modifier)}), щонайменше 1. Середнє (
                {Math.floor(plan.hit_die / 2) + 1}) надійніше; кидок може дати більше або менше.
                Вибір остаточний.
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
                  кидок d{plan.hit_die} (число на кубику):
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
                            Опису цього вміння в довіднику немає — подивіться в
                            книзі гравця, розділ класу.
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

            {plan.features.some((item) => item.name_en === "Expertise") ? (
              <p className="hint hint--warn">
                Цей рівень дає <Term k="expertise">експертизу</Term> у двох навичках. Оберіть їх
                одразу після підвищення: лист персонажа → блок «Навички» → «Експертиза».
              </p>
            ) : null}

            {plan.subclass?.required ? (
              <section className="wizard-block">
                <h3>
                  {nextStep()}. {plan.subclass.title ? termLabel(plan.subclass.title) : "Підклас"}
                </h3>
                <p className="hint">
                  Цей рівень дає <Term k="subclass">підклас</Term> — спеціалізацію на всю гру,
                  змінити її потім не можна. Розгорніть варіант, щоб побачити, що він дасть
                  зараз і на наступних рівнях.
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
                <h3>
                  {nextStep()}. <Term k="ability_score_improvement">Покращення характеристик</Term>
                </h3>
                <p className="hint">
                  Рівні дали {plan.asi.slots} {plural(plan.asi.slots, "покращення", "покращення", "покращень")},
                  використано {plan.asi.taken}. Оберіть +2 до однієї характеристики, +1 до двох або{" "}
                  <Term k="feat">рису</Term>. Порада: доводьте до парного числа — саме тоді росте{" "}
                  <Term k="modifier">модифікатор</Term>.
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
                          {option.room ? option.change : ` — ${option.value?.total ?? ""}: більше 20 не буде`}
                          {option.key ? " · основна для класу" : ""}
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
                            {option.room ? option.change : ` — ${option.value?.total ?? ""}: більше 20 не буде`}
                            {option.key ? " · основна для класу" : ""}
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
                    <FeatPicker
                      feats={feats.data ?? []}
                      value={featId}
                      onChange={(id) => {
                        setFeatId(id);
                        setFeatAbility(view?.feat_abilities?.[id]?.[0] ?? null);
                      }}
                    />
                    {featId && (view?.feat_abilities?.[featId]?.length ?? 0) > 1 ? (
                      <label className="field">
                        <span>Риса дає +1 до характеристики — оберіть яку</span>
                        <select
                          className="select"
                          value={featAbility ?? ""}
                          onChange={(event) => setFeatAbility(event.target.value)}
                        >
                          {view?.feat_abilities?.[featId]?.map((code) => (
                            <option key={code} value={code}>
                              {ABILITY_LABELS[code as AbilityCode] ?? code}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <p className="hint">
                      +1 до характеристики, Tough, Alert, Mobile, Observant, Resilient і броню рис
                      лист рахує сам. Якщо риса дає вибір (навички, закляття, маневри), його буде
                      запропоновано на листі в «Уміннях → Вибори класу й рис».
                    </p>
                  </div>
                )}
              </section>
            ) : null}

            {plan.skill_options?.length ? (
              <section className="wizard-block">
                <h3>{nextStep()}. Навичка нового класу</h3>
                <p className="hint">
                  Мультиклас у {plan.class_name} дає володіння однією навичкою (PHB, с. 164).
                </p>
                <select className="select" value={skill ?? ""} onChange={(event) => setSkill(event.target.value || null)}>
                  <option value="">— оберіть навичку —</option>
                  {plan.skill_options.map((code) => (
                    <option key={code} value={code}>
                      {skillLabel(code)}
                    </option>
                  ))}
                </select>
              </section>
            ) : null}

            {plan.tool_options?.length ? (
              <section className="wizard-block">
                <h3>{nextStep()}. Музичний інструмент</h3>
                <p className="hint">Мультиклас у барда дає володіння одним музичним інструментом (PHB, с. 164).</p>
                <select className="select" value={tool ?? ""} onChange={(event) => setTool(event.target.value || null)}>
                  <option value="">— оберіть інструмент —</option>
                  {plan.tool_options.map((name) => (
                    <option key={name} value={name}>
                      {itemLabel(name)}
                    </option>
                  ))}
                </select>
              </section>
            ) : null}

            {knownSpells.length ? (
              <section className="wizard-block">
                <h3>{nextStep()}. Заміна закляття (за бажанням)</h3>
                <p className="hint">
                  На кожному рівні класу можна забути одне відоме закляття й вивчити замість нього
                  інше зі списку класу доступного рівня.
                </p>
                <div className="inline-row">
                  <select
                    className="select"
                    value={replaceSpell.from}
                    onChange={(event) => setReplaceSpell({ from: event.target.value, to: "" })}
                  >
                    <option value="">не замінювати</option>
                    {knownSpells.map((spell) => (
                      <option key={spell.name_en} value={spell.name_en}>
                        {spellLabel(spell.name_en)} ({spell.level} рів.)
                      </option>
                    ))}
                  </select>
                  {replaceSpell.from ? (
                    <select
                      className="select"
                      value={replaceSpell.to}
                      onChange={(event) => setReplaceSpell({ ...replaceSpell, to: event.target.value })}
                    >
                      <option value="">{classSpells.isPending ? "читаємо список…" : "— нове закляття —"}</option>
                      {replacements.map((entry) => (
                        <option key={entry.id} value={entry.name_en}>
                          {spellLabel(entry.name_en)} ({Number(entry.data.level)} рів.)
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>
              </section>
            ) : null}

            {plan.max_spell_level > 0 ? (
              <section className="wizard-block">
                <h3>{nextStep()}. {pickCantrips + pickLeveled ? "Нові закляття" : "Закляття — підготовка після підвищення"}</h3>
                {pickCantrips + pickLeveled ? (
                  <div className="levelup-spells">
                    <p className="hint">
                      {pickCantrips ? `Заговорів (cantrips): ${pickedOf(true).length} з ${pickCantrips}. ` : ""}
                      {pickLeveled
                        ? `${plan.class_key === "wizard" ? "У книгу заклять (spellbook)" : "Відомих заклять"}: ${pickedOf(false).length} з ${pickLeveled}, до ${plan.max_spell_level}-го рівня.`
                        : ""}
                    </p>
                    {plan.class_key === "fighter" || plan.class_key === "rogue" ? (
                      <p className="hint">
                        {plan.class_key === "fighter"
                          ? "Містичний лицар (Eldritch Knight) вивчає закляття огородження й вивернення"
                          : "Таємний пройдисвіт (Arcane Trickster) вивчає закляття зачарування й ілюзії"}
                        ; лише на 3, 8, 14 і 20 рівнях можна взяти одне будь-якої школи (PHB, с. 75, 98).
                      </p>
                    ) : null}
                    <label className="search-field">
                      <span className="visually-hidden">Пошук закляття</span>
                      <input
                        type="search"
                        value={spellQuery}
                        placeholder="Пошук закляття українською або англійською"
                        onChange={(event) => setSpellQuery(event.target.value)}
                      />
                    </label>
                    {classSpells.isPending ? <p className="meta">Читаємо список класу…</p> : null}
                    <div className="chip-row">
                      {learnable
                        .filter((entry) => {
                          const cantrip = Number(entry.data.level ?? 0) === 0;
                          if (cantrip ? !pickCantrips : !pickLeveled) return false;
                          const needle = spellQuery.trim().toLocaleLowerCase();
                          return !needle || spellLabel(entry.name_en).toLocaleLowerCase().includes(needle);
                        })
                        .map((entry) => {
                          const cantrip = Number(entry.data.level ?? 0) === 0;
                          const active = newSpells.includes(entry.name_en);
                          const full = pickedOf(cantrip).length >= (cantrip ? pickCantrips : pickLeveled);
                          return (
                            <button
                              key={entry.id}
                              type="button"
                              className={`chip ${active ? "chip--active" : ""}`}
                              aria-pressed={active}
                              disabled={!active && full}
                              onClick={() =>
                                setNewSpells((current) =>
                                  active ? current.filter((name) => name !== entry.name_en) : [...current, entry.name_en],
                                )
                              }
                            >
                              {spellLabel(entry.name_en)} · {cantrip ? "заговір" : `${Number(entry.data.level)} рів.`}
                              {entry.data.school ? ` · ${schoolLabel(String(entry.data.school))}` : ""}
                            </button>
                          );
                        })}
                    </div>
                  </div>
                ) : null}
                <p className="hint">
                  {plan.class_key === "wizard"
                    ? "Маг вписує в книгу 2 нові закляття за рівень (PHB, с. 114), а готує лише з книги. "
                    : ""}
                  {pickCantrips + pickLeveled
                    ? "Описи заклять — на листі, вкладка «Закляття»."
                    : gain.leveled
                      ? `Клас готує закляття щодня зі всього списку: тепер можна готувати на ${gain.leveled} більше, до ${plan.max_spell_level}-го рівня. Підготовка — наступним кроком, одразу після підвищення.`
                      : "Нових заклять цей рівень не додає."}
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
                    вимоги мультикласу проігноровано: {abilityCodesUk(plan.requirements.join(" або "))} — на
                    листі буде позначка
                  </li>
                )}
                <li>
                  хіти: {sheet.data?.sheet.hit_points.maximum ?? "?"} →{" "}
                  {(sheet.data?.sheet.hit_points.maximum ?? 0) + hpGain}
                </li>
                {plan.proficiency_bonus.after !== plan.proficiency_bonus.before ? (
                  <li>
                    <Term k="proficiency_bonus">бонус майстерності</Term>{" "}
                    {modifierLabel(plan.proficiency_bonus.before)} →{" "}
                    {modifierLabel(plan.proficiency_bonus.after)}
                  </li>
                ) : null}
                {plan.slots
                  .filter((row) => row.before !== row.after)
                  .map((row) => (
                    <li key={row.level}>
                      <Term k="spell_slot">комірки</Term> {row.level} рівня: {row.before} → {row.after}
                    </li>
                  ))}
                {plan.pact.after ? (
                  <li>
                    <Term k="pact_magic">магія пакту</Term>: {plan.pact.before?.[0] ?? 0} →{" "}
                    {plan.pact.after[0]} комірок {plan.pact.after[1]} рівня
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
              <p className="hint">
                Підвищення не можна скасувати в застосунку — перевірте список вище.
                {plan.max_spell_level > 0 && plan.limits.prepared.after !== null
                  ? " Підготовку на день запропонуємо одразу після цього."
                  : ""}
              </p>
              {error ? (
                <p className="status status--error" role="alert">
                  Рівень не піднято: {error}
                </p>
              ) : null}
              <button
                type="button"
                className="button button--primary button--seal"
                disabled={busy || Boolean(plan.subclass?.required && !subclassKey) || (plan.asi.pending && asiMode === "feat" && !featId)}
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
      <aside className="margin" aria-label="Пояснення">
        <ActiveGloss
          fallback={
            <p className="margin__tip">
              Слова з пунктиром — терміни. Натисніть, і тут зʼявиться пояснення.
            </p>
          }
        />
      </aside>
    </section>
    </GlossProvider>
  );
}

/** Відповідь сервера людською мовою: «dex: підсумок…» → «Спритність: …». */
function humanError(raw: string): string {
  const match = raw.match(/^(str|dex|con|int|wis|cha): підсумок не може бути більшим за 20 \((\d+) \+ (\d+) бонус виду \+ (\d+)\)/);
  if (match) {
    const [, code, base, bonus, amount] = match;
    const total = Number(base) + Number(bonus);
    return `${ABILITY_LABELS[code]} уже ${total}, а +${amount} дасть ${total + Number(amount)} — більше 20 не можна. Оберіть іншу характеристику або +1 і +1.`;
  }
  return abilityCodesUk(raw);
}

/** Підпис під чипом класу: що дасть саме цей рівень — ще до кліку. */
function planPreview(plan: LevelUpPlan): string {
  const parts: string[] = [];
  if (plan.subclass?.required) parts.push("підклас");
  if (plan.asi.pending) parts.push("покращення характеристик");
  if (plan.proficiency_bonus.after !== plan.proficiency_bonus.before) parts.push("бонус майстерності");
  const named = plan.features
    .filter((item) => item.name_en !== "Ability Score Improvement")
    .map((item) => item.name_uk || item.name_en);
  parts.push(...named.slice(0, 2));
  if (named.length > 2) parts.push(`ще ${named.length - 2}`);
  return parts.length ? parts.join(", ") : "лише хіти";
}

/** Риси: пошук, книга, вимоги й текст на розгортання. */
export function FeatPicker({
  feats,
  value,
  onChange,
}: {
  feats: FeatEntry[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLocaleLowerCase();
  const list = feats.filter(
    (feat) =>
      !needle ||
      feat.name_en.toLocaleLowerCase().includes(needle) ||
      (feat.name_uk ?? featLabel(feat.name_en)).toLocaleLowerCase().includes(needle),
  );
  return (
    <div className="feat-picker">
      <label className="search-field">
        <span className="visually-hidden">Пошук риси</span>
        <input
          type="search"
          value={query}
          placeholder="Пошук риси: «Tough», «Пильний»…"
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <ul className="option-list">
        {list.map((feat) => (
          <FeatOption
            key={feat.id}
            feat={feat}
            active={value === feat.id}
            onPick={() => onChange(feat.id)}
          />
        ))}
      </ul>
    </div>
  );
}

function FeatOption({ feat, active, onPick }: { feat: FeatEntry; active: boolean; onPick: () => void }) {
  const [open, setOpen] = useState(false);
  const [entry, setEntry] = useState<{ text: string; prerequisite: string | null } | null>(null);
  useEffect(() => {
    if (!open || entry) return;
    let alive = true;
    void fetchEntry(feat.id)
      .then((full) => {
        const prerequisite = full.data?.prerequisite;
        if (alive) {
          setEntry({
            text: full.text_uk || full.text_en || "",
            prerequisite: typeof prerequisite === "string" ? prerequisite : null,
          });
        }
      })
      .catch(() => {
        if (alive) setEntry({ text: "", prerequisite: null });
      });
    return () => {
      alive = false;
    };
  }, [open, entry, feat.id]);
  return (
    <li className={`option ${active ? "option--active" : ""}`}>
      <div className="option__head">
        <button type="button" className="option__pick" aria-pressed={active} onClick={onPick}>
          <span className="option__mark" aria-hidden="true">{active ? "✓" : ""}</span>
          <span className="option__name">
            {feat.name_uk ? withEnglish(feat.name_en, feat.name_uk) : featLabel(feat.name_en)}
          </span>
        </button>
        <span className="option__meta">{sourceLabel(feat.source_id)}</span>
      </div>
      <details className="option__details" onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary>Що дає</summary>
        {!entry ? <p className="meta">Читаємо опис…</p> : null}
        {entry?.prerequisite ? (
          <p className="tag tag--key">Вимога: {entry.prerequisite}</p>
        ) : null}
        {entry?.text ? <RuleText text={entry.text} /> : null}
        {entry && !entry.text ? <p className="meta">Опису в довіднику немає.</p> : null}
      </details>
    </li>
  );
}

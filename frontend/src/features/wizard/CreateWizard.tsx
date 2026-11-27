/** Оболонка візарда: навігація кроками, збереження, фініш.
 *
 * Стан одного кроку лежить на сервері: кожен «Далі» — це `PUT`, який або
 * зберігає відповідь, або повертає причину відмови. Тому «назад» не втрачає
 * нічого, а перезавантаження сторінки не починає створення заново.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { StepJumpBar } from "./StepJumpBar";
import { ActiveGloss, GlossProvider, Term } from "../../components/Term";
import {
  ABILITY_SHORT,
  STEP_LABELS,
  STEP_ORDER,
  abilityModifier,
  classGuide,
  modifierLabel,
} from "../../labels";
import { finishDraft, readDraft, readStep, startWizard, writeStep } from "../../api";
import {
  AbilitiesStep,
  BackgroundStep,
  ClassStep,
  EquipmentStep,
  SpeciesStep,
  SpellsStep,
} from "./steps";
import type {
  AbilitiesOptions,
  BackgroundOptions,
  ClassView,
  EquipmentOptions,
  SpeciesView,
  SpellsOptions,
  StepView,
  DraftView,
} from "./types";
import { speciesLabel, termLabel, titleCaseKey } from "../character/uk";

function messageOf(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

//: Чернетка живе на сервері, а її id — у браузері: так перезавантаження
//: сторінки не починає створення заново.
const DRAFT_KEY = "dndsheet.draft";

export function CreateWizard({ onFinished }: { onFinished: (characterId: string) => void }) {
  const [draftId, setDraftId] = useState<string | null>(null);
  const [step, setStep] = useState<string>("species");
  const [view, setView] = useState<StepView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(true);
  const [classEquipment, setClassEquipment] = useState<string | null>(null);
  const rootRef = useRef<HTMLElement | null>(null);
  const shownStep = useRef<string | null>(null);
  const [body, setBody] = useState<HTMLDivElement | null>(null);

  // Новий крок починається згори: інакше «Далі» лишає гравця внизу нового
  // кроку (кнопка була внизу попереднього) і гортати доводиться самому.
  useEffect(() => {
    if (!view) return;
    if (shownStep.current !== null && shownStep.current !== step) {
      const top = rootRef.current ? rootRef.current.getBoundingClientRect().top + window.scrollY - 8 : 0;
      window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
    }
    shownStep.current = step;
  }, [step, view]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const saved = window.localStorage.getItem(DRAFT_KEY);
        if (saved) {
          try {
            const { draft } = await readDraft(saved);
            const target = draft.next_step ?? STEP_ORDER[STEP_ORDER.length - 1];
            const payload = await readStep(saved, target);
            if (cancelled) return;
            setDraftId(saved);
            setStep(target);
            setView(payload);
            return;
          } catch {
            window.localStorage.removeItem(DRAFT_KEY);
          }
        }
        const started = await startWizard();
        if (cancelled) return;
        window.localStorage.setItem(DRAFT_KEY, started.draft.id);
        setDraftId(started.draft.id);
        setStep(started.step);
        setView(started);
      } catch (failure) {
        if (!cancelled) setError(messageOf(failure));
      } finally {
        if (!cancelled) setStarting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async (id: string, next: string) => {
    setBusy(true);
    setError(null);
    try {
      const payload = await readStep(id, next);
      setStep(next);
      setView(payload);
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setBusy(false);
    }
  }, []);

  const submit = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!draftId) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await writeStep(draftId, step, payload);
        window.localStorage.setItem(DRAFT_KEY, draftId);
        setView(updated);
        const index = STEP_ORDER.indexOf(step as (typeof STEP_ORDER)[number]);
        const next = STEP_ORDER[index + 1];
        if (next) {
          await load(draftId, next);
          return;
        }
        // Останній крок: «Далі» означає «створити персонажа». Раніше тут не
        // було наступного кроку, і кнопка мовчки нічого не робила.
        const finished = await finishDraft(draftId);
        window.localStorage.removeItem(DRAFT_KEY);
        onFinished(finished.character_id);
      } catch (failure) {
        setError(messageOf(failure));
      } finally {
        setBusy(false);
      }
    },
    [draftId, step, load, onFinished],
  );

  async function finish() {
    if (!draftId) return;
    setBusy(true);
    setError(null);
    try {
      const finished = await finishDraft(draftId);
      window.localStorage.removeItem(DRAFT_KEY);
      onFinished(finished.character_id);
    } catch (failure) {
      setError(messageOf(failure));
      setBusy(false);
    }
  }

  // Стартове спорядження класу живе в тексті глави класу (крок «Клас» уже
  // його має) — на кроці «Спорядження» показуємо той самий текст.
  const classKey = view?.draft.answers.class?.class_key ?? null;
  useEffect(() => {
    if (step !== "equipment" || !draftId || !classKey) return;
    let alive = true;
    void readStep<{ classes: ClassView[] }>(draftId, "class")
      .then((payload) => {
        const found = payload.options.classes.find((item) => item.key === classKey);
        const row = found?.feature_texts?.find((feature) => feature.name_en === "Equipment");
        if (alive) setClassEquipment(row ? row.text_uk || row.text : null);
      })
      .catch(() => {
        if (alive) setClassEquipment(null);
      });
    return () => {
      alive = false;
    };
  }, [step, draftId, classKey]);

  async function restart() {
    if (!window.confirm("Почати створення заново? Поточну чернетку буде відкладено.")) return;
    window.localStorage.removeItem(DRAFT_KEY);
    setStarting(true);
    setError(null);
    try {
      const started = await startWizard();
      window.localStorage.setItem(DRAFT_KEY, started.draft.id);
      setDraftId(started.draft.id);
      setStep(started.step);
      setView(started);
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setStarting(false);
    }
  }

  if (starting) return <p className="status">Готуємо чернетку…</p>;
  if (!view) {
    return (
      <p className="status status--error">
        Не вдалося почати створення: {error ?? "невідома помилка"}. Оновіть сторінку; якщо не
        допоможе — перевірте, чи запущено сервер застосунку.
      </p>
    );
  }

  const statuses = new Map(view.draft.steps.map((item) => [item.step, item]));
  const index = STEP_ORDER.indexOf(step as (typeof STEP_ORDER)[number]);
  const previous = index > 0 ? STEP_ORDER[index - 1] : null;
  //: Останній крок сам веде до створення персонажа, тож кнопка в підвалі
  //: тут не потрібна — інакше їх дві.
  const isLastStep = index === STEP_ORDER.length - 1;

  return (
    <GlossProvider>
      <section className="wizard wizard--layout" ref={rootRef}>
        <header className="wizard-header">
          <div>
            <h1>Створення персонажа</h1>
            <p className="meta">
              {view.draft.name || "Без імені"} · правила Книги гравця (2014) · чернетка
              зберігається сама
            </p>
          </div>
          <button type="button" className="link-button" onClick={() => void restart()}>
            Почати заново
          </button>
        </header>

        <nav className="step-rail" aria-label="Кроки створення">
          <ol>
            {STEP_ORDER.map((name, position) => {
              const status = statuses.get(name);
              const classes = [
                "step-chip",
                name === step ? "step-chip--active" : "",
                status?.complete ? "step-chip--done" : "",
                status?.unlocked ? "" : "step-chip--locked",
                status?.optional ? "step-chip--optional" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <li key={name}>
                  <button
                    type="button"
                    className={classes}
                    aria-current={name === step ? "step" : undefined}
                    disabled={!status?.unlocked || busy}
                    title={status?.unlocked ? undefined : "Спершу завершіть попередні кроки"}
                    onClick={() => draftId && void load(draftId, name)}
                  >
                    <span className="step-index">{status?.complete ? "✓" : position + 1}</span>
                    <span className="step-label">
                      {STEP_LABELS[name]}
                      {status?.optional ? <span className="step-note"> необовʼязково</span> : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="wizard-main">
          {error ? (
            <p className="status status--error" role="alert">
              {error}
            </p>
          ) : null}

          <StepJumpBar host={body} step={step} />
          <div className="wizard-body" ref={setBody}>
            {step === "species" ? (
              <SpeciesStep
                answers={view.answers}
                options={view.options as { species: SpeciesView[] }}
                busy={busy}
                onSubmit={submit}
              />
            ) : null}
            {step === "class" ? (
              <ClassStep
                answers={view.answers}
                options={view.options as { classes: ClassView[]; hint?: string }}
                busy={busy}
                onSubmit={submit}
              />
            ) : null}
            {step === "abilities" ? (
              <AbilitiesStep
                answers={view.answers}
                options={view.options as AbilitiesOptions}
                busy={busy}
                onSubmit={submit}
                classKey={classKey}
              />
            ) : null}
            {step === "background" ? (
              <BackgroundStep
                answers={view.answers}
                options={view.options as BackgroundOptions}
                busy={busy}
                onSubmit={submit}
              />
            ) : null}
            {step === "equipment" ? (
              <EquipmentStep
                answers={view.answers}
                options={view.options as EquipmentOptions}
                busy={busy}
                onSubmit={submit}
                classEquipment={classEquipment}
              />
            ) : null}
            {step === "spells" ? (
              <SpellsStep
                answers={view.answers}
                options={view.options as SpellsOptions}
                busy={busy}
                onSubmit={submit}
              />
            ) : null}
          </div>

          <footer className="wizard-footer">
            <div>
              {previous ? (
                <button
                  type="button"
                  className="button"
                  disabled={busy}
                  onClick={() => draftId && void load(draftId, previous)}
                >
                  ← Назад: {STEP_LABELS[previous].toLowerCase()}
                </button>
              ) : null}
            </div>
            <div className="wizard-actions">
              {busy ? <span className="meta">Зберігаємо…</span> : null}
              {view.draft.ready_to_finish && !isLastStep ? (
                <button type="button" className="button button--primary" disabled={busy} onClick={() => void finish()}>
                  Створити персонажа
                </button>
              ) : null}
            </div>
          </footer>
        </div>

        <aside className="margin" aria-label="Ваш персонаж і пояснення">
          <ActiveGloss
            fallback={
              <p className="margin__tip">
                Слова з пунктиром — <Term k="proficiency">терміни</Term>. Натисніть, і тут
                зʼявиться пояснення.
              </p>
            }
          />
          <DraftSummary draft={view.draft} />
        </aside>
      </section>
    </GlossProvider>
  );
}

const SUMMARY_ABILITIES = ["str", "dex", "con", "int", "wis", "cha"] as const;

/** Класи, яким попередження «немає броні» не потрібне. */
const NO_ARMOR_CLASSES = new Set(["wizard", "sorcerer", "monk", "barbarian"]);

/** «Ваш персонаж зараз»: що вже обрано — щоб не тримати це в голові між кроками. */
function DraftSummary({ draft }: { draft: DraftView }) {
  const answers = draft.answers;
  const species = answers.species;
  const classAnswer = answers.class;
  const scores = answers.abilities?.scores ?? {};
  // Бонуси виду рахує бекенд (фіксовані + вибрані + розподіл); старий бекенд — лише розподіл.
  const bonuses: Partial<Record<string, number>> = draft.ability_bonuses ?? species?.ability_spread ?? {};
  const guide = classGuide(classAnswer?.class_key);
  const hasScores = SUMMARY_ABILITIES.some((code) => scores[code]);
  const items = answers.equipment?.items ?? [];
  const spells = answers.spells?.spells ?? [];
  const missing: string[] = [];
  if (!items.some((item) => item.kind === "weapon")) missing.push("немає зброї");
  // Маг, чародій і монах броню не носять (а варвар зазвичай без неї — Захист без броні):
  // попередження про броню їм лише заважало б.
  if (!items.some((item) => item.kind === "armor") && classAnswer?.class_key && !NO_ARMOR_CLASSES.has(classAnswer.class_key)) {
    missing.push("немає броні");
  }

  return (
    <section className="summary">
      <h2 className="summary__title">{draft.name || "Ваш персонаж"}</h2>
      <dl className="facts facts--compact">
        <div className="facts__row">
          <dt>Вид</dt>
          <dd>{species?.species_key ? speciesLabel(titleCaseKey(species.subspecies_key ?? species.species_key)) : "—"}</dd>
        </div>
        <div className="facts__row">
          <dt>Клас</dt>
          <dd>{classAnswer?.class_key ? termLabel(titleCaseKey(classAnswer.class_key)) : "—"}</dd>
        </div>
        <div className="facts__row">
          <dt>Передісторія</dt>
          <dd>
            {answers.background?.custom_background?.name ||
              (answers.background?.background_key ? termLabel(titleCaseKey(answers.background.background_key)) : "—")}
          </dd>
        </div>
      </dl>
      {hasScores ? (
        <ul className="summary__abilities" aria-label="Характеристики з бонусами виду">
          {SUMMARY_ABILITIES.map((code) => {
            const value = (scores[code] ?? 0) + (scores[code] ? bonuses[code] ?? 0 : 0);
            const key = guide?.primary.includes(code);
            return (
              <li key={code} className={key ? "summary__ability--key" : undefined}>
                <span className="summary__abbr">{ABILITY_SHORT[code].toLowerCase()}</span>
                <span className="summary__score">{value || "—"}</span>
                <span className="summary__mod">{value ? modifierLabel(abilityModifier(value)) : ""}</span>
              </li>
            );
          })}
        </ul>
      ) : null}
      <p className="meta">
        Предметів: {items.length} · заклять: {spells.length}
      </p>
      {answers.equipment?.submitted && missing.length ? (
        <p className="summary__warn">Перевірте: {missing.join(", ")}.</p>
      ) : null}
    </section>
  );
}

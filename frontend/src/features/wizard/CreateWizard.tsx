/** Оболонка візарда: навігація кроками, збереження, фініш.
 *
 * Стан одного кроку лежить на сервері: кожен «Далі» — це `PUT`, який або
 * зберігає відповідь, або повертає причину відмови. Тому «назад» не втрачає
 * нічого, а перезавантаження сторінки не починає створення заново.
 */

import { useCallback, useEffect, useState } from "react";

import { STEP_LABELS, STEP_ORDER } from "../../labels";
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
} from "./types";

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
        if (next) await load(draftId, next);
      } catch (failure) {
        setError(messageOf(failure));
      } finally {
        setBusy(false);
      }
    },
    [draftId, step, load],
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

  async function restart() {
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
        Не вдалося почати створення: {error ?? "невідома помилка"}
      </p>
    );
  }

  const statuses = new Map(view.draft.steps.map((item) => [item.step, item]));
  const index = STEP_ORDER.indexOf(step as (typeof STEP_ORDER)[number]);
  const previous = index > 0 ? STEP_ORDER[index - 1] : null;

  return (
    <section className="wizard">
      <header className="wizard-header">
        <div>
          <h1>Створення персонажа</h1>
          <p className="meta">
            {view.draft.name || "без імені"} · ревізія {view.draft.revision} · правила 2014
          </p>
          <button type="button" className="link-button" onClick={() => void restart()}>
            почати заново
          </button>
        </div>
        <ol className="wizard-progress">
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
                  disabled={!status?.unlocked || busy}
                  onClick={() => draftId && void load(draftId, name)}
                >
                  <span className="step-index">{position + 1}</span>
                  {STEP_LABELS[name]}
                </button>
              </li>
            );
          })}
        </ol>
      </header>

      {error ? <p className="status status--error">{error}</p> : null}

      <div className="wizard-body">
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
              ← Назад
            </button>
          ) : null}
        </div>
        <div className="wizard-actions">
          {busy ? <span className="meta">Зберігаємо…</span> : null}
          {view.draft.ready_to_finish ? (
            <button type="button" className="button button--primary" disabled={busy} onClick={() => void finish()}>
              Створити персонажа
            </button>
          ) : null}
        </div>
      </footer>
    </section>
  );
}

/** Власні вміння: те, що є за столом, але немає в книгах.
 *
 * Дар майстра, сила предмета, домашнє правило — текст пише гравець, лист
 * позначає його «власне» і не вдає книжковим. Чисел із нього лист не виводить;
 * єдине — лічильник «N разів на відпочинок», який живе разом із ресурсами класу
 * (його відновлює відпочинок на сервері).
 */
import { useState } from "react";

import type { CustomFeatureBody } from "../../api";
import type { SheetCustomFeature } from "../wizard/types";

import { RuleText } from "./panels";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function rechargeLabel(recharge: SheetCustomFeature["recharge"]): string {
  return recharge === "short" ? "короткий або тривалий відпочинок" : "тривалий відпочинок";
}

/** «дар майстра · 3 рівень · 2 / тривалий відпочинок» під назвою вміння. */
export function customFeatureMeta(feature: SheetCustomFeature): string {
  return [
    feature.origin ?? "",
    feature.level ? `${feature.level} рівень` : "",
    feature.uses ? `${feature.uses} / ${rechargeLabel(feature.recharge)}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

export function CustomFeaturesPanel({
  features,
  busy,
  onAdd,
  onUpdate,
  onRemove,
}: {
  features: SheetCustomFeature[];
  busy: boolean;
  onAdd: (feature: CustomFeatureBody) => Promise<boolean>;
  onUpdate: (featureId: string, fields: CustomFeatureBody) => Promise<boolean>;
  onRemove: (feature: SheetCustomFeature) => Promise<boolean>;
}) {
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  return (
    <div className="custom-features">
      {features.length ? (
        <ul className="feature-list feature-list--rich">
          {features.map((feature) =>
            editing === feature.id ? (
              <li key={feature.id}>
                <CustomFeatureForm
                  title="Змінити власне вміння"
                  initial={feature}
                  busy={busy}
                  onSubmit={async (body) => {
                    const ok = await onUpdate(feature.id, body);
                    if (ok) setEditing(null);
                    return ok;
                  }}
                  onCancel={() => setEditing(null)}
                />
              </li>
            ) : (
              <li key={feature.id}>
                <details className="feature feature--custom">
                  <summary className="feature__summary">
                    <span className="feature-name">{feature.name}</span>
                    <span className="spell-tag spell-tag--custom">власне</span>
                    <span className="feature-meta">{customFeatureMeta(feature)}</span>
                    <span className="feature__chevron" aria-hidden>
                      ▾
                    </span>
                  </summary>
                  {feature.text ? <RuleText text={feature.text} /> : <p className="hint">Без тексту.</p>}
                  <div className="custom-features__actions">
                    <button
                      type="button"
                      className="button"
                      disabled={busy}
                      onClick={() => {
                        setAdding(false);
                        setEditing(feature.id);
                      }}
                    >
                      Змінити
                    </button>
                    <button
                      type="button"
                      className="button button--quiet"
                      disabled={busy}
                      onClick={() => {
                        if (window.confirm(`Прибрати власне вміння «${feature.name}»?`)) void onRemove(feature);
                      }}
                    >
                      Прибрати
                    </button>
                  </div>
                </details>
              </li>
            ),
          )}
        </ul>
      ) : null}

      {adding ? (
        <CustomFeatureForm
          title="Власне вміння"
          busy={busy}
          onSubmit={async (body) => {
            const ok = await onAdd(body);
            if (ok) setAdding(false);
            return ok;
          }}
          onCancel={() => setAdding(false)}
        />
      ) : (
        <button
          type="button"
          className="button custom-features__open"
          disabled={busy}
          onClick={() => {
            setEditing(null);
            setAdding(true);
          }}
        >
          + Додати власне вміння
        </button>
      )}
    </div>
  );
}

/** Форма вміння: назва й текст, за бажанням — звідки, рівень і лічильник. */
export function CustomFeatureForm({
  title,
  initial,
  busy,
  onSubmit,
  onCancel,
}: {
  title: string;
  initial?: SheetCustomFeature;
  busy: boolean;
  onSubmit: (body: CustomFeatureBody) => Promise<boolean>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [origin, setOrigin] = useState(initial?.origin ?? "");
  const [level, setLevel] = useState<number | null>(initial?.level ?? null);
  const [text, setText] = useState(initial?.text ?? "");
  const [uses, setUses] = useState(initial?.uses ? String(initial.uses) : "");
  const [recharge, setRecharge] = useState<"short" | "long">(initial?.recharge ?? "long");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!name.trim()) {
      setError("Впишіть назву вміння");
      return;
    }
    const count = uses.trim() ? Number(uses) : null;
    if (count !== null && (!Number.isInteger(count) || count < 1 || count > 99)) {
      setError("Скільки разів — ціле число від 1 до 99 (або порожньо, якщо без лічильника)");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const ok = await onSubmit({
        name: name.trim(),
        text: text.trim(),
        origin: origin.trim() || null,
        level,
        uses: count,
        recharge: count === null ? null : recharge,
      });
      if (!ok) setError("Не вдалося зберегти вміння");
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="inv-form custom-form">
      <p className="inv-form__title">{title}</p>
      <div className="inv-form__grid">
        <label className="field inv-form__wide">
          Назва
          <input
            className="inv-search__input"
            value={name}
            maxLength={120}
            placeholder="Наприклад, «Око ворона»"
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="field">
          Звідки
          <input
            className="inv-search__input"
            value={origin}
            maxLength={120}
            placeholder="дар майстра, предмет…"
            onChange={(event) => setOrigin(event.target.value)}
          />
        </label>
        <label className="field">
          З рівня
          <select
            className="select"
            value={level ?? ""}
            onChange={(event) => setLevel(event.target.value ? Number(event.target.value) : null)}
          >
            <option value="">—</option>
            {Array.from({ length: 20 }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Скільки разів
          <input
            className="inv-search__input"
            inputMode="numeric"
            value={uses}
            placeholder="без лічильника"
            onChange={(event) => setUses(event.target.value.replace(/\D/g, "").slice(0, 2))}
          />
        </label>
        <label className="field">
          Відновлюється
          <select
            className="select"
            value={recharge}
            disabled={!uses.trim()}
            onChange={(event) => setRecharge(event.target.value === "short" ? "short" : "long")}
          >
            <option value="long">тривалий відпочинок</option>
            <option value="short">короткий відпочинок</option>
          </select>
        </label>
        <label className="field inv-form__wide">
          Текст (що робить)
          <textarea
            className="spell-add__text"
            rows={4}
            maxLength={4000}
            value={text}
            placeholder="Своїми словами: що дає, коли діє. Це побачить лист і PDF."
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <p className="hint inv-form__wide">
          Лист покаже це вміння з позначкою «власне» і не рахує з нього чисел. Якщо вказати «скільки разів», лічильник
          з’явиться серед ресурсів, і відпочинок відновить його.
        </p>
      </div>

      {error ? <p className="status status--error">{error}</p> : null}

      <div className="inv-form__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={saving || busy}
          onClick={() => void submit()}
        >
          {saving ? "Зберігаємо…" : "Зберегти"}
        </button>
        <button type="button" className="button" onClick={onCancel}>
          Скасувати
        </button>
      </div>
    </section>
  );
}

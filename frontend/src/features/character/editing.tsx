/** Дрібні елементи редагування на місці.
 *
 * Клік по числу відкриває поле; збереження одразу летить на сервер. Обчислене
 * поле, змінене вручну, позначається крапкою й кнопкою «↺», яка скидає
 * виправлення — інакше гравець не зрозуміє, чому КЗ перестав рахуватися.
 *
 * `NumberField` — навпаки, завжди видиме поле зі степперами: ним вводять те,
 * що не є похідним числом листа (скільки хітів зняти, кидок кості хітів,
 * кількість предметів). Браузерні стрілочки навмисно вимкнені: на темній
 * дошці вони виглядають чужорідно й на дотику майже не працюють.
 */

import { useEffect, useRef, useState } from "react";

export function EditableNumber({
  value,
  title,
  overridden = false,
  onSave,
  onReset,
  suffix = "",
  min = -30,
  max = 999,
  size = "md",
}: {
  value: number;
  title: string;
  overridden?: boolean;
  onSave: (value: number) => void;
  onReset?: () => void;
  suffix?: string;
  min?: number;
  max?: number;
  size?: "md" | "lg";
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setDraft(String(value));
  }, [value]);
  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  function commit() {
    const parsed = Number(draft);
    setEditing(false);
    if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
      setDraft(String(value));
      return;
    }
    const rounded = Math.round(parsed);
    if (rounded !== value) onSave(rounded);
  }

  return (
    <span className={`editable editable--${size} ${overridden ? "editable--override" : ""}`}>
      {editing ? (
        <input
          ref={inputRef}
          className="editable-input"
          type="text"
          inputMode="numeric"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
            if (event.key === "Escape") {
              setDraft(String(value));
              setEditing(false);
            }
          }}
          aria-label={title}
        />
      ) : (
        <button
          type="button"
          className="editable-value"
          title={`${title}. Клік — змінити`}
          onClick={() => setEditing(true)}
        >
          {value}
          {suffix}
        </button>
      )}
      {overridden && onReset ? (
        <button type="button" className="editable-reset" title="Скинути виправлення" onClick={onReset}>
          ↺
        </button>
      ) : null}
    </span>
  );
}

/** Числове поле зі степперами: − [значення] +, з підписом і суфіксом. */
export function NumberField({
  value,
  onChange,
  min = 0,
  max = 999,
  step = 1,
  title,
  suffix = "",
  disabled = false,
  live = false,
  size = "md",
}: {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  title: string;
  suffix?: string;
  disabled?: boolean;
  /** true — віддавати кожне валідне натискання (локальний стан), false — на blur/Enter. */
  live?: boolean;
  size?: "sm" | "md";
}) {
  const [draft, setDraft] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setDraft(String(value));
  }, [value, focused]);

  const clamp = (next: number) => Math.min(max, Math.max(min, Math.round(next)));

  function parse(text: string): number | null {
    const trimmed = text.trim().replace(",", ".");
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function handleInput(text: string) {
    setDraft(text);
    if (!live) return;
    const parsed = parse(text);
    if (parsed === null) return;
    const next = clamp(parsed);
    if (next !== value) onChange(next);
  }

  function commit() {
    setFocused(false);
    const parsed = parse(draft);
    if (parsed === null) {
      setDraft(String(value));
      return;
    }
    const next = clamp(parsed);
    setDraft(String(next));
    if (next !== value) onChange(next);
  }

  function nudge(delta: number) {
    const next = clamp(value + delta);
    if (next === value) return;
    setDraft(String(next));
    onChange(next);
  }

  return (
    <span className={`numfield numfield--${size} ${disabled ? "is-disabled" : ""}`}>
      <button
        type="button"
        className="numfield__btn"
        title={`${title}: −${step}`}
        aria-label={`${title}: менше`}
        disabled={disabled || value <= min}
        onClick={() => nudge(-step)}
      >
        −
      </button>
      <span className="numfield__box">
        <input
          className="numfield__input"
          type="text"
          inputMode="numeric"
          value={draft}
          disabled={disabled}
          aria-label={title}
          onFocus={() => setFocused(true)}
          onChange={(event) => handleInput(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              commit();
              event.currentTarget.blur();
            }
            if (event.key === "Escape") {
              setDraft(String(value));
              event.currentTarget.blur();
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              nudge(step);
            }
            if (event.key === "ArrowDown") {
              event.preventDefault();
              nudge(-step);
            }
          }}
        />
        {suffix ? <span className="numfield__suffix">{suffix}</span> : null}
      </span>
      <button
        type="button"
        className="numfield__btn"
        title={`${title}: +${step}`}
        aria-label={`${title}: більше`}
        disabled={disabled || value >= max}
        onClick={() => nudge(step)}
      >
        +
      </button>
    </span>
  );
}

export function Counter({
  used,
  total,
  title,
  onChange,
}: {
  used: number;
  total: number;
  title: string;
  onChange: (used: number) => void;
}) {
  return (
    <span className="counter">
      <span className="counter-value">
        {total - used} / {total}
      </span>
      <button
        type="button"
        className="counter-btn counter-btn--use"
        disabled={used >= total}
        onClick={() => onChange(used + 1)}
        title={`${title}: витратити`}
      >
        Використати
      </button>
      <button
        type="button"
        className="counter-btn"
        disabled={used <= 0}
        onClick={() => onChange(used - 1)}
        title={`${title}: повернути`}
      >
        Відновити
      </button>
    </span>
  );
}

export function Pips({
  count,
  max,
  title,
  onChange,
}: {
  count: number;
  max: number;
  title: string;
  onChange: (value: number) => void;
}) {
  return (
    <span className="pips" aria-label={title}>
      {Array.from({ length: max }, (_, index) => (
        <button
          key={index}
          type="button"
          className={`pip ${index < count ? "pip--on" : ""}`}
          aria-label={`${title}: ${index + 1}`}
          onClick={() => onChange(index + 1 === count ? index : index + 1)}
        />
      ))}
    </span>
  );
}

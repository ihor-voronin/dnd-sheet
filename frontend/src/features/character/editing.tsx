/** Дрібні елементи редагування на місці.
 *
 * Клік по числу відкриває поле; збереження одразу летить на сервер. Обчислене
 * поле, змінене вручну, позначається крапкою й кнопкою «↺», яка скидає
 * виправлення — інакше гравець не зрозуміє, чому КЗ перестав рахуватися.
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
}: {
  value: number;
  title: string;
  overridden?: boolean;
  onSave: (value: number) => void;
  onReset?: () => void;
  suffix?: string;
  min?: number;
  max?: number;
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
    <span className={`editable ${overridden ? "editable--override" : ""}`}>
      {editing ? (
        <input
          ref={inputRef}
          className="editable-input"
          type="number"
          value={draft}
          min={min}
          max={max}
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
          title={`${title}. Клік — виправити вручну`}
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
      <button
        type="button"
        className="counter-button"
        disabled={used <= 0}
        onClick={() => onChange(used - 1)}
        title={`Повернути (${title})`}
      >
        −
      </button>
      <span className="counter-value">
        {total - used} / {total}
      </span>
      <button
        type="button"
        className="counter-button"
        disabled={used >= total}
        onClick={() => onChange(used + 1)}
        title={`Витратити (${title})`}
      >
        +
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

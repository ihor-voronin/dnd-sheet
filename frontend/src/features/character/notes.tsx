/** Нотатки персонажа: розділи з автозбереженням і лічильниками.
 *
 * Нотатки — вільний текст, але за столом їх пишуть часто й потроху. Тому:
 * поле саме виростає під текст, зміни йдуть на сервер через паузу (без
 * кнопки «зберегти»), а поруч видно, скільки слів і чи вже збережено.
 * «Очистити» — у два кліки, щоб не втратити розділ випадково.
 */

import { useEffect, useRef, useState } from "react";

import { inTelegram } from "../../telegram";

export type NoteStatus = "idle" | "saving" | "saved" | "error";

export const NOTE_SECTIONS: { key: string; label: string; hint: string }[] = [
  {
    key: "allies",
    label: "Союзники",
    hint: "хто поруч, чим корисний, де його шукати",
  },
  {
    key: "enemies",
    label: "Вороги",
    hint: "кому ви винні, хто полює на вас",
  },
  {
    key: "backstory",
    label: "Передісторія",
    hint: "що було до пригод",
  },
  {
    key: "notes",
    label: "Нотатки",
    hint: "плани, зачіпки, здобич, усе інше",
  },
];

/** Поле нотатки, яке саме виростає під текст. */
export function NoteArea({
  value,
  onChange,
  placeholder,
  minHeight = 120,
  rows = 6,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minHeight?: number;
  rows?: number;
  label: string;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.max(minHeight, element.scrollHeight)}px`;
  }, [value, minHeight]);

  return (
    <textarea
      ref={ref}
      className="note-area"
      rows={rows}
      value={value}
      placeholder={placeholder}
      aria-label={label}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function counts(text: string): { words: number; chars: number } {
  const trimmed = text.trim();
  return {
    words: trimmed ? trimmed.split(/\s+/).length : 0,
    chars: text.length,
  };
}

function plural(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

export function notesStatusText(
  status: NoteStatus,
  savedAt: string | null,
): string {
  if (status === "saving") return "Зберігаємо…";
  if (status === "error") return "Не вдалося зберегти — спробуйте ще раз";
  if (status === "saved") return savedAt ? `Збережено о ${savedAt}` : "Збережено";
  return "Зміни зберігаються автоматично";
}

export function NotesPanel({
  notes,
  status,
  savedAt,
  onUpdate,
  onSaveNow,
  onExport,
}: {
  notes: Record<string, string>;
  status: NoteStatus;
  savedAt: string | null;
  onUpdate: (key: string, value: string) => void;
  onSaveNow: () => void;
  onExport: () => void;
}) {
  const [confirmKey, setConfirmKey] = useState<string | null>(null);

  return (
    <div className="notes-panel">
      <div className="notes-toolbar">
        <span className={`notes-status notes-status--${status}`} role="status">
          {notesStatusText(status, savedAt)}
        </span>
        <span className="notes-toolbar__actions">
          {/* У Telegram webview не зберігає файли з браузера — кнопка там нічого б не зробила. */}
          {inTelegram ? null : (
            <button
              type="button"
              className="note-tool"
              onClick={onExport}
              title="Завантажити всі розділи як Markdown"
            >
              Експорт .md
            </button>
          )}
          <button
            type="button"
            className="note-tool"
            onClick={onSaveNow}
            disabled={status === "saving"}
          >
            Зберегти зараз
          </button>
        </span>
      </div>

      <div className="notes-grid notes-grid--rich">
        {NOTE_SECTIONS.map((section) => {
          const value = notes[section.key] ?? "";
          const { words, chars } = counts(value);
          return (
            <section key={section.key} className="note-card">
              <header className="note-card__head">
                <span className="note-card__label">{section.label}</span>
                <span className="note-card__count">
                  {words} {plural(words, "слово", "слова", "слів")} · {chars}{" "}
                  {plural(chars, "символ", "символи", "символів")}
                </span>
              </header>
              <NoteArea
                label={section.label}
                value={value}
                placeholder={section.hint}
                onChange={(next) => onUpdate(section.key, next)}
              />
              <footer className="note-card__actions">
                {confirmKey === section.key ? (
                  <>
                    <button
                      type="button"
                      className="note-clear note-clear--danger"
                      onClick={() => {
                        onUpdate(section.key, "");
                        setConfirmKey(null);
                      }}
                    >
                      точно очистити?
                    </button>
                    <button
                      type="button"
                      className="note-clear"
                      onClick={() => setConfirmKey(null)}
                    >
                      скасувати
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="note-clear"
                    disabled={!value}
                    onClick={() => setConfirmKey(section.key)}
                  >
                    очистити
                  </button>
                )}
              </footer>
            </section>
          );
        })}
      </div>
    </div>
  );
}

/** Кнопка експорту всіх розділів у Markdown-файл. */
export function downloadNotes(
  notes: Record<string, string>,
  name: string,
  sections: { key: string; label: string }[],
): void {
  const body = sections
    .map((section) => {
      const text = (notes[section.key] ?? "").trim();
      return `## ${section.label}\n\n${text || "—"}`;
    })
    .join("\n\n");
  const blob = new Blob([`# ${name} — нотатки\n\n${body}\n`], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${name} — нотатки.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

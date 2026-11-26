/** Закляття під час гри: денна підготовка й додавання поза рівнем.

 * Дві різні дії, які й у книзі різні:
 *
 * * **підготувати** (PHB, p. 201) — на день вибрати набір зі списку класу,
 *   не більше ніж «модифікатор + рівень»; учорашній набір замінюється;
 * * **додати** — взяти закляття в лист (зі списку класу) або вписати своє,
 *   якого немає в книзі. Власне позначається словом «власне» і не вдає
 *   книжкове: довідник його не знає, текст дав гравець.
 *
 * Числа не рахуються тут: ліміт і найвищий рівень прийшли з сервера
 * (`spellcasting.classes`), а перевірку все одно робить агрегат.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { fetchClassSpells } from "../../api";
import type { SpellBody } from "../../api";
import type { SheetSpell, SheetSpellcasting } from "../wizard/types";
import { spellLabel, termLabel } from "./uk";

type CastingClass = SheetSpellcasting["classes"][number];

type Pick = { name_en: string; level: number; entry_id: string | null };

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function levelLabel(level: number): string {
  return level === 0 ? "заговір" : `${level} рівень`;
}

function spellLevelOf(entry: { data: Record<string, unknown> }): number {
  return Number(entry.data.level ?? 0);
}

/** Ліміт і найвищий рівень — з сервера, не з клієнта. */
function preparedLimit(item: CastingClass): number {
  return item.prepared_limit ?? 0;
}

// ---------------------------------------------------------------------------
// денна підготовка
// ---------------------------------------------------------------------------

export function SpellsPreparePanel({
  casting,
  spells,
  busy,
  onSave,
}: {
  casting: SheetSpellcasting;
  spells: SheetSpell[];
  busy: boolean;
  onSave: (classKey: string, picks: Pick[]) => Promise<boolean>;
}) {
  const preparing = casting.classes.filter((item) => item.prepares && item.prepared_limit !== null);
  if (!preparing.length) return null;

  return (
    <>
      <h3 className="ddb-work__title">
        <span>Підготовка на день</span>
        <span className="short">зі списку класу</span>
      </h3>
      {preparing.map((item) => (
        <PreparedClass
          key={item.key}
          casting={item}
          spells={spells}
          busy={busy}
          onSave={onSave}
        />
      ))}
    </>
  );
}

function PreparedClass({
  casting,
  spells,
  busy,
  onSave,
}: {
  casting: CastingClass;
  spells: SheetSpell[];
  busy: boolean;
  onSave: (classKey: string, picks: Pick[]) => Promise<boolean>;
}) {
  const own = spells.filter((spell) => spell.class_key === casting.key);
  const learned = own.filter((spell) => spell.level > 0 && !spell.custom);
  const cantrips = own.filter((spell) => spell.level === 0);
  const custom = own.filter((spell) => spell.custom);
  const preparedNames = learned.filter((spell) => spell.prepared).map((spell) => spell.name_en);
  const signature = preparedNames.slice().sort().join("|");

  const [selected, setSelected] = useState<string[]>(preparedNames);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Після збереження сервер повертає новий лист — підтягуємо його набір.
  useEffect(() => {
    setSelected(signature ? signature.split("|") : []);
  }, [signature]);

  const list = useQuery({
    queryKey: ["class-spells", casting.key, casting.max_spell_level],
    queryFn: () => fetchClassSpells(casting.key, casting.max_spell_level),
  });

  const options = useMemo(() => {
    const map = new Map<string, Pick>();
    for (const entry of list.data?.items ?? []) {
      const level = spellLevelOf(entry);
      // Заговори не готують: вони змінюються лише з рівнем.
      if (level === 0) continue;
      map.set(entry.name_en.toLocaleLowerCase(), {
        name_en: entry.name_en,
        level,
        entry_id: entry.id,
      });
    }
    // Те, що вже є в листі (підклас, давній вибір), теж має бути у списку.
    for (const spell of learned) {
      map.set(spell.name_en.toLocaleLowerCase(), {
        name_en: spell.name_en,
        level: spell.level,
        entry_id: spell.entry_id,
      });
    }
    return Array.from(map.values()).sort(
      (left, right) => left.level - right.level || left.name_en.localeCompare(right.name_en),
    );
  }, [list.data, learned]);

  const needle = query.trim().toLocaleLowerCase();
  const visible = needle
    ? options.filter(
        (option) =>
          option.name_en.toLocaleLowerCase().includes(needle) ||
          spellLabel(option.name_en).toLocaleLowerCase().includes(needle),
      )
    : options;

  const limit = preparedLimit(casting);
  // Власні закляття теж займають місце в ліміті — рахуємо їх одразу, інакше
  // «обрано 0/1» дозволяло б зберегти набір, який сервер відхилить.
  const occupiedByCustom = custom.filter((item) => item.prepared).length;
  const used = selected.length + occupiedByCustom;
  const over = used > limit;

  function toggle(nameEn: string) {
    setError(null);
    setSelected((current) =>
      current.includes(nameEn)
        ? current.filter((item) => item !== nameEn)
        : [...current, nameEn],
    );
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const picks = selected
        .map((name) => options.find((option) => option.name_en === name))
        .filter((option): option is Pick => Boolean(option));
      const ok = await onSave(casting.key, picks);
      if (!ok) setError("Не вдалося зберегти підготовку");
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="spell-prep">
      <header className="spell-prep__head">
        <span className="spell-prep__class">{termLabel(casting.name_en)}</span>
        <span className={`spell-prep__count ${over ? "is-over" : ""}`}>
          {occupiedByCustom
            ? `обрано ${selected.length} + власних ${occupiedByCustom} / ${limit}`
            : `обрано ${selected.length} / ${limit}`}
        </span>
      </header>

      <div className="spell-prep__tools">
        <input
          className="inv-search__input"
          type="search"
          value={query}
          placeholder={`Пошук у списку ${termLabel(casting.name_en)}…`}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button
          type="button"
          className="button button--primary"
          disabled={saving || busy || over}
          onClick={() => void save()}
        >
          {saving ? "Зберігаємо…" : "Зберегти підготовку"}
        </button>
      </div>

      {error ? <p className="status status--error">{error}</p> : null}
      {list.isPending ? <p className="hint">Читаємо список класу…</p> : null}
      {list.error ? (
        <p className="hint hint--warn">Список не завантажився: {messageOf(list.error)}</p>
      ) : null}

      <div className="spell-prep__list">
        {visible.map((option) => (
          <label
            key={option.name_en}
            className={`chip chip--row ${selected.includes(option.name_en) ? "chip--active" : ""}`}
          >
            <input
              type="checkbox"
              checked={selected.includes(option.name_en)}
              onChange={() => toggle(option.name_en)}
            />
            <span>{spellLabel(option.name_en)}</span>
            <span className="meta">{levelLabel(option.level)}</span>
          </label>
        ))}
        {!visible.length && !list.isPending ? (
          <p className="hint">Нічого не знайшли — змініть пошук.</p>
        ) : null}
      </div>

      {over ? (
        <p className="hint hint--warn">
          Більше, ніж клас готує на день: приберіть {used - limit} — сервер інакше
          відмовить.
        </p>
      ) : null}

      {cantrips.length ? (
        <p className="hint">
          Заговори не змінюються підготовкою: {cantrips.map((item) => spellLabel(item.name_en)).join(", ")}.
        </p>
      ) : null}
      {custom.length ? (
        <p className="hint">
          Власні закляття завжди доступні й займають місце в ліміті:{" "}
          {custom.map((item) => item.name_en).join(", ")}.
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// додати закляття
// ---------------------------------------------------------------------------

export function AddSpellForm({
  casting,
  busy,
  onAdd,
}: {
  casting: SheetSpellcasting;
  busy: boolean;
  onAdd: (spell: SpellBody) => Promise<boolean>;
}) {
  const classes = casting.classes;
  const [open, setOpen] = useState(false);
  const [classKey, setClassKey] = useState(classes[0]?.key ?? "");
  const [custom, setCustom] = useState(false);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<Pick | null>(null);
  const [name, setName] = useState("");
  const [level, setLevel] = useState(1);
  const [description, setDescription] = useState("");
  const [prepared, setPrepared] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const current = classes.find((item) => item.key === classKey) ?? classes[0];
  const list = useQuery({
    queryKey: ["class-spells", classKey, current?.max_spell_level ?? 0],
    queryFn: () => fetchClassSpells(classKey, current?.max_spell_level ?? 0),
    enabled: open && !custom && Boolean(classKey),
  });

  if (!classes.length) return null;

  function reset() {
    setPicked(null);
    setName("");
    setLevel(1);
    setDescription("");
    setQuery("");
    setError(null);
    setPrepared(Boolean(current?.prepares));
  }

  function openForm() {
    reset();
    setOpen(true);
  }

  const needle = query.trim().toLocaleLowerCase();
  const options = (list.data?.items ?? [])
    .map((entry) => ({
      name_en: entry.name_en,
      level: spellLevelOf(entry),
      entry_id: entry.id,
    }))
    .filter((entry) => !needle || spellLabel(entry.name_en).toLocaleLowerCase().includes(needle) ||
      entry.name_en.toLocaleLowerCase().includes(needle))
    .slice(0, 40);

  async function submit() {
    const finalName = custom ? name.trim() : picked?.name_en ?? "";
    if (!finalName) {
      setError(custom ? "Впишіть назву власного закляття" : "Оберіть закляття зі списку");
      return;
    }
    if (custom && level === 0) {
      setError("Власний заговір теж можна додати — оберіть «заговір», якщо це він");
    }
    setSaving(true);
    setError(null);
    try {
      const body: SpellBody = {
        class_key: classKey,
        name_en: finalName,
        level: custom ? level : picked?.level ?? 0,
        entry_id: custom ? null : picked?.entry_id ?? null,
        prepared,
        custom,
        description: custom ? description.trim() || null : null,
      };
      const ok = await onAdd(body);
      if (!ok) {
        setError("Не вдалося додати закляття");
        return;
      }
      setOpen(false);
      reset();
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="button spell-add__open" disabled={busy} onClick={openForm}>
        + закляття
      </button>
    );
  }

  return (
    <section className="inv-form spell-add">
      <p className="inv-form__title">Додати закляття</p>
      <div className="inv-form__grid">
        {classes.length > 1 ? (
          <label className="field">
            Клас
            <select
              className="select"
              value={classKey}
              onChange={(event) => {
                setClassKey(event.target.value);
                setPicked(null);
                setQuery("");
              }}
            >
              {classes.map((item) => (
                <option key={item.key} value={item.key}>
                  {termLabel(item.name_en)}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label className="field inv-form__check inv-form__wide">
          <input
            type="checkbox"
            checked={custom}
            onChange={(event) => {
              setCustom(event.target.checked);
              setPicked(null);
              setError(null);
            }}
          />
          власне закляття (немає в книзі)
        </label>

        {custom ? (
          <>
            <label className="field inv-form__wide">
              Назва
              <input
                className="inv-search__input"
                value={name}
                placeholder="Наприклад, «Благословення столу»"
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="field">
              Рівень
              <select
                className="select"
                value={level}
                onChange={(event) => setLevel(Number(event.target.value))}
              >
                <option value={0}>заговір</option>
                {Array.from({ length: 9 }, (_, index) => index + 1).map((value) => (
                  <option key={value} value={value}>
                    {value} рівень
                  </option>
                ))}
              </select>
            </label>
            <label className="field inv-form__wide">
              Текст (що робить)
              <textarea
                className="spell-add__text"
                rows={3}
                value={description}
                placeholder="Своїми словами: ефект, урон, рятунок. Це побачить лист і PDF."
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
          </>
        ) : (
          <>
            <label className="field inv-form__wide">
              Пошук у списку класу
              <input
                className="inv-search__input"
                type="search"
                value={query}
                placeholder="Частина назви…"
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div className="spell-add__results">
              {list.isPending ? <p className="hint">Читаємо список класу…</p> : null}
              {list.error ? (
                <p className="hint hint--warn">Список не завантажився: {messageOf(list.error)}</p>
              ) : null}
              {options.map((option) => (
                <button
                  key={option.name_en}
                  type="button"
                  className={`chip ${picked?.name_en === option.name_en ? "chip--active" : ""}`}
                  onClick={() => {
                    setPicked(option);
                    setError(null);
                  }}
                >
                  {spellLabel(option.name_en)} · {levelLabel(option.level)}
                </button>
              ))}
              {!options.length && !list.isPending ? (
                <p className="hint">
                  У списку нічого не знайшли. Якщо це ваше закляття — увімкніть «власне».
                </p>
              ) : null}
            </div>
          </>
        )}

        {custom ? (
          <p className="hint inv-form__wide">
            Власне закляття завжди підготовлене: у нього немає списку класу, з
            якого його готувати. Місце в денному ліміті воно займає — якщо місця
            немає, спершу зніміть підготовку з іншого закляття.
          </p>
        ) : (
          <label className="field inv-form__check inv-form__wide">
            <input
              type="checkbox"
              checked={prepared}
              onChange={(event) => setPrepared(event.target.checked)}
            />
            підготовлене зараз
          </label>
        )}
      </div>

      {error ? <p className="status status--error">{error}</p> : null}

      <div className="inv-form__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={saving || busy}
          onClick={() => void submit()}
        >
          {saving ? "Додаємо…" : "Додати"}
        </button>
        <button type="button" className="button" onClick={() => setOpen(false)}>
          Скасувати
        </button>
      </div>
    </section>
  );
}

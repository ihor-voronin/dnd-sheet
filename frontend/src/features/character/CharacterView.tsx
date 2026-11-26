/** Екран персонажа: огляд у дусі D&D Beyond, вкладки, правки на місці.
 *
 * Усі числа приходять із сервера; компонент їх не перераховує. Клік по
 * похідному числу (КЗ, ініціатива, навичка) створює **виправлення** — сервер
 * зберігає його окремо й позначає поле як «вручну», доки гравець не скине.
 * Лічильники (хіти, слоти, хіт-дайси, кидки смерті) — це стан, а не
 * виправлення: кожна зміна одразу йде на диск.
 *
 * Розкладка повторює звичний аркуш D&D Beyond: шапка з портретом, рядок
 * характеристик-гексагонів, далі три колонки — порятунки й володіння,
 * ініціатива з навичками, робоча панель із вкладками.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  addCharacterItem,
  exportUrl,
  fetchRenderers,
  patchCharacter,
  removeCharacterItem,
  restCharacter,
  spendHitDie,
  updateCharacterItem,
} from "../../api";
import type { ItemBody } from "../../api";
import type { RestReport, SheetViewPayload } from "../wizard/types";
import {
  ABILITY_LABELS,
  ALIGNMENT_LABELS,
  abilityLabel,
  damageTypeLabel,
  modifierLabel,
  subclassLabel,
} from "../../labels";
import {
  AbilityHex,
  HexStat,
  PassiveList,
  ProficiencyGroups,
  SavePills,
  SkillTable,
  initials,
} from "./ddb";
import { EditableNumber, NumberField, Pips } from "./editing";
import { HitDiceBlock, HitPointsBlock } from "./hp";
import { InventoryPanel } from "./inventory";
import { NotesPanel, downloadNotes } from "./notes";
import type { NoteStatus } from "./notes";
import { BackgroundPanel } from "./background";
import {
  ActionSpells,
  AttacksTable,
  CastingBlock,
  FeatureResources,
  FeaturesList,
  ProficienciesList,
  SpellsKnownList,
} from "./panels";

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"];

const TABS: { id: string; label: string }[] = [
  { id: "actions", label: "Дії" },
  { id: "spells", label: "Закляття" },
  { id: "inventory", label: "Інвентар" },
  { id: "features", label: "Уміння" },
  { id: "background", label: "Передісторія" },
  { id: "notes", label: "Нотатки" },
];

/** Стандартні дії ходу з правил 2014 — не дані персонажа, а памʼятка.
 * Підказка — короткий переказ правила, щоб не тримати PHB під рукою. */
const COMBAT_ACTIONS: { name: string; hint: string }[] = [
  {
    name: "Атака",
    hint: "Одна атака зброєю або без неї; риси можуть давати більше. Замість атаки — Захват чи Штовханина.",
  },
  {
    name: "Ривок",
    hint: "Додатковий рух на відстань, що дорівнює швидкості, цього ходу.",
  },
  {
    name: "Відхід",
    hint: "Рух без атак можливості від істот, яких ви покидаєте, до кінця ходу.",
  },
  {
    name: "Ухиляння",
    hint: "Атаки по вас — із перешкодою, порятунки СПР — з перевагою; втрачається, якщо не можете діяти.",
  },
  {
    name: "Захват",
    hint: "Особлива атака: ціль рятується СИЛ або СПР; утримуєте її, доки не вивільниться.",
  },
  {
    name: "Допомога",
    hint: "Союзник дістає перевагу на атаку по цілі поруч або на перевірку чи порятунок.",
  },
  {
    name: "Сховатися",
    hint: "Перевірка Скритності проти пасивної Спостережливості; потрібне укриття.",
  },
  {
    name: "Імпровізація",
    hint: "Будь-яка дія поза списком; чи можлива вона й що коштує — вирішує майстер.",
  },
  {
    name: "Вплив",
    hint: "Спроба переконати, обманути, залякати чи розважити істоту.",
  },
  {
    name: "Магія",
    hint: "Чарування закляття з часом «1 дія»; бонусні дії та реакції — окремо.",
  },
  {
    name: "Готовність",
    hint: "Підготувати дію з умовою-тригером; виконується реакцією до початку вашого наступного ходу.",
  },
  {
    name: "Пошук",
    hint: "Перевірка МУД (Спостережливість) або ІНТ (Розслідування), щоб щось знайти.",
  },
  {
    name: "Штовханина",
    hint: "Особлива атака: ціль рятується СИЛ або СПР; відсуваєте на 5 фт або збиваєте з ніг.",
  },
  {
    name: "Вивчення",
    hint: "Перевірка ІНТ (Магія, Історія, Природа чи Релігія), щоб пригадати знання.",
  },
  {
    name: "Використання",
    hint: "Взаємодія з предметом; зазвичай раз за хід безкоштовно, далі — дія.",
  },
];

const NOTE_LABELS: Record<string, string> = {
  appearance: "Зовнішність",
  allies: "Союзники",
  enemies: "Вороги",
  backstory: "Передісторія",
  notes: "Нотатки",
};

function partLabel(raw: string): string {
  if (raw.startsWith("armor:")) return `броня ${raw.slice("armor:".length)}`;
  if (raw === "unarmored") return "без броні";
  if (raw === "dexterity") return "Спритність";
  if (raw === "shield") return "щит";
  if (raw === "bonus") return "бонус";
  if (raw === "override") return "вручну";
  if (raw === "manual-override") return "вписано вручну";
  const max = raw.match(/^level-1-max: (d\d+)$/);
  if (max) return `1 рівень: максимум ${max[1]}`;
  const roll = raw.match(/^level-(\d+)-roll: (d\d+)$/);
  if (roll) return `${roll[1]} рівень: кидок ${roll[2]}`;
  const average = raw.match(/^level-(\d+)-average: (d\d+)$/);
  if (average) return `${average[1]} рівень: середнє ${average[2]}`;
  if (raw.startsWith("unarmored-defense:")) {
    return `безбронний захист (${abilityLabel(raw.split(":")[1])})`;
  }
  return raw;
}

function partList(parts: { label: string; value: number }[]): string {
  return parts.map((part) => `${partLabel(part.label)} ${part.value}`).join(" · ");
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Що саме змінив відпочинок — з відповіді сервера, а не зі стану екрана. */
function describeRest(report: RestReport): string {
  const parts: string[] = [];
  if (report.kind === "long") {
    if (report.hp_before !== report.hp_after) {
      parts.push(`хіти ${report.hp_before} → ${report.hp_after}`);
    }
    if (report.hit_dice_before !== report.hit_dice_after) {
      parts.push(`кістки хитів: витрачено ${report.hit_dice_before} → ${report.hit_dice_after}`);
    }
    if (report.slots_before > 0) parts.push("слоти відновлено");
    if (report.exhaustion_before !== report.exhaustion_after) {
      parts.push(`втома ${report.exhaustion_before} → ${report.exhaustion_after}`);
    }
    if (report.temporary > 0) {
      parts.push(`тимчасові хіти ${report.temporary} збережено`);
    }
  } else {
    parts.push("хіти не змінилися — витрачайте кістки хитів");
    if (report.slots_before > report.slots_after) parts.push("Pact Magic відновлено");
  }
  if (report.features_reset.length) {
    parts.push(`відновлено: ${report.features_reset.join(", ")}`);
  }
  if (!parts.length) parts.push("стан уже був повний");
  return `${report.kind === "long" ? "Довгий" : "Короткий"} відпочинок · ${parts.join(" · ")}`;
}

export function CharacterView({ initial }: { initial: SheetViewPayload }) {
  const [sheet, setSheet] = useState<SheetViewPayload>(initial);
  const [tab, setTab] = useState("actions");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [restNote, setRestNote] = useState<string | null>(null);
  const [notesDraft, setNotesDraft] = useState<Record<string, string>>({
    ...initial.state.notes,
  });

  const id = sheet.character.id;
  // Версія для оптимістичного контролю: беремо з ref, а не з рендера, бо
  // клік може статися до того, як React перемалює після попередньої відповіді.
  const versionRef = useRef(initial.character.version);

  // PDF збирається на сервері через WeasyPrint: без GTK його немає, і тоді
  // посилання не показуємо, замість того щоб віддати 503 у новій вкладці.
  const renderers = useQuery({ queryKey: ["renderers"], queryFn: fetchRenderers });
  const pdfReady = renderers.data?.available.includes("pdf") ?? false;

  async function run(action: Promise<{ sheet: SheetViewPayload }>): Promise<SheetViewPayload | null> {
    setBusy(true);
    setError(null);
    try {
      const result = await action;
      versionRef.current = result.sheet.character.version;
      setSheet(result.sheet);
      return result.sheet;
    } catch (failure) {
      setError(messageOf(failure));
      return null;
    } finally {
      setBusy(false);
    }
  }

  const patch = (body: Record<string, unknown>) =>
    run(patchCharacter(id, { ...body, version: versionRef.current }));

  const damage = (amount: number) => patch({ hp: { damage: amount } });
  const heal = (amount: number) => patch({ hp: { heal: amount } });
  const setHitPoints = (fields: { current?: number; temporary?: number }) =>
    patch({ hp: fields });
  const addItem = (item: ItemBody) =>
    run(addCharacterItem(id, item, versionRef.current)).then((result) => result !== null);
  const updateItem = (index: number, fields: Partial<ItemBody>) =>
    run(updateCharacterItem(id, index, fields, versionRef.current)).then(
      (result) => result !== null,
    );
  const removeItem = (index: number) =>
    run(removeCharacterItem(id, index, versionRef.current)).then(
      (result) => result !== null,
    );

  async function rest(kind: "short" | "long") {
    setBusy(true);
    setError(null);
    try {
      const result = await restCharacter(id, kind);
      versionRef.current = result.sheet.character.version;
      setSheet(result.sheet);
      setRestNote(describeRest(result.rest));
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setBusy(false);
    }
  }

  function setFeatureUse(key: string, used: number) {
    const values: Record<string, number> = {};
    for (const resource of sheet.feature_resources) {
      const next = resource.key === key ? used : resource.used;
      if (next) values[resource.key] = next;
    }
    patch({ feature_used: values });
  }

  // --- нотатки й зовнішність: автозбереження через паузу ---------------
  const [notesStatus, setNotesStatus] = useState<NoteStatus>("idle");
  const [notesSavedAt, setNotesSavedAt] = useState<string | null>(null);
  const notesTimer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (notesTimer.current) window.clearTimeout(notesTimer.current);
    },
    [],
  );

  function updateNote(key: string, value: string) {
    const next = { ...notesDraft, [key]: value };
    setNotesDraft(next);
    if (notesTimer.current) window.clearTimeout(notesTimer.current);
    setNotesStatus("saving");
    notesTimer.current = window.setTimeout(() => {
      void saveNotes(next);
    }, 800);
  }

  async function saveNotes(next: Record<string, string>) {
    try {
      const result = await patchCharacter(id, { notes: next });
      versionRef.current = Math.max(versionRef.current, result.sheet.character.version);
      setNotesStatus("saved");
      setNotesSavedAt(
        new Date().toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" }),
      );
    } catch (failure) {
      setNotesStatus("error");
      setError(messageOf(failure));
    }
  }

  function saveNotesNow() {
    if (notesTimer.current) window.clearTimeout(notesTimer.current);
    setNotesStatus("saving");
    void saveNotes(notesDraft);
  }

  function exportNotes() {
    downloadNotes(
      notesDraft,
      character.name,
      Object.entries(NOTE_LABELS).map(([key, label]) => ({ key, label })),
    );
  }

  const overridden = new Set(sheet.overridden);
  const { character } = sheet;
  const casting = sheet.spellcasting;

  function overrideNumber(key: string, value: number, title: string, suffix = "") {
    return (
      <EditableNumber
        value={value}
        title={title}
        suffix={suffix}
        overridden={overridden.has(key)}
        onSave={(next) => patch({ overrides: { [key]: next } })}
        onReset={() => patch({ overrides: { [key]: null } })}
      />
    );
  }

  const totalLevel = character.total_level;
  const speciesText = character.species
    ? (character.species.subspecies ?? character.species.name_en)
    : "вид не вказано";
  const classText = character.classes.length
    ? character.classes
        .map(
          (item) =>
            `${item.name_en} ${item.level}${item.subclass ? ` (${subclassLabel(item.subclass)})` : ""}`,
        )
        .join(" / ")
    : "клас не вказано";
  const originText = [
    character.alignment ? (ALIGNMENT_LABELS[character.alignment] ?? character.alignment) : "",
    character.background?.name_en ?? "",
    "правила 2014",
  ]
    .filter(Boolean)
    .join(" · ");

  // Пасивна уважність рахується на сервері; розслідування й проникливість
  // показуємо як 10 + навичка — це похідне число для ока, воно не зберігається.
  const passives = [
    { label: "Пасивна спостережливість", value: sheet.passive_perception },
    {
      label: "Пасивне розслідування",
      value: 10 + (sheet.skills.investigation?.value ?? 0),
      note: "10 + навичка",
    },
    {
      label: "Пасивна проникливість",
      value: 10 + (sheet.skills.insight?.value ?? 0),
      note: "10 + навичка",
    },
  ];

  const workTab = (() => {
    if (tab === "actions") {
      return (
        <>
          <h3 className="ddb-work__title">
            <span>Атаки</span>
            <span className="short">дій за хід: 1</span>
          </h3>
          <AttacksTable attacks={sheet.attacks} />
          {casting.classes.length ? (
            <>
              <h3 className="ddb-work__title">
                <span>Закляття</span>
                <span className="short">доступні зараз</span>
              </h3>
              <ActionSpells spells={sheet.spells} casting={casting} />
            </>
          ) : null}
          <h3 className="ddb-work__title">
            <span>Дії в бою</span>
            <span className="short">стандартні</span>
          </h3>
          <ul className="combat-actions">
            {COMBAT_ACTIONS.map((action) => (
              <li key={action.name} className="combat-action">
                <span className="combat-action__name">{action.name}</span>
                <span className="combat-action__hint">{action.hint}</span>
              </li>
            ))}
          </ul>
        </>
      );
    }
    if (tab === "spells") {
      return (
        <>
          <h3 className="ddb-work__title">
            <span>Чарування</span>
          </h3>
          <CastingBlock
            casting={casting}
            resources={sheet.resources}
            onSlotsUsed={(level, used) => {
              const usedMap: Record<string, number> = {};
              for (const [key, value] of Object.entries(sheet.resources.slots)) {
                const next = key === level ? used : value.used;
                if (next) usedMap[key] = next;
              }
              patch({ slots: usedMap });
            }}
            onPactUsed={(used) => patch({ pact_used: used })}
          />
          <h3 className="ddb-work__title">
            <span>Відомі закляття</span>
          </h3>
          <SpellsKnownList spells={sheet.spells} />
        </>
      );
    }
    if (tab === "inventory") {
      return (
        <InventoryPanel
          items={sheet.inventory.items}
          money={sheet.inventory.money}
          carrying={sheet.carrying}
          disabled={busy}
          onAdd={addItem}
          onUpdate={updateItem}
          onRemove={removeItem}
        />
      );
    }
    if (tab === "features") {
      return (
        <>
          {sheet.feature_resources.length ? (
            <>
              <h3 className="ddb-work__title">
                <span>Ресурси класу</span>
                <span className="short">витрачено</span>
              </h3>
              <FeatureResources
                resources={sheet.feature_resources}
                disabled={busy}
                onChange={setFeatureUse}
              />
            </>
          ) : null}
          <h3 className="ddb-work__title">
            <span>Уміння</span>
            <span className="short">натисніть, щоб читати</span>
          </h3>
          <FeaturesList features={sheet.features} />
          <h3 className="ddb-work__title">
            <span>Володіння з джерелами</span>
          </h3>
          <ProficienciesList proficiencies={sheet.proficiencies} />
        </>
      );
    }
    if (tab === "background") {
      return (
        <BackgroundPanel
          details={sheet.background_details}
          alignment={character.alignment}
          appearance={notesDraft.appearance ?? ""}
          status={notesStatus}
          savedAt={notesSavedAt}
          onAppearanceChange={(value) => updateNote("appearance", value)}
        />
      );
    }
    return (
      <NotesPanel
        notes={notesDraft}
        status={notesStatus}
        savedAt={notesSavedAt}
        onUpdate={updateNote}
        onSaveNow={saveNotesNow}
        onExport={exportNotes}
      />
    );
  })();

  return (
    <article className="sheet character-view">
      <header className="ddb-top">
        <div className="ddb-identity">
          <span className="ddb-portrait" aria-hidden="true">
            {initials(character.name)}
          </span>
          <div>
            <p className="ddb-kicker">Лист персонажа · {originText}</p>
            <h1 className="ddb-name">{character.name}</h1>
            <p className="ddb-sub">
              <span>{speciesText}</span>
              <span>·</span>
              <span>{classText}</span>
              <span>· рівень {totalLevel}</span>
            </p>
          </div>
        </div>
        <div className="ddb-top__actions">
          <div className="ddb-rest">
            <button
              type="button"
              className="ddb-btn"
              disabled={busy}
              onClick={() => void rest("short")}
            >
              Короткий відпочинок
            </button>
            <button
              type="button"
              className="ddb-btn ddb-btn--primary"
              disabled={busy}
              onClick={() => void rest("long")}
            >
              Довгий відпочинок
            </button>
          </div>
          <div className="ddb-export">
            <span className="ddb-export__label">Експорт</span>
            <a className="ddb-btn ddb-btn--link" href={exportUrl(id, "markdown")} download>
              Markdown
            </a>
            <a
              className="ddb-btn ddb-btn--link"
              href={`${exportUrl(id, "markdown")}?originals=false`}
              download
            >
              без англ.
            </a>
            {pdfReady ? (
              <a
                className="ddb-btn ddb-btn--link ddb-btn--primary"
                href={exportUrl(id, "pdf")}
                download
              >
                PDF (A4)
              </a>
            ) : (
              <span className="meta" title="На сервері немає WeasyPrint (extra `pdf` + GTK)">
                без PDF
              </span>
            )}
          </div>
        </div>
      </header>

      {restNote ? (
        <p className="ddb-rest-note" role="status">
          <span>{restNote}</span>
          <button
            type="button"
            className="ddb-rest-note__close"
            onClick={() => setRestNote(null)}
            aria-label="Закрити повідомлення про відпочинок"
          >
            ×
          </button>
        </p>
      ) : null}

      <div className="ddb-strip">
        <ul className="ddb-abilities">
          {ABILITIES.map((ability) => (
            <AbilityHex key={ability} code={ability} ability={sheet.abilities[ability]} />
          ))}
        </ul>

        <HexStat label="Майстерність" value={modifierLabel(sheet.proficiency_bonus)} />
        <HexStat
          label="Швидкість"
          value={overrideNumber("speed", sheet.speed, "Швидкість", " фт")}
        />

        <HitPointsBlock
          hitPoints={sheet.hit_points}
          maxField={overrideNumber("hit_points_max", sheet.hit_points.maximum, "Максимум хітів")}
          disabled={busy}
          onSet={setHitPoints}
          onDamage={damage}
          onHeal={heal}
        />
      </div>

      {error ? <p className="status status--error ddb-status">{error}</p> : null}
      {busy ? <p className="meta ddb-status">Зберігаємо…</p> : null}

      <div className="ddb-grid">
        <div className="ddb-col">
          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Кидки порятунку</span>
            </h2>
            <SavePills saves={sheet.saving_throws} render={overrideNumber} />
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Пасивні показники</span>
            </h2>
            <PassiveList items={passives} />
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Чуття та опір</span>
            </h2>
            <ul className="ddb-rows">
              <li>
                <span className="ddb-rows__label">Темний зір</span>
                <span>{sheet.darkvision ? `${sheet.darkvision} фт` : "—"}</span>
              </li>
              <li>
                <span className="ddb-rows__label">Швидкість</span>
                <span>{sheet.speed} фт</span>
              </li>
              <li>
                <span className="ddb-rows__label">Опір</span>
                <span>{sheet.resistances.length ? sheet.resistances.map(damageTypeLabel).join(", ") : "—"}</span>
              </li>
            </ul>
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Володіння</span>
            </h2>
            <ProficiencyGroups proficiencies={sheet.proficiencies} />
          </section>
        </div>

        <div className="ddb-col ddb-col--mid">
          <div className="ddb-hexrow">
            <HexStat
              label="Ініціатива"
              value={overrideNumber("initiative", sheet.initiative, "Ініціатива")}
            />
            <HexStat
              label="Клас захисту"
              value={overrideNumber("armor_class", sheet.armor_class.value, "Клас захисту")}
              note="КЗ"
              title={partList(sheet.armor_class.parts)}
            />
          </div>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Навички</span>
            </h2>
            <SkillTable skills={sheet.skills} render={overrideNumber} />
            <details className="reckoning">
              <summary>Звідки числа</summary>
              <ul className="reckoning-list">
                {ABILITIES.map((ability) => {
                  const value = sheet.abilities[ability];
                  const save = sheet.saving_throws[ability];
                  const parts = [String(value.base)];
                  if (value.bonus) {
                    parts.push(`${value.bonus > 0 ? "+" : "−"} ${Math.abs(value.bonus)}`);
                  }
                  return (
                    <li key={ability} className="reckoning-row">
                      <span className="reckoning-row__name">{abilityLabel(ability)}</span>
                      <span className="reckoning-row__total" title="Підсумок характеристики">
                        {value.total}
                      </span>
                      <span className="reckoning-row__math">
                        {parts.join(" ")} = {value.total} · мод {modifierLabel(value.modifier)}
                      </span>
                      <span className="reckoning-row__save">
                        порятунок{" "}
                        {overrideNumber(
                          `save:${ability}`,
                          save.value,
                          `Порятунок ${ABILITY_LABELS[ability]}`,
                        )}
                        {save.proficient ? <span className="dot" title="володіє" /> : null}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </details>
          </section>
        </div>

        <div className="ddb-col ddb-col--work">
          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Стан</span>
            </h2>
            <div className="state-row">
              <span>
                Натхнення:{" "}
                <button
                  type="button"
                  className={`chip ${sheet.state.inspiration ? "chip--active" : ""}`}
                  onClick={() => patch({ inspiration: !sheet.state.inspiration })}
                >
                  {sheet.state.inspiration ? "є" : "немає"}
                </button>
              </span>
              <span>
                Втома:{" "}
                <NumberField
                  value={sheet.state.exhaustion}
                  min={0}
                  max={6}
                  size="sm"
                  disabled={busy}
                  title="Рівень втоми"
                  onChange={(value) => patch({ exhaustion: value })}
                />
              </span>
              <span className="state-row__wide">
                Кидки смерті: успіхи{" "}
                <Pips
                  count={sheet.state.death_saves.successes}
                  max={3}
                  title="Успіхи кидків смерті"
                  onChange={(value) =>
                    patch({
                      death_saves: {
                        successes: value,
                        failures: sheet.state.death_saves.failures,
                      },
                    })
                  }
                />{" "}
                провали{" "}
                <Pips
                  count={sheet.state.death_saves.failures}
                  max={3}
                  title="Провали кидків смерті"
                  onChange={(value) =>
                    patch({
                      death_saves: {
                        successes: sheet.state.death_saves.successes,
                        failures: value,
                      },
                    })
                  }
                />
              </span>
            </div>
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Кістки хитів</span>
            </h2>
            <HitDiceBlock
              resources={sheet.resources}
              conModifier={sheet.abilities.con?.modifier ?? 0}
              disabled={busy}
              onSpend={(die, roll) =>
              run(spendHitDie(id, die, roll)).then((result) => result !== null)
            }
            />
          </section>

          <div className="ddb-work">
            <nav className="ddb-tabs" aria-label="Розділи листа">
              {TABS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`ddb-tab ${tab === item.id ? "is-active" : ""}`}
                  onClick={() => setTab(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            <div className="ddb-work__body">{workTab}</div>
          </div>
        </div>
      </div>
    </article>
  );
}

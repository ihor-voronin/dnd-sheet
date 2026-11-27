/** Екран персонажа: огляд у дусі D&D Beyond, вкладки, правки на місці.
 *
 * Усі числа приходять із сервера; компонент їх не перераховує. Клік по
 * похідному числу (КЗ, ініціатива, навичка) створює **виправлення** — сервер
 * зберігає його окремо й позначає поле як «вручну», доки гравець не скине.
 * Лічильники (хіти, комірки, кістки хітів, кидки смерті) — це стан, а не
 * виправлення: кожна зміна одразу йде на диск.
 *
 * Розкладка повторює звичний аркуш D&D Beyond: шапка з портретом, рядок
 * характеристик-гексагонів, далі три колонки — рятівні кидки й володіння,
 * ініціатива з навичками, робоча панель із вкладками.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import {
  addCharacterItem,
  addCharacterSpell,
  exportUrl,
  fetchCharacter,
  fetchCharacterVersion,
  fetchShared,
  fetchSharedVersion,
  fetchRenderers,
  patchCharacter,
  prepareCharacterSpells,
  setCharacterClassChoice,
  setCharacterSpeciesFeat,
  setCharacterSpeciesSource,
  setCharacterExpertise,
  removeCharacterItem,
  removeCharacterSpell,
  restCharacter,
  spendHitDie,
  updateCharacterItem,
} from "../../api";
import type { ItemBody, SpellBody } from "../../api";
import { SharePanel } from "./SharePanel";
import type { RestReport, SheetViewPayload } from "../wizard/types";
import {
  ABILITY_LABELS,
  ALIGNMENT_LABELS,
  abilityCodesUk,
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
} from "./sheetParts";
import { EditableNumber, NumberField, Pips } from "./editing";
import { HitDiceBlock, HitPointsBlock } from "./hp";
import { InventoryPanel } from "./inventory";
import { NotesPanel, downloadNotes } from "./notes";
import type { NoteStatus } from "./notes";
import { BackgroundPanel } from "./background";
import { ClassChoices, SpeciesFeat, SpeciesSource } from "./classChoices";
import { ExpertisePicker } from "./expertise";
import { ActionPanel } from "./actions";
import { AddSpellForm, SpellsPreparePanel } from "./spells";
import { speciesLabel, termLabel, ukSubclass, withEnglish } from "./uk";
import {
  CastingBlock,
  FeatureResources,
  FeatsList,
  FeaturesList,
  ProficienciesList,
  SpellsKnownList,} from "./panels";

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"];

/** Як часто лист питає сервер, чи не змінили його з іншого пристрою. */
const SYNC_INTERVAL_MS = 4000;

const TABS: { id: string; label: string }[] = [
  { id: "actions", label: "Дії" },
  { id: "spells", label: "Закляття" },
  { id: "inventory", label: "Інвентар" },
  { id: "features", label: "Уміння" },
  { id: "background", label: "Передісторія" },
  { id: "notes", label: "Нотатки" },
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
  if (raw === "mage-armor") return "Чарівна броня (Mage Armor)";
  if (raw === "dragon-hide") return "Драконяча шкура (Dragon Hide)";
  if (raw === "draconic-resilience") return "Драконяча стійкість (Draconic Resilience)";
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
      parts.push(`кістки хітів: витрачено ${report.hit_dice_before} → ${report.hit_dice_after}`);
    }
    if (report.slots_before > 0) parts.push("комірки відновлено");
    if (report.exhaustion_before !== report.exhaustion_after) {
      parts.push(`виснаження ${report.exhaustion_before} → ${report.exhaustion_after}`);
    }
    if (report.temporary > 0) {
      parts.push(`тимчасові хіти ${report.temporary} збережено`);
    }
  } else {
    parts.push("хіти не змінилися — витрачайте кістки хітів");
    if (report.slots_before > report.slots_after) parts.push("комірки магії угоди (Pact Magic) відновлено");
  }
  if (report.features_reset.length) {
    parts.push(`відновлено: ${report.features_reset.join(", ")}`);
  }
  if (!parts.length) parts.push("стан уже був повний");
  return `${report.kind === "long" ? "Тривалий" : "Короткий"} відпочинок · ${parts.join(" · ")}`;
}

/** Вимкнений fieldset без власної розкладки: усе всередині лише для перегляду. */
function ReadOnly({ on, children }: { on: boolean; children: ReactNode }) {
  if (!on) return <>{children}</>;
  return (
    <fieldset disabled className="sheet-readonly">
      {children}
    </fieldset>
  );
}

export function CharacterView({
  initial,
  initialTab,
  shareToken,
}: {
  initial: SheetViewPayload;
  /** Вкладка, з якої відкрити лист: після підвищення рівня — «Закляття». */
  initialTab?: string;
  /** Лист за посиланням «лише читати»: жодних змін, друк і PDF — через посилання. */
  shareToken?: string;
}) {
  const readOnly = Boolean(shareToken);
  const [shareOpen, setShareOpen] = useState(false);
  // На телефоні дії з листом (відпочинок, рівень, експорт) сховані під одну кнопку:
  // за столом першими мають бути хіти й атаки, а не ряд службових кнопок.
  const [actionsOpen, setActionsOpen] = useState(false);
  const [sheet, setSheet] = useState<SheetViewPayload>(initial);
  const [tab, setTab] = useState(initialTab ?? "actions");
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
  // Скільки версії листа екран уже прийняв від батька. Потрібно, щоб після
  // підвищення рівня (окремий маршрут) повернення на лист показало **нові**
  // числа, а не ті, що були в кеші на момент відкриття.
  const adoptedVersion = useRef(initial.character.version);
  useEffect(() => {
    // Батько міг принести ту саму версію, що екран уже має після власної зміни.
    if (initial.character.version <= Math.max(adoptedVersion.current, versionRef.current)) return;
    adoptedVersion.current = initial.character.version;
    versionRef.current = initial.character.version;
    setSheet(initial);
    setNotesDraft({ ...initial.state.notes });
  }, [initial]);

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
      const message = messageOf(failure);
      // Конфлікт версій: хтось змінив лист раніше. Показуємо свіжу версію
      // одразу, щоб повтор дії пішов уже від неї.
      if (/версі|іншому пристрої/i.test(message)) {
        try {
          const fresh = await fetchCharacter(id);
          versionRef.current = fresh.sheet.character.version;
          adoptedVersion.current = Math.max(adoptedVersion.current, versionRef.current);
          setSheet(fresh.sheet);
          setError("Лист щойно змінили на іншому пристрої — показано свіжу версію. Повторіть дію.");
          return null;
        } catch {
          // не вдалося перечитати — покажемо початкову помилку
        }
      }
      setError(message);
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

  // Закляття: помилки не ковтаємо — форма показує текст відмови сервера
  // («можна 5», «клас не готує»), а не загальне «не вдалося».
  async function applySpellChange(action: Promise<{ sheet: SheetViewPayload }>): Promise<void> {
    setBusy(true);
    try {
      const result = await action;
      versionRef.current = result.sheet.character.version;
      setSheet(result.sheet);
    } finally {
      setBusy(false);
    }
  }

  async function addSpell(spell: SpellBody): Promise<boolean> {
    await applySpellChange(addCharacterSpell(id, spell, versionRef.current));
    return true;
  }

  async function removeSpell(spell: SheetViewPayload["spells"][number]): Promise<boolean> {
    if (!spell.class_key) return false;
    try {
      await applySpellChange(
        removeCharacterSpell(id, spell.name_en, spell.class_key, versionRef.current),
      );
      return true;
    } catch (failure) {
      setError(messageOf(failure));
      return false;
    }
  }

  async function savePrepared(
    classKey: string,
    picks: { name_en: string; level: number; entry_id: string | null }[],
  ): Promise<boolean> {
    await applySpellChange(
      prepareCharacterSpells(id, classKey, picks, versionRef.current),
    );
    return true;
  }

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

  // --- синхронізація між пристроями -----------------------------------
  // Лист живе в базі: його можуть змінити з телефона чи іншої вкладки. Раз на
  // кілька секунд питаємо лише номер версії; новіша — перечитуємо лист. Поки
  // екран сам зберігає зміну чи нотатки, не чіпаємо: інакше відповідь
  // перезаписала б те, що гравець щойно ввів.
  const [syncNote, setSyncNote] = useState<string | null>(null);
  const quiet = useRef(true);
  quiet.current = !busy && notesStatus !== "saving";
  async function syncFromServer(): Promise<void> {
    if (!quiet.current || document.hidden) return;
    try {
      const { version } = await (shareToken ? fetchSharedVersion(shareToken) : fetchCharacterVersion(id));
      if (version <= versionRef.current || !quiet.current) return;
      const fresh = await (shareToken ? fetchShared(shareToken) : fetchCharacter(id));
      if (fresh.sheet.character.version <= versionRef.current || !quiet.current) return;
      versionRef.current = fresh.sheet.character.version;
      adoptedVersion.current = Math.max(adoptedVersion.current, versionRef.current);
      setSheet(fresh.sheet);
      setNotesDraft({ ...fresh.sheet.state.notes });
      setSyncNote(readOnly ? "Лист оновлено: власник щойно його змінив." : "Лист оновлено: його змінили на іншому пристрої.");
    } catch {
      // мережа зникла — спробуємо на наступному такті
    }
  }
  useEffect(() => {
    const timer = window.setInterval(() => void syncFromServer(), SYNC_INTERVAL_MS);
    const onVisible = () => {
      if (!document.hidden) void syncFromServer();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
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
  const speciesKey = character.species?.subspecies ?? character.species?.name_en;
  const speciesText = speciesKey ? speciesLabel(speciesKey) : "вид не вказано";
  const classText = character.classes.length
    ? character.classes
        .map(
          (item) =>
            `${termLabel(item.name_en)} ${item.level}${item.subclass ? ` · ${withEnglish(item.subclass_name ?? subclassLabel(item.subclass), item.subclass_name_uk ?? ukSubclass(item.subclass))}` : ""}`,
        )
        .join(" / ")
    : "клас не вказано";
  const originText = [
    character.alignment ? (ALIGNMENT_LABELS[character.alignment] ?? character.alignment) : "",
    character.background ? termLabel(character.background.name_en) : "",
    "правила 2014",
  ]
    .filter(Boolean)
    .join(" · ");

  // Класи, узяті без вимог мультикласу: лист каже це прямо, а не мовчить.
  const waiverText = (character.multiclass_waivers ?? [])
    .map((waiver) => {
      const name =
        character.classes.find((item) => item.key === waiver.class_key)?.name_en ??
        waiver.class_key;
      const required = abilityCodesUk(waiver.requirements.join(" або "));
      return required ? `${termLabel(name)} · ${required}` : termLabel(name);
    })
    .join("; ");

  // Пасивна уважність рахується на сервері; розслідування й проникливість
  // показуємо як 10 + навичка — це похідне число для ока, воно не зберігається.
  const passives = [
    { label: "Пасивна спостережливість", value: sheet.passive_perception },
    {
      label: "Пасивне розслідування",
      value: sheet.passive_investigation ?? 10 + (sheet.skills.investigation?.value ?? 0),
      note: "10 + навичка",
    },
    {
      label: "Пасивна проникливість",
      value: sheet.passive_insight ?? 10 + (sheet.skills.insight?.value ?? 0),
      note: "10 + навичка",
    },
  ];

  const workTab = (() => {
    if (tab === "actions") {
      return <ActionPanel sheet={sheet} onUseFeature={setFeatureUse} />;
    }
    if (tab === "spells") {
      return (
        <>
          <h3 className="sheet-work__title">
            <span>Чарування</span>
          </h3>
          {sheet.armor_untrained?.length ? (
            <p className="hint hint--warn">
              Поки вдягнено {sheet.armor_untrained.join(", ")} без володіння, чарувати закляття не можна
              (PHB, с. 144).
            </p>
          ) : null}
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
          <SpellsPreparePanel
            casting={casting}
            spells={sheet.spells}
            busy={busy}
            onSave={savePrepared}
          />
          <h3 className="sheet-work__title">
            <span>Відомі закляття</span>
            <span className="short">натисніть, щоб читати</span>
          </h3>
          <AddSpellForm casting={casting} busy={busy} onAdd={addSpell} />
          <SpellsKnownList
            spells={sheet.spells}
            casting={sheet.spellcasting.classes}
            onRemove={(spell) => void removeSpell(spell)}
          />
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
          bonds={sheet.weapon_bonds}
          attunementLimit={sheet.attunement_limit}
        />
      );
    }
    if (tab === "features") {
      return (
        <>
          {sheet.feature_resources.length ? (
            <>
              <h3 className="sheet-work__title">
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
          {sheet.class_choices?.length || sheet.species_feat || sheet.species_source ? (
            <>
              <h3 className="sheet-work__title">
                <span>Вибори класу й рис</span>
              </h3>
              {sheet.species_source ? (
                <SpeciesSource
                  value={sheet.species_source}
                  busy={busy}
                  onSave={(source) => run(setCharacterSpeciesSource(id, source, versionRef.current))}
                />
              ) : null}
              {sheet.species_feat ? (
                <SpeciesFeat
                  value={sheet.species_feat}
                  busy={busy}
                  onSave={(featKey, ability) =>
                    run(setCharacterSpeciesFeat(id, featKey, ability, versionRef.current))
                  }
                />
              ) : null}
              <ClassChoices
                groups={sheet.class_choices ?? []}
                busy={busy}
                onSave={(group, values) =>
                  run(setCharacterClassChoice(id, group, values, versionRef.current))
                }
              />
            </>
          ) : null}
          <h3 className="sheet-work__title">
            <span>Уміння</span>
            <span className="short">натисніть, щоб читати</span>
          </h3>
          <FeaturesList features={sheet.features} />
          {sheet.feat_details?.length ? (
            <>
              <h3 className="sheet-work__title">
                <span>Риси</span>
              </h3>
              <FeatsList feats={sheet.feat_details} />
            </>
          ) : null}
          <h3 className="sheet-work__title">
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
      <header className="sheet-top">
        <div className="sheet-identity">
          <span className="sheet-portrait" aria-hidden="true">
            {initials(character.name)}
          </span>
          <div>
            <p className="sheet-kicker">Лист персонажа · {originText}</p>
            <h1 className="sheet-name">{character.name}</h1>
            <p className="sheet-sub">
              <span>{speciesText}</span>
              <span>·</span>
              <span>{classText}</span>
              <span>· рівень {totalLevel}</span>
            </p>
          </div>
        </div>
        {readOnly ? (
          <div className="sheet-top__actions">
            <p className="sheet-readonly-note">Лише перегляд: змінювати лист може тільки власник.</p>
            <div className="sheet-export">
              <span className="sheet-export__label">Роздрукувати</span>
              {pdfReady ? (
                <a
                  className="sheet-btn sheet-btn--link sheet-btn--primary"
                  href={`/api/v1/shared/${encodeURIComponent(shareToken ?? "")}/export/pdf`}
                  download
                >
                  PDF
                </a>
              ) : null}
              <a
                className="sheet-btn sheet-btn--link"
                href={`/api/v1/shared/${encodeURIComponent(shareToken ?? "")}/print`}
                target="_blank"
                rel="noopener"
                title="Аркуш у вкладці браузера — друк через Ctrl+P"
              >
                у браузері
              </a>
            </div>
          </div>
        ) : (
        <>
        <button
          type="button"
          className="sheet-btn sheet-actions-toggle"
          aria-expanded={actionsOpen}
          aria-controls="sheet-actions"
          onClick={() => setActionsOpen((open) => !open)}
        >
          {actionsOpen ? "Сховати дії" : "Дії з листом"}
        </button>
        <div id="sheet-actions" className={`sheet-top__actions sheet-top__actions--owner ${actionsOpen ? "is-open" : ""}`}>
          <button
            type="button"
            className="sheet-btn"
            aria-expanded={shareOpen}
            onClick={() => setShareOpen((open) => !open)}
            title="Посилання на лист лише для перегляду"
          >
            Поділитися
          </button>
          <a
            className="sheet-btn sheet-btn--link"
            href={`#/character/${encodeURIComponent(id)}/level-up`}
            title="Узяти наступний рівень: клас, хіти, підклас, характеристики"
          >
            +1 рівень
          </a>
          <div className="sheet-rest">
            <button
              type="button"
              className="sheet-btn"
              disabled={busy}
              onClick={() => void rest("short")}
            >
              Короткий відпочинок
            </button>
            <button
              type="button"
              className="sheet-btn sheet-btn--primary"
              disabled={busy}
              onClick={() => void rest("long")}
            >
              Тривалий відпочинок
            </button>
          </div>
          <div className="sheet-export">
            <span className="sheet-export__label">Завантажити</span>
            {pdfReady ? (
              <>
                <a
                  className="sheet-btn sheet-btn--link sheet-btn--primary"
                  href={exportUrl(id, "pdf")}
                  download
                  title="Аркуш для гри (головна, закляття, спорядження) і додаткові аркуші з повними текстами умінь і заклять"
                >
                  PDF
                </a>
              </>
            ) : null}
            <a
              className="sheet-btn sheet-btn--link"
              href={exportUrl(id, "markdown")}
              download
              title="Текст листа для нотаток і чатів"
            >
              Markdown
            </a>
            <a
              className="sheet-btn sheet-btn--link"
              href={`/api/v1/characters/${encodeURIComponent(id)}/print`}
              target="_blank"
              rel="noopener"
              title="Той самий аркуш у вкладці браузера — друк через Ctrl+P"
            >
              Друк
            </a>
          </div>
        </div>
        </>
        )}
      </header>

      {shareOpen && !readOnly ? <SharePanel characterId={id} onClose={() => setShareOpen(false)} /> : null}

      {waiverText ? (
        <p className="sheet-waiver-note" role="note">
          <span>
            Вимоги мультикласу проігноровано: {waiverText}. Це правило дому — PHB вимагає
            13 у ключовій характеристиці класу.
          </span>
        </p>
      ) : null}

      {syncNote ? (
        <p className="sheet-rest-note" role="status">
          <span>{syncNote}</span>
          <button
            type="button"
            className="sheet-rest-note__close"
            onClick={() => setSyncNote(null)}
            aria-label="Закрити повідомлення про оновлення"
          >
            ×
          </button>
        </p>
      ) : null}

      {restNote ? (
        <p className="sheet-rest-note" role="status">
          <span>{restNote}</span>
          <button
            type="button"
            className="sheet-rest-note__close"
            onClick={() => setRestNote(null)}
            aria-label="Закрити повідомлення про відпочинок"
          >
            ×
          </button>
        </p>
      ) : null}

      <ReadOnly on={readOnly}>
      <div className="sheet-strip">
        <ul className="sheet-abilities">
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
      </ReadOnly>

      {error ? <p className="status status--error sheet-status">{error}</p> : null}
      {busy ? <p className="meta sheet-status">Зберігаємо…</p> : null}

      <div className="sheet-grid">
        <ReadOnly on={readOnly}>
        <div className="sheet-col">
          <section className="sheet-card">
            <h2 className="sheet-card__title">
              <span>Рятівні кидки</span>
            </h2>
            <SavePills saves={sheet.saving_throws} render={overrideNumber} />
          </section>

          <section className="sheet-card">
            <h2 className="sheet-card__title">
              <span>Пасивні показники</span>
            </h2>
            <PassiveList items={passives} />
          </section>

          <section className="sheet-card">
            <h2 className="sheet-card__title">
              <span>Чуття та опір</span>
            </h2>
            <ul className="sheet-rows">
              <li>
                <span className="sheet-rows__label">Темний зір</span>
                <span>{sheet.darkvision ? `${sheet.darkvision} фт` : "—"}</span>
              </li>
              {sheet.blindsight ? (
                <li>
                  <span className="sheet-rows__label">Сліпе чуття</span>
                  <span>{sheet.blindsight} фт</span>
                </li>
              ) : null}
              <li>
                <span className="sheet-rows__label">Швидкість</span>
                <span>{sheet.speed} фт</span>
              </li>
              <li>
                <span className="sheet-rows__label">Опір</span>
                <span>{sheet.resistances.length ? sheet.resistances.map(damageTypeLabel).join(", ") : "—"}</span>
              </li>
              {(sheet.roll_notes ?? []).map((note) => (
                <li key={note}>
                  <span className="hint">{note}</span>
                </li>
              ))}
              {(sheet.resistance_notes ?? []).map((note) => (
                <li key={note}>
                  <span className="hint">{note}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="sheet-card">
            <h2 className="sheet-card__title">
              <span>Володіння</span>
            </h2>
            <ProficiencyGroups proficiencies={sheet.proficiencies} />
          </section>
        </div>
        </ReadOnly>

        <ReadOnly on={readOnly}>
        <div className="sheet-col sheet-col--mid">
          {sheet.warnings?.length ? (
            <div className="sheet-warnings" role="status">
              {sheet.warnings.map((warning) => (
                <p key={warning} className="hint hint--warn">
                  {warning}
                </p>
              ))}
            </div>
          ) : null}
          <div className="sheet-hexrow">
            <HexStat
              label="Ініціатива"
              value={overrideNumber("initiative", sheet.initiative, "Ініціатива")}
            />
            <HexStat
              label="Клас захисту"
              value={overrideNumber("armor_class", sheet.armor_class.value, "Клас захисту")}
              note="КЗ"
              title={[partList(sheet.armor_class.parts), ...(sheet.armor_class.notes ?? [])].join("\n")}
            />
          </div>
          {sheet.armor_class.notes?.length ? (
            <p className="hint">{sheet.armor_class.notes.join("; ")}</p>
          ) : null}

          <section className="sheet-card">
            <h2 className="sheet-card__title">
              <span>Навички</span>
            </h2>
            <SkillTable skills={sheet.skills} render={overrideNumber} />
            {sheet.expertise && sheet.expertise.slots > 0 ? (
              <ExpertisePicker
                expertise={sheet.expertise}
                busy={busy}
                onSave={(values) =>
                  run(setCharacterExpertise(id, values, versionRef.current))
                }
              />
            ) : null}
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
                        рятівний кидок{" "}
                        {overrideNumber(
                          `save:${ability}`,
                          save.value,
                          `Рятівний кидок ${ABILITY_LABELS[ability]}`,
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
        </ReadOnly>

        <div className="sheet-col sheet-col--work">
          <ReadOnly on={readOnly}>
          <section className="sheet-card">
            <h2 className="sheet-card__title">
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
                Виснаження:{" "}
                <NumberField
                  value={sheet.state.exhaustion}
                  min={0}
                  max={6}
                  size="sm"
                  disabled={busy}
                  title="Рівень виснаження"
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

          {/* Кістки хітів не є ключовим блоком (хіти — так), тому згорнуті:
              розгортає гравець, коли справді витрачає кістку. */}
          <details className="sheet-card sheet-card--collapsible">
            <summary className="sheet-card__title">
              <span>
                <span className="sheet-caret" aria-hidden>
                  ▸
                </span>{" "}
                Кістки хітів
              </span>
            </summary>
            <HitDiceBlock
              resources={sheet.resources}
              conModifier={sheet.abilities.con?.modifier ?? 0}
              disabled={busy}
              onSpend={(die, roll) =>
              run(spendHitDie(id, die, roll)).then((result) => result !== null)
            }
            />
          </details>

          </ReadOnly>
          <div className="sheet-work">
            <nav className="sheet-tabs" aria-label="Розділи листа">
              {TABS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`sheet-tab ${tab === item.id ? "is-active" : ""}`}
                  aria-current={tab === item.id ? "page" : undefined}
                  onClick={() => setTab(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            <div className="sheet-work__body"><ReadOnly on={readOnly}>{workTab}</ReadOnly></div>
          </div>
        </div>
      </div>
    </article>
  );
}

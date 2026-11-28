/**
 * Вибір портрета: спершу поради під вид, клас і стать героя, далі — увесь
 * каталог із фільтрами.
 *
 * Портрети малює сервер (власні малюнки сайту, без завантажень гравця). Цей
 * модуль вантажиться окремим шматком лише тоді, коли гравець відкрив вибір, —
 * лист без нього не важчає. Плитки — `<img loading="lazy">`: каталог має понад
 * тисячу портретів, але браузер тягне лише видимі, і по 48 за раз.
 */
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { fetchAvatarCatalog, fetchRecommendedAvatars } from "../../api";
import { type PortraitCard, PortraitImage } from "../../components/Portrait";
import type { Gender } from "../wizard/types";

const PAGE = 48;

const GENDER_LABELS: Record<"f" | "m" | "x", string> = { f: "жіночий", m: "чоловічий", x: "" };

export interface AvatarPickerProps {
  name: string;
  /** Англійська назва виду з підрасою («drow elf Elf») — за нею сервер знаходить групу. */
  species: string | null;
  classKey: string | null;
  gender: Gender | null;
  current: PortraitCard | undefined;
  busy: boolean;
  onChoose: (avatar: string | null) => void;
  onGender: (gender: Gender | null) => void;
  onClose: () => void;
}

function Tile({
  portrait,
  selected,
  busy,
  onChoose,
}: {
  portrait: PortraitCard;
  selected: boolean;
  busy: boolean;
  onChoose: (id: string) => void;
}) {
  return (
    <li>
      <button
        type="button"
        className="avatar-tile"
        aria-pressed={selected}
        aria-label={portrait.label}
        title={portrait.label}
        disabled={busy}
        onClick={() => onChoose(portrait.id)}
      >
        <PortraitImage portrait={portrait} name="" size={88} alt="" />
      </button>
    </li>
  );
}

export function AvatarPicker({
  name,
  species,
  classKey,
  gender,
  current,
  busy,
  onChoose,
  onGender,
  onClose,
}: AvatarPickerProps) {
  const advice = useQuery({
    queryKey: ["avatars", "recommended", species, classKey, gender],
    queryFn: () => fetchRecommendedAvatars({ species, classKey, gender }),
    staleTime: Infinity,
  });
  const [showAll, setShowAll] = useState(false);
  const catalog = useQuery({
    queryKey: ["avatars", "catalog"],
    queryFn: fetchAvatarCatalog,
    staleTime: Infinity,
    enabled: showAll,
  });
  const [group, setGroup] = useState<string>("");
  const [klass, setKlass] = useState<string>("");
  const [look, setLook] = useState<"" | "f" | "m" | "x">("");
  const [shown, setShown] = useState(PAGE);

  const all = useMemo(() => {
    const data = catalog.data;
    if (!data) return [];
    const groups = new Map(data.groups.map((item) => [item.key, item.label]));
    const classes = new Map(data.classes.map((item) => [item.key, item.label]));
    return data.items
      .filter(
        ([, itemGroup, itemGender, itemClass]) =>
          (!group || itemGroup === group) && (!klass || itemClass === klass) && (!look || itemGender === look),
      )
      .map(([id, itemGroup, itemGender, itemClass]): PortraitCard => {
        const variant = id.slice(id.lastIndexOf("-") + 1);
        const parts = [groups.get(itemGroup) ?? itemGroup, GENDER_LABELS[itemGender], classes.get(itemClass)];
        const label = `Портрет: ${parts.filter(Boolean).join(", ")}${variant !== "1" ? ` (${variant})` : ""}`;
        return { id, url: `${data.base}${id}.svg`, label };
      });
  }, [catalog.data, group, klass, look]);

  function filter(apply: () => void) {
    apply();
    setShown(PAGE);
  }

  // Поточний портрет позначено навіть типовий: видно, що зараз на листі.
  const selectedId = current?.id ?? null;

  return (
    <section className="avatar-panel" aria-labelledby="avatar-panel-title">
      <header className="share-panel__head">
        <h2 className="share-panel__title" id="avatar-panel-title">
          Портрет {name ? `· ${name}` : ""}
        </h2>
        <button type="button" className="link-button" onClick={onClose}>
          закрити
        </button>
      </header>
      <p className="share-panel__lead">
        Портрети намальовані для цього сайту. Спершу — ті, що пасують виду, класу й статі героя; змінити можна
        будь-коли.
      </p>

      <fieldset className="avatar-gender" disabled={busy}>
        <legend>Стать героя</legend>
        {(
          [
            [null, "не вказано"],
            ["female", "жіноча"],
            ["male", "чоловіча"],
          ] as const
        ).map(([value, label]) => (
          <label key={label} className={`chip ${gender === value ? "chip--active" : ""}`}>
            <input
              type="radio"
              name="avatar-gender"
              checked={gender === value}
              onChange={() => onGender(value)}
              className="visually-hidden"
            />
            {label}
          </label>
        ))}
      </fieldset>

      <h3 className="avatar-panel__title">Радимо</h3>
      {advice.isPending ? <p className="meta">Підбираємо…</p> : null}
      {advice.error ? <p className="hint hint--warn">Не вдалося отримати поради: {String(advice.error)}</p> : null}
      <ul className="avatar-grid">
        {(advice.data?.items ?? []).map((portrait) => (
          <Tile
            key={portrait.id}
            portrait={portrait}
            selected={portrait.id === selectedId}
            busy={busy}
            onChoose={onChoose}
          />
        ))}
      </ul>
      {current?.chosen ? (
        <p>
          <button type="button" className="link-button" disabled={busy} onClick={() => onChoose(null)}>
            Повернути типовий портрет
          </button>
        </p>
      ) : null}

      {!showAll ? (
        <button type="button" className="button" onClick={() => setShowAll(true)}>
          Усі портрети
        </button>
      ) : (
        <>
          <h3 className="avatar-panel__title">
            Усі портрети{catalog.data ? <span className="meta"> · знайдено {all.length}</span> : null}
          </h3>
          {catalog.isPending ? <p className="meta">Завантажуємо каталог…</p> : null}
          {catalog.data ? (
            <div className="avatar-filters">
              <label className="field field--small">
                <span>Вид</span>
                <select value={group} onChange={(event) => filter(() => setGroup(event.target.value))}>
                  <option value="">усі</option>
                  {catalog.data.groups.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field field--small">
                <span>Клас</span>
                <select value={klass} onChange={(event) => filter(() => setKlass(event.target.value))}>
                  <option value="">усі</option>
                  {catalog.data.classes.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field field--small">
                <span>Стать</span>
                <select
                  value={look}
                  onChange={(event) => filter(() => setLook(event.target.value as "" | "f" | "m" | "x"))}
                >
                  <option value="">усі</option>
                  <option value="f">жіночі</option>
                  <option value="m">чоловічі</option>
                  <option value="x">без ознак статі</option>
                </select>
              </label>
            </div>
          ) : null}
          <ul className="avatar-grid">
            {all.slice(0, shown).map((portrait) => (
              <Tile
                key={portrait.id}
                portrait={portrait}
                selected={portrait.id === selectedId}
                busy={busy}
                onChoose={onChoose}
              />
            ))}
          </ul>
          {all.length > shown ? (
            <button type="button" className="button" onClick={() => setShown((count) => count + PAGE)}>
              Показати ще {Math.min(PAGE, all.length - shown)}
            </button>
          ) : null}
        </>
      )}
    </section>
  );
}

export default AvatarPicker;

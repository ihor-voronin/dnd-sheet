/**
 * Адреси довідника. Довідник — серверні сторінки `/kb/<розділ>/<запис>` (бекенд,
 * `backend/src/dndsheet/site`), а не екран SPA: у кожного запису одна адреса, яку
 * бачать і люди, і пошуковики. Старі посилання `#/kb/...` SPA переводить сюди.
 */

export const KB_SECTIONS = ["species", "classes", "backgrounds", "feats", "spells", "options", "items"] as const;
export type KbSection = (typeof KB_SECTIONS)[number];

export function isKbSection(value: string | undefined): value is KbSection {
  return KB_SECTIONS.includes(value as KbSection);
}

/** Як `slugify` на сервері (`site/domain/publication.py`): «Abi-Dalzim's Horrid Wilting» → `abi-dalzims-horrid-wilting`. */
export function kbSlug(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/['’ʼ`]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Сторінка розділу чи запису. Ключ — як у старих адресах SPA: id запису
 * довідника («phb-2014/spell/fireball» — береться хвіст) або ключ виду, класу,
 * передісторії («hill dwarf»). Хвости з різних книг сервер сам переадресує.
 */
export function kbUrl(section?: string, key?: string): string {
  if (!section || !isKbSection(section)) return "/kb";
  if (!key) return `/kb/${section}`;
  const slug = kbSlug(key.split("/").pop() ?? key);
  return slug ? `/kb/${section}/${slug}` : `/kb/${section}`;
}

/** Перейти на серверну сторінку (повне завантаження, не маршрут SPA). */
export function openServerPage(url: string): void {
  window.location.assign(url);
}

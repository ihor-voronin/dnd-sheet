/** Стартове спорядження класів (PHB 2014, розділ «Equipment» кожного класу).
 *
 * У корпусі це лише текст («(a) a rapier or (b) a shortsword»), тому вибір
 * описано тут структурно: рядок — це вибір між варіантами, варіант — набір
 * предметів. Назви предметів — **точно як у довіднику** (`Leather`, а не
 * «leather armor»; `Crossbow, light`), щоб крок «Спорядження» знаходив їх і
 * брав вагу, урон і КЗ з книги.
 *
 * Набори спорядження (Burglar's Pack тощо) у довіднику окремими записами
 * немає — вони додаються одним предметом із переліком вмісту в нотатках.
 * «Будь-яка проста зброя» не додається сама: гравець обирає її в каталозі.
 */

export type StartingItem =
  | { name: string; qty?: number }
  | { pack: PackKey }
  | { any: string };

export interface StartingOption {
  label: string;
  items: StartingItem[];
}

/** Рядок спорядження: один варіант — без вибору; кілька — (a)/(b)/(c). */
export type StartingRow = StartingOption[];

export type PackKey =
  | "burglar"
  | "diplomat"
  | "dungeoneer"
  | "entertainer"
  | "explorer"
  | "priest"
  | "scholar";

export const PACKS: Record<PackKey, { name_en: string; label: string; weight: number; contents: string }> = {
  burglar: {
    name_en: "Burglar's Pack",
    label: "Набір зломщика",
    weight: 44.5,
    contents:
      "рюкзак, мішечок з 1000 кульок, 10 фт мотузки, дзвіночок, 5 свічок, ломик, молоток, 10 кілків, ліхтар із заслінкою, 2 фляги олії, 5 днів раціону, трутниця, бурдюк, 50 фт пенькової мотузки",
  },
  diplomat: {
    name_en: "Diplomat's Pack",
    label: "Набір дипломата",
    weight: 36,
    contents:
      "скриня, 2 футляри для мап і сувоїв, вишуканий одяг, пляшечка чорнил, перо, лампа, 2 фляги олії, 5 аркушів паперу, флакон парфумів, сургуч, мило",
  },
  dungeoneer: {
    name_en: "Dungeoneer's Pack",
    label: "Набір підземельника",
    weight: 61.5,
    contents:
      "рюкзак, ломик, молоток, 10 кілків, 10 смолоскипів, трутниця, 10 днів раціону, бурдюк, 50 фт пенькової мотузки",
  },
  entertainer: {
    name_en: "Entertainer's Pack",
    label: "Набір артиста",
    weight: 38,
    contents: "рюкзак, спальник, 2 костюми, 5 свічок, 5 днів раціону, бурдюк, набір для гриму",
  },
  explorer: {
    name_en: "Explorer's Pack",
    label: "Набір дослідника",
    weight: 59,
    contents:
      "рюкзак, спальник, казанок, трутниця, 10 смолоскипів, 10 днів раціону, бурдюк, 50 фт пенькової мотузки",
  },
  priest: {
    name_en: "Priest's Pack",
    label: "Набір священника",
    weight: 24,
    contents:
      "рюкзак, ковдра, 10 свічок, трутниця, скринька для пожертв, 2 бруски ладану, кадило, облачення, 2 дні раціону, бурдюк",
  },
  scholar: {
    name_en: "Scholar's Pack",
    label: "Набір учня",
    weight: 10,
    contents:
      "рюкзак, книга знань, пляшечка чорнил, перо, 10 аркушів пергаменту, мішечок піску, маленький ніж",
  },
};

const pack = (key: PackKey): StartingOption => ({ label: PACKS[key].label, items: [{ pack: key }] });
const one = (label: string, ...items: StartingItem[]): StartingOption => ({ label, items });
const fixed = (label: string, ...items: StartingItem[]): StartingRow => [one(label, ...items)];

const LIGHT_CROSSBOW = one(
  "легкий арбалет і 20 болтів",
  { name: "Crossbow, light" },
  { name: "Crossbow bolts (20)" },
);
const FOCUS: StartingRow = [
  one("мішечок компонентів", { name: "Component pouch" }),
  one("магічний фокус (кристал)", { name: "Crystal" }),
  one("магічний фокус (жезл)", { name: "Wand" }),
  one("магічний фокус (куля)", { name: "Orb" }),
];

export const STARTING_EQUIPMENT: Record<string, StartingRow[]> = {
  // Артифіцер (TCoE, p. 10).
  artificer: [
    fixed("дві будь-які прості зброї", { any: "дві прості зброї" }),
    [LIGHT_CROSSBOW],
    [one("шипована шкіряна броня", { name: "Studded leather" }), one("лускатий обладунок", { name: "Scale mail" })],
    fixed("злодійські інструменти й набір підземельника", { name: "Thieves' tools" }, { pack: "dungeoneer" }),
  ],
  barbarian: [
    [one("велика сокира", { name: "Greataxe" }), one("будь-яка військова зброя ближнього бою", { any: "військова зброя ближнього бою" })],
    [one("дві ручні сокири", { name: "Handaxe", qty: 2 }), one("будь-яка проста зброя", { any: "проста зброя" })],
    fixed("набір дослідника і 4 сулиці", { pack: "explorer" }, { name: "Javelin", qty: 4 }),
  ],
  bard: [
    [one("рапіра", { name: "Rapier" }), one("довгий меч", { name: "Longsword" }), one("будь-яка проста зброя", { any: "проста зброя" })],
    [pack("diplomat"), pack("entertainer")],
    [one("лютня", { name: "Lute" }), one("інший музичний інструмент", { any: "музичний інструмент" })],
    fixed("шкіряна броня і кинджал", { name: "Leather" }, { name: "Dagger" }),
  ],
  cleric: [
    [one("булава", { name: "Mace" }), one("бойовий молот (якщо володієте)", { name: "Warhammer" })],
    [
      one("лускатий обладунок", { name: "Scale mail" }),
      one("шкіряна броня", { name: "Leather" }),
      one("кольчуга (якщо володієте)", { name: "Chain mail" }),
    ],
    [LIGHT_CROSSBOW, one("будь-яка проста зброя", { any: "проста зброя" })],
    [pack("priest"), pack("explorer")],
    fixed("щит і священний символ", { name: "Shield" }, { name: "Amulet" }),
  ],
  druid: [
    [one("деревʼяний щит", { name: "Shield" }), one("будь-яка проста зброя", { any: "проста зброя" })],
    [one("скимітар", { name: "Scimitar" }), one("будь-яка проста зброя ближнього бою", { any: "проста зброя ближнього бою" })],
    fixed(
      "шкіряна броня, набір дослідника, друїдський фокус",
      { name: "Leather" },
      { pack: "explorer" },
      { name: "Sprig of mistletoe" },
    ),
  ],
  fighter: [
    [
      one("кольчуга", { name: "Chain mail" }),
      one("шкіряна броня, довгий лук і 20 стріл", { name: "Leather" }, { name: "Longbow" }, { name: "Arrows (20)" }),
    ],
    [
      one("військова зброя і щит", { any: "військова зброя" }, { name: "Shield" }),
      one("дві військові зброї", { any: "дві військові зброї" }),
    ],
    [LIGHT_CROSSBOW, one("дві ручні сокири", { name: "Handaxe", qty: 2 })],
    [pack("dungeoneer"), pack("explorer")],
  ],
  monk: [
    [one("короткий меч", { name: "Shortsword" }), one("будь-яка проста зброя", { any: "проста зброя" })],
    [pack("dungeoneer"), pack("explorer")],
    fixed("10 дротиків", { name: "Dart", qty: 10 }),
  ],
  paladin: [
    [
      one("військова зброя і щит", { any: "військова зброя" }, { name: "Shield" }),
      one("дві військові зброї", { any: "дві військові зброї" }),
    ],
    [one("5 сулиць", { name: "Javelin", qty: 5 }), one("будь-яка проста зброя ближнього бою", { any: "проста зброя ближнього бою" })],
    [pack("priest"), pack("explorer")],
    fixed("кольчуга і священний символ", { name: "Chain mail" }, { name: "Amulet" }),
  ],
  ranger: [
    [one("лускатий обладунок", { name: "Scale mail" }), one("шкіряна броня", { name: "Leather" })],
    [one("два короткі мечі", { name: "Shortsword", qty: 2 }), one("дві прості зброї ближнього бою", { any: "дві прості зброї ближнього бою" })],
    [pack("dungeoneer"), pack("explorer")],
    fixed("довгий лук і сагайдак із 20 стрілами", { name: "Longbow" }, { name: "Quiver" }, { name: "Arrows (20)" }),
  ],
  rogue: [
    [one("рапіра (шпага)", { name: "Rapier" }), one("короткий меч", { name: "Shortsword" })],
    [
      one("короткий лук і сагайдак із 20 стрілами", { name: "Shortbow" }, { name: "Quiver" }, { name: "Arrows (20)" }),
      one("короткий меч", { name: "Shortsword" }),
    ],
    [pack("burglar"), pack("dungeoneer"), pack("explorer")],
    fixed(
      "шкіряна броня, два кинджали й злодійські інструменти",
      { name: "Leather" },
      { name: "Dagger", qty: 2 },
      { name: "Thieves' tools" },
    ),
  ],
  sorcerer: [
    [LIGHT_CROSSBOW, one("будь-яка проста зброя", { any: "проста зброя" })],
    FOCUS,
    [pack("dungeoneer"), pack("explorer")],
    fixed("два кинджали", { name: "Dagger", qty: 2 }),
  ],
  warlock: [
    [LIGHT_CROSSBOW, one("будь-яка проста зброя", { any: "проста зброя" })],
    FOCUS,
    [pack("scholar"), pack("dungeoneer")],
    fixed(
      "шкіряна броня, будь-яка проста зброя і два кинджали",
      { name: "Leather" },
      { any: "проста зброя" },
      { name: "Dagger", qty: 2 },
    ),
  ],
  wizard: [
    [one("бойовий посох", { name: "Quarterstaff" }), one("кинджал", { name: "Dagger" })],
    FOCUS,
    [pack("scholar"), pack("explorer")],
    fixed("книга заклять", { name: "Spellbook" }),
  ],
};

export function startingEquipmentFor(classKey: string | null | undefined): StartingRow[] | null {
  if (!classKey) return null;
  const slug = classKey.toLowerCase().split("/").pop() ?? classKey;
  return STARTING_EQUIPMENT[slug] ?? null;
}

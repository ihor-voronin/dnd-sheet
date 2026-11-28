import { describe, expect, it } from "vitest";

import { isKbSection, kbSlug, kbUrl } from "./kbLinks";

describe("compendium addresses", () => {
  it("makes the same slugs as the server", () => {
    expect(kbSlug("Fireball")).toBe("fireball");
    expect(kbSlug("Abi-Dalzim's Horrid Wilting")).toBe("abi-dalzims-horrid-wilting");
    expect(kbSlug("Ashardalon’s Stride")).toBe("ashardalons-stride");
    expect(kbSlug("dragonborn (chromatic)")).toBe("dragonborn-chromatic");
    expect(kbSlug("hill dwarf")).toBe("hill-dwarf");
  });

  it("turns old SPA keys into real pages", () => {
    expect(kbUrl()).toBe("/kb");
    expect(kbUrl("monsters")).toBe("/kb");
    expect(kbUrl("spells")).toBe("/kb/spells");
    // Старі ключі заклять — id запису: береться хвіст, інші книги сервер переадресує.
    expect(kbUrl("spells", "phb-2014/spell/fireball")).toBe("/kb/spells/fireball");
    expect(kbUrl("species", "dragonborn (chromatic)")).toBe("/kb/species/dragonborn-chromatic");
    expect(kbUrl("backgrounds", "folk hero")).toBe("/kb/backgrounds/folk-hero");
    expect(kbUrl("classes", "’")).toBe("/kb/classes");
  });

  it("knows the sections", () => {
    expect(isKbSection("options")).toBe(true);
    expect(isKbSection("rules")).toBe(false);
    expect(isKbSection(undefined)).toBe(false);
  });
});

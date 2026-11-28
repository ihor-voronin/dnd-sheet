import { describe, expect, it } from "vitest";

import { KB_LABELS_VERSION, kbLabels } from "./kbLabels";

describe("dictionaries for the server-rendered compendium", () => {
  it("exports what the pages need, with the app's keys", () => {
    const labels = kbLabels();
    expect(labels.version).toBe(KB_LABELS_VERSION);
    expect(labels.terms.warlock).toBe("Чаклун");
    expect(labels.species.dwarf).toBeTruthy();
    expect(labels.skills.athletics).toBe("Атлетика");
    expect(labels.glossary.hit_die.term).toBeTruthy();
    expect(labels.class_guide.wizard.primary).toContain("int");
    // Звірене з SRD важить більше за великий словник — як у `ukItem`.
    for (const [key, name] of Object.entries(labels.items).slice(0, 50)) {
      expect(typeof name).toBe("string");
      expect(key).toBe(key.toLowerCase());
    }
  });
});

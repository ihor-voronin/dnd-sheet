import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { explore } from "../../test/explore";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { body, ids } from "../../test/tape";

type Step = "species" | "class" | "abilities" | "background" | "equipment" | "spells";

/** Open a recorded draft at a step (the recorded draft says where it stopped; we say where to go). */
async function openStep(step: Step, draft = "draft-gnome-wizard") {
  const draftId = ids[draft];
  const saved = body<{ draft: Record<string, unknown> }>("GET", `/api/v1/characters/wizard/drf_any`);
  override("GET", `/api/v1/characters/wizard/${draftId}$`, {
    status: 200,
    body: { draft: { ...saved.draft, id: draftId, next_step: step } },
  });
  window.localStorage.setItem("dndsheet.draft", draftId);
  const app = await renderApp("#/create");
  await waitFor(() => expect(requests.some((item) => item.url.endsWith(`/steps/${step}`))).toBe(true));
  await waitFor(() => expect(document.querySelector(".wizard-step, .wizard-block")).not.toBeNull());
  return app;
}

const step = () => document.querySelector("main") as HTMLElement;

/** Every chip and select inside the blocks a choice revealed (spread, choices, sources). */
async function workBlocks(user: Awaited<ReturnType<typeof openStep>>["user"]) {
  for (const block of Array.from(document.querySelectorAll<HTMLElement>(".wizard-block"))) {
    for (const chip of within(block).queryAllByRole("button")) {
      if (chip.isConnected && !(chip as HTMLButtonElement).disabled && /chip/.test(chip.className))
        await user.click(chip);
    }
    for (const select of within(block).queryAllByRole("combobox") as HTMLSelectElement[]) {
      if (select.isConnected && select.options.length > 1) {
        await user.selectOptions(select, select.options[select.options.length - 1].value);
      }
    }
  }
}

describe("species step", () => {
  it("opens every species and subspecies with its details", async () => {
    const { user } = await openStep("species");
    const names = Array.from(step().querySelectorAll<HTMLButtonElement>("button[aria-label]")).map((button) =>
      button.getAttribute("aria-label"),
    );
    expect(names.length).toBeGreaterThan(3);
    for (const name of names) {
      const card = step().querySelector<HTMLButtonElement>(`button[aria-label="${name}"]`);
      if (!card) continue;
      await user.click(card);
      const children = Array.from(step().querySelectorAll<HTMLButtonElement>("button[aria-label]")).filter(
        (button) => !names.includes(button.getAttribute("aria-label")),
      );
      for (const child of children) {
        if (!child.isConnected) continue;
        await user.click(child);
        await workBlocks(user);
      }
      await workBlocks(user);
    }
    expect(step()).toBeInTheDocument();
  });

  it("filters species by search and names the character", async () => {
    const { user } = await openStep("species");
    const search = screen.getByPlaceholderText(/Пошук виду/);
    await user.type(search, "gnome");
    await user.clear(search);
    await user.type(search, "нічого такого");
    await user.clear(search);
    await user.type(screen.getByPlaceholderText(/Дарія/), "Тікі");
    // Людина не просить нічого більше (підраси, рис), тож крок можна відправити.
    const human = step().querySelector<HTMLButtonElement>('button[aria-label="Human"]');
    if (human) await user.click(human);
    // Стать — необовʼязкова, лише для порад портрета; іде в тій самій відповіді кроку.
    await user.selectOptions(screen.getByRole("combobox", { name: "Стать (необовʼязково)" }), "female");
    // Сама кнопка кроку (не «Далі» в панелі переходів — та лише гортає до неї).
    const next = screen
      .getAllByRole("button", { name: /^Далі: клас/ })
      .find((button) => button.classList.contains("button--primary")) as HTMLButtonElement;
    expect(next).toBeEnabled();
    await user.click(next);
    await waitFor(() =>
      expect(
        requests.filter((item) => item.method === "PUT" && item.url.endsWith("/steps/species")).at(-1)?.body,
      ).toMatchObject({ gender: "female" }),
    );
    const grid = screen.queryAllByRole("button", { name: /усі види|сіткою|списком/i });
    for (const button of grid) await user.click(button);
  });

  it("splits the bonuses of a species without fixed ones", async () => {
    const { user } = await openStep("species");
    // The MotM deep gnome is its own card (the last one), besides the gnome subrace.
    const card = Array.from(step().querySelectorAll<HTMLButtonElement>("button[aria-label]"))
      .filter((button) => /deep gnome/i.test(button.getAttribute("aria-label") ?? ""))
      .pop();
    expect(card).toBeDefined();
    await user.click(card!);
    expect(await screen.findByRole("button", { name: "+2 і +1" })).toBeInTheDocument();
    for (const mode of ["+1, +1 і +1", "+2 і +1"]) {
      const button = screen.queryByRole("button", { name: mode });
      if (button) {
        await user.click(button);
        await workBlocks(user);
      }
    }
    const next = screen
      .getAllByRole("button", { name: /^Далі/ })
      .find((button) => !(button as HTMLButtonElement).disabled);
    if (next) await user.click(next);
  });
});

describe("other steps", () => {
  it.each([
    ["class", "draft-gnome-wizard"],
    ["class", "draft-elf-fighter"],
    ["abilities", "draft-gnome-wizard"],
    ["abilities", "draft-elf-fighter"],
    ["background", "draft-gnome-wizard"],
    ["equipment", "draft-elf-fighter"],
    ["equipment", "draft-gnome-wizard"],
    ["spells", "draft-gnome-wizard"],
    ["spells", "draft-elf-fighter"],
  ] as const)("works through %s of %s", async (name, draft) => {
    const { user } = await openStep(name, draft);
    await workBlocks(user);
    // Only the step itself: the step bar above it would jump to other steps.
    await explore(user, document.querySelector<HTMLElement>(".wizard-step") ?? step(), {
      rounds: 5,
      maxClicks: 250,
      skip: /^(← |Мої персонажі|Довідник|Знайшли помилку|Світла тема|Темна тема|Почати)/,
    });
    expect(step()).toBeInTheDocument();
  });

  it.each(["standard_array", "point_buy", "manual", "roll"])("switches the abilities method to %s", async (method) => {
    const { user } = await openStep("abilities");
    const radios = screen.queryAllByRole("radio");
    const buttons = screen.queryAllByRole("button").filter((button) => /chip|method/.test(button.className));
    for (const control of [...radios, ...buttons]) {
      if (control.isConnected && (control.getAttribute("value") === method || control.textContent?.length)) {
        await user.click(control);
      }
    }
    for (const field of screen.queryAllByRole("spinbutton")) {
      await user.clear(field);
      await user.type(field, "14");
    }
    for (const select of screen.queryAllByRole("combobox") as HTMLSelectElement[]) {
      if (select.options.length > 1) await user.selectOptions(select, select.options[1].value);
    }
  });
});

import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { explore } from "../../test/explore";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { ids } from "../../test/tape";

const CHARACTERS = [
  "fighter-1",
  "warlock-1",
  "fighter-2-wizard-3",
  "wizard-4",
  "warlock-5",
  "cleric-5",
  "multiclass-14",
];

async function openLevelUp(key: string) {
  const app = await renderApp(`#/character/${ids[key]}/level-up`);
  await waitFor(() => expect(requests.some((item) => item.url.endsWith("/level-up"))).toBe(true));
  await screen.findAllByRole("button", { name: /до листа/ });
  return app;
}

describe("level up", () => {
  it.each(CHARACTERS)("plans the next level of %s", async (key) => {
    const { user } = await openLevelUp(key);
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 4, maxClicks: 200 });
    expect(document.querySelector("main")).toBeInTheDocument();
  });

  it("applies a level and reports what it gave", async () => {
    const { user } = await openLevelUp("fighter-1");
    // Step 1 is the class: the plan (and the apply button) shows up after it.
    await user.click(screen.getByRole("button", { name: /Воїн \(Fighter\) 1 → 2/ }));
    await waitFor(() => expect(document.querySelector(".button--seal")).not.toBeNull());
    await user.click(document.querySelector<HTMLButtonElement>(".button--seal")!);
    await waitFor(() =>
      expect(requests.some((item) => item.method === "POST" && item.url.endsWith("/level-up"))).toBe(true),
    );
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2 });
  });

  it("levels a cleric and prepares the day's spells right away", async () => {
    const { user } = await openLevelUp("cleric-5");
    await user.click(screen.getByRole("button", { name: /Жрець \(Cleric\) 5 → 6/ }));
    await waitFor(() => expect(document.querySelector(".button--seal")).not.toBeNull());
    // An ability score improvement level asks for +2 / +1+1 / a feat first.
    for (const mode of screen.queryAllByRole("button", { name: /\+2|\+1 і \+1|риса/i })) await user.click(mode);
    for (const select of screen.queryAllByRole("combobox") as HTMLSelectElement[]) {
      if (select.options.length > 1) await user.selectOptions(select, select.options[1].value);
    }
    const twoMode = screen.queryAllByRole("button", { name: /^\+2/ })[0];
    if (twoMode) await user.click(twoMode);
    const seal = document.querySelector<HTMLButtonElement>(".button--seal")!;
    if (!seal.disabled) await user.click(seal);
    expect(await screen.findByRole("heading", { name: /Рівень піднято/ })).toBeInTheDocument();
    const panel = document.querySelector<HTMLElement>(".levelup")!;
    await explore(user, panel, { rounds: 3, skip: /^До листа/ });
    await user.click(screen.getByRole("button", { name: "До листа" }));
    await waitFor(() => expect(window.location.hash).toBe(`#/character/${ids["cleric-5"]}`));
  });

  it("says there's nothing to take at level 20", async () => {
    override("GET", `/api/v1/characters/${ids["fighter-1"]}/level-up`, {
      status: 200,
      body: { name: "Ветеран", version: 9, can_level_up: false, plans: [] },
    });
    const { user } = await renderApp(`#/character/${ids["fighter-1"]}/level-up`);
    expect(await screen.findByText(/на 20 рівні/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "← До листа" }));
  });

  it("explains a refused level-up", async () => {
    override("POST", `/api/v1/characters/${ids["fighter-1"]}/level-up`, {
      status: 422,
      body: { detail: "Оберіть характеристику" },
    });
    const { user } = await openLevelUp("fighter-1");
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 3 });
  });

  it("goes back to the sheet", async () => {
    const { user } = await openLevelUp("cleric-5");
    await user.click(screen.getAllByRole("button", { name: /до листа/ })[0]);
    await waitFor(() => expect(window.location.hash).toBe(`#/character/${ids["cleric-5"]}`));
  });

  it("says when the plan can't be loaded", async () => {
    override("GET", `/api/v1/characters/${ids["cleric-5"]}/level-up`, { status: 500, body: { detail: "збій" } });
    await renderApp(`#/character/${ids["cleric-5"]}/level-up`);
    expect(await screen.findByText(/збій/)).toBeInTheDocument();
  });
});

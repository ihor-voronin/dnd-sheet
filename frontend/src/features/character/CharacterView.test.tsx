import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { explore } from "../../test/explore";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { ids } from "../../test/tape";

const TABS = ["Дії", "Закляття", "Інвентар", "Уміння", "Передісторія", "Нотатки"];

async function openSheet(key: string, tab?: string) {
  const app = await renderApp(`#/character/${ids[key]}${tab ? `?tab=${tab}` : ""}`);
  await screen.findByRole("button", { name: "Дії" });
  return app;
}

describe("character sheet", () => {
  it.each(["fighter-1", "warlock-5", "cleric-5", "multiclass-14", "wizard-4", "fighter-2-wizard-3"])(
    "renders every tab of %s",
    async (key) => {
      const { user } = await openSheet(key);
      for (const name of TABS) {
        const tab = screen.getByRole("button", { name });
        await user.click(tab);
        expect(tab).toHaveAttribute("aria-current", "page");
      }
    },
  );

  it.each(
    TABS.map((name, index) => [name, ["actions", "spells", "inventory", "features", "background", "notes"][index]]),
  )("lets a player use the %s tab", async (_name, tab) => {
    const { user } = await openSheet("cleric-5", tab);
    // The tab's own body first (the tab bar would switch away), then the whole sheet.
    await explore(user, document.querySelector<HTMLElement>(".sheet-work__body")!, { rounds: 3 });
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2 });
    expect(screen.getByRole("button", { name: "Дії" })).toBeInTheDocument();
  });

  it("lets a warlock use the class choices and the spells tab", async () => {
    const { user } = await openSheet("warlock-5", "features");
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 3 });
    await user.click(screen.getByRole("button", { name: "Закляття" }));
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2 });
    expect(screen.getByRole("button", { name: "Закляття" })).toBeInTheDocument();
  });

  it("lets a rogue pick expertise", async () => {
    const { user } = await openSheet("rogue-6");
    const picker = document.querySelector(".expertise") as HTMLElement;
    expect(picker).not.toBeNull();
    const change = within(picker).queryByRole("button", { name: "змінити" });
    if (change) await user.click(change);
    for (const chip of within(picker).getAllByRole("button", { pressed: false }).slice(0, 2)) await user.click(chip);
    await user.click(within(picker).getByRole("button", { name: /Зберегти експертизу/ }));
    await waitFor(() => expect(requests.some((item) => item.url.endsWith("/expertise"))).toBe(true));
  });

  it.each(["warlock-5", "wizard-4", "rogue-6", "variant-human", "fighter-2-wizard-3"])(
    "lets a player use every tab of %s",
    async (key) => {
      const { user } = await openSheet(key);
      for (const name of TABS) {
        await user.click(screen.getByRole("button", { name }));
        await explore(user, document.querySelector<HTMLElement>(".sheet-work__body")!, { rounds: 2, maxClicks: 60 });
      }
    },
  );

  it("explores a multiclass sheet", async () => {
    const { user } = await openSheet("multiclass-14", "spells");
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2 });
    await user.click(screen.getByRole("button", { name: "Уміння" }));
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2 });
  });

  it.each([
    ["Тривалий відпочинок", /Тривалий відпочинок ·/],
    ["Короткий відпочинок", /Короткий відпочинок ·/],
  ])("takes a rest (%s) and reports what came back", async (name, note) => {
    const { user } = await openSheet("warlock-5");
    await user.click(screen.getByRole("button", { name: "Дії з листом" }));
    await user.click(screen.getByRole("button", { name }));
    expect(await screen.findByText(note)).toBeInTheDocument();
  });

  it("explains a refused rest", async () => {
    override("POST", `/api/v1/characters/${ids["cleric-5"]}/rest`, { status: 500, body: { detail: "Сервер спить" } });
    const { user } = await openSheet("cleric-5");
    await user.click(screen.getByRole("button", { name: "Тривалий відпочинок" }));
    expect(await screen.findByText("Сервер спить")).toBeInTheDocument();
  });

  it("removes a known spell and marks slots used", async () => {
    const { user } = await openSheet("cleric-5", "spells");
    const remove = screen.queryAllByRole("button", { name: /прибрати|забути|×/i });
    if (remove.length) await user.click(remove[remove.length - 1]);
    const slots = document.querySelectorAll<HTMLElement>(".slot, .slot-box, input[type=checkbox]");
    for (const slot of Array.from(slots).slice(0, 3)) await user.click(slot);
    await waitFor(() => expect(requests.some((item) => item.method !== "GET")).toBe(true));
  });

  it("refreshes the sheet after a version conflict", async () => {
    override("PATCH", `/api/v1/characters/${ids["cleric-5"]}`, {
      status: 409,
      body: { detail: "Лист змінено на іншому пристрої (версія застаріла)" },
    });
    const { user } = await openSheet("cleric-5");
    await explore(user, document.querySelector(".sheet-hp, main") as HTMLElement, { rounds: 1, maxClicks: 25 });
    expect(screen.getByRole("button", { name: "Дії" })).toBeInTheDocument();
  });

  it("shows a server error instead of crashing", async () => {
    override("POST", `/api/v1/characters/${ids["cleric-5"]}/`, { status: 422, body: { detail: "Так не можна" } });
    override("PATCH", `/api/v1/characters/${ids["cleric-5"]}`, { status: 422, body: { detail: "Так не можна" } });
    const { user } = await openSheet("cleric-5");
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2, maxClicks: 60 });
    expect(screen.getByRole("button", { name: "Дії" })).toBeInTheDocument();
  });

  it("opens a shared sheet read-only", async () => {
    override("GET", "/api/v1/auth/me", { status: 200, body: { user: null } });
    const { user } = await renderApp("#/s/token-1");
    await screen.findByRole("button", { name: "Дії" });
    for (const name of TABS) await user.click(screen.getByRole("button", { name }));
    const main = document.querySelector("main") as HTMLElement;
    expect(within(main).getAllByRole("button").length).toBeGreaterThan(5);
  });
});

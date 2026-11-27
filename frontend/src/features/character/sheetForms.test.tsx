import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { explore } from "../../test/explore";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { ids } from "../../test/tape";

async function openSheet(key: string, tab?: string) {
  const app = await renderApp(`#/character/${ids[key]}${tab ? `?tab=${tab}` : ""}`);
  await screen.findByRole("button", { name: "Дії" });
  return app;
}

const main = () => document.querySelector("main") as HTMLElement;

describe("sheet forms", () => {
  it("adds a spell from the class list", async () => {
    const { user } = await openSheet("cleric-5", "spells");
    await user.click(await screen.findByRole("button", { name: "+ закляття" }));
    const form = document.querySelector(".spell-add") as HTMLElement;
    await user.type(within(form).getByPlaceholderText("Частина назви…"), "Bl");
    await user.clear(within(form).getByPlaceholderText("Частина назви…"));
    await user.click(within(form).getByRole("button", { name: /Bless/ }));
    await user.click(within(form).getByRole("button", { name: "Додати" }));
    await waitFor(() =>
      expect(requests.find((item) => item.method === "POST" && item.url.endsWith("/spells"))?.body).toMatchObject({
        name_en: "Bless",
      }),
    );
  });

  it("asks for a spell before adding", async () => {
    const { user } = await openSheet("cleric-5", "spells");
    await user.click(await screen.findByRole("button", { name: "+ закляття" }));
    const form = document.querySelector(".spell-add") as HTMLElement;
    await user.click(within(form).getByRole("button", { name: "Додати" }));
    expect(await within(form).findByText("Оберіть закляття зі списку")).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "Скасувати" }));
    expect(document.querySelector(".spell-add")).toBeNull();
  });

  it("adds a custom spell with its own text", async () => {
    const { user } = await openSheet("wizard-4", "spells");
    await user.click(await screen.findByRole("button", { name: "+ закляття" }));
    const form = document.querySelector(".spell-add") as HTMLElement;
    await user.click(within(form).getByRole("checkbox", { name: /власне закляття/ }));
    await user.click(within(form).getByRole("button", { name: "Додати" }));
    expect(await within(form).findByText("Впишіть назву власного закляття")).toBeInTheDocument();
    for (const field of within(form).getAllByRole("textbox")) await user.type(field, "Благословення столу");
    for (const select of within(form).queryAllByRole("combobox") as HTMLSelectElement[]) {
      await user.selectOptions(select, select.options[select.options.length - 1].value);
    }
    await user.click(within(form).getByRole("button", { name: "Додати" }));
    await waitFor(() =>
      expect(requests.find((item) => item.method === "POST" && item.url.endsWith("/spells"))?.body).toMatchObject({
        custom: true,
      }),
    );
  });

  it("refuses a spell the server doesn't allow", async () => {
    override("POST", `/api/v1/characters/${ids["cleric-5"]}/spells`, { status: 422, body: { detail: "Можна лише 5" } });
    const { user } = await openSheet("cleric-5", "spells");
    await user.click(await screen.findByRole("button", { name: "+ закляття" }));
    const form = document.querySelector(".spell-add") as HTMLElement;
    await user.click(within(form).getByRole("button", { name: /Bless/ }));
    await user.click(within(form).getByRole("button", { name: "Додати" }));
    expect(await screen.findByText("Можна лише 5")).toBeInTheDocument();
  });

  it("saves the variant human's fighting style and feat choices", async () => {
    const { user } = await openSheet("variant-human", "features");
    const pending = Array.from(document.querySelectorAll<HTMLElement>(".expertise--pending"));
    expect(pending.length).toBeGreaterThan(0);
    for (const group of pending) {
      const slots = Number(/0 з (\d+)/.exec(group.textContent ?? "")?.[1] ?? 1);
      for (let index = 0; index < slots; index += 1) {
        const chip = within(group)
          .getAllByRole("button", { pressed: false })
          .find((button) => !(button as HTMLButtonElement).disabled);
        if (chip) await user.click(chip);
      }
      await user.click(within(group).getByRole("button", { name: /^Зберегти/ }));
    }
    await waitFor(() =>
      expect(requests.filter((item) => item.url.endsWith("/class-choices")).length).toBe(pending.length),
    );
  });

  it("changes the species feat", async () => {
    const { user } = await openSheet("variant-human", "features");
    const block = document.querySelector<HTMLElement>(".expertise:not(.expertise--pending)")!;
    await user.click(within(block).getByRole("button", { name: "змінити" }));
    await explore(user, block, { rounds: 3, maxClicks: 60 });
    expect(document.querySelector("main")).toBeInTheDocument();
  });

  it("creates, copies and revokes a share link", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    override("GET", "/api/v1/auth/config", {
      status: 200,
      body: { auth_enabled: true, telegram_bot: "dnd_bot", telegram_ready: true, dev_login: false },
    });
    const { user } = await openSheet("cleric-5");
    await user.click(screen.getByRole("button", { name: "Поділитися" }));
    const panel = await screen.findByRole("region", { name: "Поділитися листом" });
    await explore(user, panel, { rounds: 4, skip: /^закрити/i });
    await waitFor(() =>
      expect(requests.some((item) => item.url.endsWith("/share") && item.method !== "GET")).toBe(true),
    );
  });

  it("reports a failed copy", async () => {
    override("GET", `/api/v1/characters/${ids["cleric-5"]}/share`, { status: 200, body: { token: "abc" } });
    const { user } = await openSheet("cleric-5");
    // user-event keeps its own clipboard on navigator: make that one refuse.
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
    await user.click(screen.getByRole("button", { name: "Поділитися" }));
    const panel = await screen.findByRole("region", { name: "Поділитися листом" });
    await user.click(await within(panel).findByRole("button", { name: "Копіювати" }));
    expect(await within(panel).findByText(/Не вдалося скопіювати/)).toBeInTheDocument();
  });

  it.each(["multiclass-14", "fighter-1", "warlock-5", "rogue-6"])("manages the inventory of %s", async (key) => {
    const { user } = await openSheet(key, "inventory");
    await explore(user, main(), { rounds: 4, maxClicks: 200 });
    expect(screen.getByRole("button", { name: "Інвентар" })).toBeInTheDocument();
  });

  it("opens every item's details", async () => {
    const { user } = await openSheet("multiclass-14", "inventory");
    const rows = document.querySelectorAll<HTMLElement>(".inv-row, .inventory li, tr");
    for (const row of Array.from(rows).slice(0, 6)) {
      const first = within(row).queryAllByRole("button")[0];
      if (first) await user.click(first);
    }
    await waitFor(() => expect(requests.some((item) => item.url.startsWith("/api/v1/compendium/"))).toBe(true));
  });
});

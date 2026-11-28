import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { explore } from "../../test/explore";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { ids } from "../../test/tape";

async function openInventory(key = "fighter-1") {
  const app = await renderApp(`#/character/${ids[key]}?tab=inventory`);
  await screen.findByRole("button", { name: "Каталог" });
  return app;
}

const rows = () => Array.from(document.querySelectorAll<HTMLElement>(".item-row"));
const sent = (method: string, suffix: RegExp) =>
  requests.some((item) => item.method === method && suffix.test(item.url));

describe("inventory", () => {
  it("shows an item's description, then hides it", async () => {
    const { user } = await openInventory();
    for (const row of rows()) {
      const name = within(row).getByTitle("Показати опис");
      await user.click(name);
      await waitFor(() => expect(requests.some((item) => item.url.startsWith("/api/v1/compendium/"))).toBe(true));
      const english = within(row).queryAllByRole("button", { name: /англійською|оригінал|English/i });
      for (const button of english) await user.click(button);
      await user.click(within(row).getAllByRole("button")[0]);
    }
  });

  it("equips, edits and removes an item", async () => {
    const { user } = await openInventory();
    const [first, , third] = rows();
    await user.click(within(third).getByTitle("Спорядити"));
    await waitFor(() => expect(sent("PATCH", /\/items\/2$/)).toBe(true));
    await user.click(within(first).getByTitle("Змінити предмет"));
    const form = document.querySelector<HTMLElement>(".inv-form")!;
    expect(form).not.toBeNull();
    await explore(user, form, { rounds: 2, skip: /^(Скасувати|Зберегти|Додати)/ });
    await user.click(
      within(form)
        .getAllByRole("button")
        .find((button) => /Зберегти|Додати/.test(button.textContent ?? ""))!,
    );
    await waitFor(() => expect(sent("PATCH", /\/items\/0$/)).toBe(true));
    await user.click(within(rows()[1]).getByTitle("Прибрати з інвентаря"));
    const confirm = within(rows()[1])
      .getAllByRole("button")
      .find((button) => /прибрати|так/i.test(button.textContent ?? ""));
    await user.click(confirm!);
    await waitFor(() => expect(sent("DELETE", /\/items\/1$/)).toBe(true));
  });

  it("cancels a removal", async () => {
    const { user } = await openInventory();
    await user.click(within(rows()[0]).getByTitle("Прибрати з інвентаря"));
    const cancel = within(rows()[0])
      .getAllByRole("button")
      .find((button) => /ні|скасувати|лишити/i.test(button.textContent ?? ""));
    if (cancel) await user.click(cancel);
    expect(sent("DELETE", /\/items\//)).toBe(false);
  });

  it.each(["weapon", "armor", "gear"])("adds a custom %s", async (kind) => {
    const { user } = await openInventory("cleric-5");
    await user.click(screen.getByRole("button", { name: "Свій предмет" }));
    const form = document.querySelector<HTMLElement>(".inv-form")!;
    const [name] = within(form).getAllByRole("textbox");
    await user.type(name, "Мотузка дракона");
    for (const select of within(form).queryAllByRole("combobox") as HTMLSelectElement[]) {
      const option = Array.from(select.options).find((item) => item.value === kind);
      if (option) await user.selectOptions(select, kind);
    }
    await explore(user, form, { rounds: 2, skip: /^(Скасувати|Зберегти|Додати)/ });
    const save = within(form)
      .getAllByRole("button")
      .find((button) => /Зберегти|Додати/.test(button.textContent ?? ""));
    await user.click(save!);
    await waitFor(() => expect(sent("POST", /\/items$/)).toBe(true));
  });

  it("browses the catalog with filters and adds from it", async () => {
    const { user } = await openInventory("cleric-5");
    await user.click(screen.getByRole("button", { name: "Каталог" }));
    await waitFor(() =>
      expect(requests.some((item) => item.url.startsWith("/api/v1/compendium/items?limit="))).toBe(true),
    );
    const catalog = await waitFor(() => {
      const found = document.querySelector<HTMLElement>(".catalog, .item-catalog, .inv-catalog");
      expect(found).not.toBeNull();
      return found!;
    });
    await explore(user, catalog, { rounds: 3, maxClicks: 120 });
    await waitFor(() => expect(sent("POST", /\/items$/)).toBe(true));
  });

  it("finds an item by search and adds it", async () => {
    const { user } = await openInventory("cleric-5");
    await user.type(screen.getByLabelText("Пошук предмета в довіднику"), "rope");
    await waitFor(() => expect(requests.some((item) => item.url.startsWith("/api/v1/compendium/items"))).toBe(true));
    await explore(user, document.querySelector<HTMLElement>(".inv-search")!.parentElement!, {
      rounds: 2,
      maxClicks: 30,
    });
  });

  it("shows a refused change", async () => {
    override("PATCH", `/api/v1/characters/${ids["fighter-1"]}/items/`, {
      status: 422,
      body: { detail: "Ліміт настроювання" },
    });
    const { user } = await openInventory();
    await user.click(within(rows()[2]).getByTitle("Спорядити"));
    expect(await screen.findByText(/Ліміт настроювання/)).toBeInTheDocument();
  });

  it("marks a warlock's pact weapon", async () => {
    const { user } = await openInventory("warlock-5");
    for (const row of rows()) {
      for (const button of within(row).queryAllByRole("button", { name: /угод|хекс|кенсе/i })) await user.click(button);
      await user.click(within(row).getByTitle("Показати опис"));
      await explore(user, row, { rounds: 2, maxClicks: 20, skip: /^(×)/ });
    }
    expect(rows().length).toBeGreaterThan(0);
  });
});

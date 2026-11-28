import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { ids, lookup } from "../../test/tape";

async function openSheet(key: string, tab?: string) {
  const app = await renderApp(`#/character/${ids[key]}${tab ? `?tab=${tab}` : ""}`);
  await screen.findByRole("button", { name: "Дії" });
  return app;
}

const sent = (method: string, suffix: string) =>
  requests.filter((item) => item.method === method && item.url.endsWith(suffix)).map((item) => item.body);

describe("custom features", () => {
  it("adds, edits and removes a feature of the table", async () => {
    const { user } = await openSheet("cleric-5", "features");
    await user.click(await screen.findByRole("button", { name: "+ Додати власне вміння" }));
    let form = document.querySelector(".custom-form") as HTMLElement;

    await user.click(within(form).getByRole("button", { name: "Зберегти" }));
    expect(await within(form).findByText("Впишіть назву вміння")).toBeInTheDocument();

    await user.type(within(form).getByPlaceholderText("Наприклад, «Око ворона»"), "Дар майстра");
    await user.type(within(form).getByPlaceholderText(/Своїми словами/), "Раз на день — перекинути кидок.");
    const uses = within(form).getByPlaceholderText("без лічильника");
    await user.type(uses, "0");
    await user.click(within(form).getByRole("button", { name: "Зберегти" }));
    expect(await within(form).findByText(/ціле число від 1 до 99/)).toBeInTheDocument();
    await user.clear(uses);
    await user.type(uses, "1x");
    await user.selectOptions(within(form).getByRole("combobox", { name: "З рівня" }), "3");
    await user.click(within(form).getByRole("button", { name: "Зберегти" }));

    await waitFor(() =>
      expect(sent("POST", "/custom-features")[0]).toEqual({
        feature: {
          name: "Дар майстра",
          text: "Раз на день — перекинути кидок.",
          origin: null,
          level: 3,
          uses: 1,
          recharge: "long",
        },
        version: expect.any(Number),
      }),
    );
    // Відповідь сервера: вміння з позначкою «власне», лічильник — серед ресурсів.
    const card = (await screen.findByText("Дар майстра", { selector: ".feature-name" })).closest(
      "details",
    ) as HTMLElement;
    expect(within(card).getByText("власне")).toBeInTheDocument();
    expect(within(card).getByText(/1 \/ тривалий відпочинок/)).toBeInTheDocument();
    expect(document.querySelector(".feature-resources")?.textContent).toContain("власне");

    await user.click(within(card).getByRole("button", { name: "Змінити" }));
    form = document.querySelector(".custom-form") as HTMLElement;
    expect(within(form).getByDisplayValue("Дар майстра")).toBeInTheDocument();
    await user.type(within(form).getByPlaceholderText("дар майстра, предмет…"), "Перстень");
    await user.selectOptions(within(form).getByRole("combobox", { name: "Відновлюється" }), "short");
    await user.click(within(form).getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(sent("PATCH", "")).toHaveLength(1));
    const patch = requests.find((item) => item.method === "PATCH")!;
    expect(patch.url).toMatch(/\/custom-features\/[0-9a-f]+$/);
    expect(patch.body).toMatchObject({ fields: { origin: "Перстень", recharge: "short", uses: 1 } });
    await waitFor(() => expect(document.querySelector(".custom-form")).toBeNull());

    const edited = (await screen.findByText("Дар майстра", { selector: ".feature-name" })).closest(
      "details",
    ) as HTMLElement;
    expect(within(edited).getByText(/Перстень/)).toBeInTheDocument();
    await user.click(within(edited).getByRole("button", { name: "Прибрати" }));
    await waitFor(() => expect(requests.some((item) => item.method === "DELETE")).toBe(true));
    await waitFor(() => expect(screen.queryByText("Дар майстра", { selector: ".feature-name" })).toBeNull());
  });

  it("shows the server's refusal in the form", async () => {
    override("POST", `/api/v1/characters/${ids["cleric-5"]}/custom-features`, {
      status: 422,
      body: { detail: "власних умінь не може бути більше за 50" },
    });
    const { user } = await openSheet("cleric-5", "features");
    await user.click(await screen.findByRole("button", { name: "+ Додати власне вміння" }));
    const form = document.querySelector(".custom-form") as HTMLElement;
    await user.type(within(form).getByPlaceholderText("Наприклад, «Око ворона»"), "Ще одне");
    await user.click(within(form).getByRole("button", { name: "Зберегти" }));
    expect(await within(form).findByText("власних умінь не може бути більше за 50")).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "Скасувати" }));
    expect(document.querySelector(".custom-form")).toBeNull();
  });
});

describe("custom spells", () => {
  it("adds a spell outside any class and edits it", async () => {
    const url = `/api/v1/characters/${ids["cleric-5"]}/spells`;
    // Відповідь на додавання — лист із цим закляттям (записаний на сервері).
    const withSpell = lookup("PATCH", url)!;
    override("POST", `${url}$`, withSpell);
    const { user } = await openSheet("cleric-5", "spells");

    await user.click(await screen.findByRole("button", { name: "+ закляття" }));
    const form = document.querySelector(".spell-add") as HTMLElement;
    await user.click(within(form).getByRole("checkbox", { name: /власне закляття/ }));
    await user.selectOptions(within(form).getByRole("combobox", { name: "Чий" }), "other");
    expect(within(form).getByText(/місця в лімітах не займає/)).toBeInTheDocument();
    await user.type(within(form).getByPlaceholderText(/Благословення столу/), "Вогонь перстня");
    await user.type(within(form).getByPlaceholderText("1 дія"), "1 дія");
    await user.type(within(form).getByPlaceholderText("втілення, ілюзія…"), "втілення");
    await user.click(within(form).getByRole("checkbox", { name: "концентрація" }));
    await user.type(within(form).getByPlaceholderText(/ефект, урон/), "1d10 вогню.");
    await user.click(within(form).getByRole("button", { name: "Додати" }));

    await waitFor(() =>
      expect(sent("POST", "/spells")[0]).toEqual({
        class_key: "other",
        name_en: "Вогонь перстня",
        custom: true,
        prepared: true,
        level: 1,
        description: "1d10 вогню.",
        school: "втілення",
        casting_time: "1 дія",
        range: null,
        duration: null,
        components: null,
        concentration: true,
        ritual: false,
        version: expect.any(Number),
      }),
    );
    const name = await screen.findByText("Вогонь перстня", { selector: ".spell__name" });
    const summary = name.closest("summary") as HTMLElement;
    expect(within(summary).getByText("власне")).toBeInTheDocument();
    expect(within(summary).getByText("поза класом")).toBeInTheDocument();

    await user.click(within(summary).getByRole("button", { name: "Змінити «Вогонь перстня»" }));
    const edit = document.querySelector(".spell-edit") as HTMLElement;
    expect(within(edit).getByDisplayValue("Вогонь перстня")).toBeInTheDocument();
    await user.selectOptions(within(edit).getByRole("combobox", { name: "Рівень" }), "3");
    await user.click(within(edit).getByRole("button", { name: "Зберегти" }));
    await waitFor(() =>
      expect(sent("PATCH", "/spells")[0]).toMatchObject({
        name_en: "Вогонь перстня",
        class_key: "other",
        fields: { name_en: "Вогонь перстня", class_key: "other", level: 3 },
      }),
    );
    await waitFor(() => expect(document.querySelector(".spell-edit")).toBeNull());
  });

  it("keeps the edit form open when the name is empty", async () => {
    const url = `/api/v1/characters/${ids["cleric-5"]}/spells`;
    override("POST", `${url}$`, lookup("PATCH", url)!);
    override("PATCH", `${url}$`, { status: 422, body: { detail: "закляття «Інше» уже є в листі" } });
    const { user } = await openSheet("cleric-5", "spells");
    await user.click(await screen.findByRole("button", { name: "+ закляття" }));
    const form = document.querySelector(".spell-add") as HTMLElement;
    await user.click(within(form).getByRole("checkbox", { name: /власне закляття/ }));
    await user.type(within(form).getByPlaceholderText(/Благословення столу/), "Вогонь перстня");
    await user.click(within(form).getByRole("button", { name: "Додати" }));

    await user.click(await screen.findByRole("button", { name: "Змінити «Вогонь перстня»" }));
    const edit = document.querySelector(".spell-edit") as HTMLElement;
    const field = within(edit).getByDisplayValue("Вогонь перстня");
    await user.clear(field);
    await user.click(within(edit).getByRole("button", { name: "Зберегти" }));
    expect(await within(edit).findByText("Впишіть назву власного закляття")).toBeInTheDocument();
    await user.type(field, "Інше");
    await user.click(within(edit).getByRole("button", { name: "Зберегти" }));
    expect(await within(edit).findByText("закляття «Інше» уже є в листі")).toBeInTheDocument();
    await user.click(within(edit).getByRole("button", { name: "Скасувати" }));
    expect(document.querySelector(".spell-edit")).toBeNull();
  });

  it("lets a character without spellcasting add a custom spell", async () => {
    const { user } = await openSheet("fighter-1", "spells");
    await user.click(await screen.findByRole("button", { name: "+ Додати власне закляття" }));
    const form = document.querySelector(".spell-add") as HTMLElement;
    expect(within(form).queryByRole("checkbox", { name: /власне закляття/ })).toBeNull();
    await user.click(within(form).getByRole("button", { name: "Додати" }));
    expect(await within(form).findByText("Впишіть назву власного закляття")).toBeInTheDocument();
    await user.type(within(form).getByPlaceholderText(/Благословення столу/), "Шепіт амулета");
    await user.selectOptions(within(form).getByRole("combobox", { name: "Рівень" }), "0");
    await user.click(within(form).getByRole("checkbox", { name: "ритуал" }));
    await user.click(within(form).getByRole("button", { name: "Додати" }));
    await waitFor(() =>
      expect(sent("POST", "/spells")[0]).toMatchObject({
        class_key: "other",
        name_en: "Шепіт амулета",
        level: 0,
        custom: true,
        ritual: true,
      }),
    );
  });
});

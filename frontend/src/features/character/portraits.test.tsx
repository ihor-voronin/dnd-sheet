import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PortraitImage, initials } from "../../components/Portrait";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { body, ids } from "../../test/tape";
import type { SheetViewPayload } from "../wizard/types";

const sent = (method: string, suffix: string) =>
  requests.filter((item) => item.method === method && item.url.endsWith(suffix)).map((item) => item.body);

describe("portrait image", () => {
  it("shows the server drawing with its size and falls back to initials", () => {
    const portrait = { id: "elf-f-wizard-1", url: "/assets/avatars/v/elf-f-wizard-1.svg", label: "Портрет: ельф" };
    const { container } = render(<PortraitImage portrait={portrait} name="Аріель Світанкова" size={64} />);
    const image = screen.getByRole("img", { name: "Портрет: ельф" });
    expect(image).toHaveAttribute("width", "64");
    expect(image).toHaveAttribute("height", "64");
    expect(image).toHaveAttribute("loading", "lazy");
    fireEvent.error(image);
    expect(container.textContent).toBe("АС");
    expect(initials("  ")).toBe("?");
  });

  it("is decorative when alt is empty and eager in the sheet header", () => {
    const portrait = { id: "x", url: "/x.svg", label: "Портрет" };
    const { container } = render(<PortraitImage portrait={portrait} name="Б" size={96} alt="" eager />);
    const image = container.querySelector("img") as HTMLImageElement;
    expect(image).toHaveAttribute("alt", "");
    expect(image).toHaveAttribute("loading", "eager");
  });

  it("shows initials without a portrait", () => {
    const { container } = render(<PortraitImage name="Торін" size={52} />);
    expect(container.textContent).toBe("Т");
  });
});

describe("portrait on the sheet", () => {
  it("opens the picker, recommends, chooses and changes the gender", async () => {
    const sheet = body<{ sheet: SheetViewPayload }>("GET", `/api/v1/characters/${ids["fighter-1"]}`).sheet;
    let character = { ...sheet.character };
    const reply = (changes: Record<string, unknown>) => {
      character = { ...character, ...changes, version: character.version + 1 };
      return { status: 200, body: { sheet: { ...sheet, character }, version: character.version } };
    };
    override("PATCH", `/api/v1/characters/${ids["fighter-1"]}$`, (request) => {
      const patch = request as { avatar?: string | null; gender?: string | null };
      if ("gender" in patch) return reply({ gender: patch.gender });
      const id = patch.avatar ?? "human-m-fighter-1";
      return reply({
        avatar: patch.avatar,
        portrait: { id, url: `/assets/avatars/v/${id}.svg`, label: "Портрет: обраний", chosen: Boolean(patch.avatar) },
      });
    });

    const { user } = await renderApp(`#/character/${ids["fighter-1"]}`);
    const button = await screen.findByRole("button", { name: /Змінити портрет/ });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button.querySelector("img")).toHaveAttribute("src", sheet.character.portrait?.url);

    await user.click(button);
    const panel = await screen.findByRole("region", { name: /Портрет/ });
    const tiles = await within(panel).findAllByRole("button", { name: /^Портрет: людина/ });
    expect(tiles.length).toBeGreaterThanOrEqual(5);

    await user.click(tiles[2]);
    await waitFor(() => expect(sent("PATCH", ids["fighter-1"]).at(-1)).toMatchObject({ avatar: expect.any(String) }));
    expect(await within(panel).findByRole("button", { name: "Повернути типовий портрет" })).toBeInTheDocument();

    await user.click(within(panel).getByRole("radio", { name: "жіноча" }));
    await waitFor(() => expect(sent("PATCH", ids["fighter-1"]).at(-1)).toMatchObject({ gender: "female" }));

    await user.click(within(panel).getByRole("button", { name: "Повернути типовий портрет" }));
    await waitFor(() => expect(sent("PATCH", ids["fighter-1"]).at(-1)).toMatchObject({ avatar: null }));

    await user.click(within(panel).getByRole("button", { name: "закрити" }));
    expect(screen.queryByRole("region", { name: /Портрет/ })).not.toBeInTheDocument();
  });

  it("lists all portraits with filters and pages", async () => {
    const catalog = {
      version: "v",
      base: "/assets/avatars/v/",
      groups: [
        { key: "elf", label: "ельф" },
        { key: "kenku", label: "кенку" },
      ],
      classes: [
        { key: "wizard", label: "чарівник" },
        { key: "rogue", label: "пройдисвіт" },
      ],
      items: [
        ...Array.from({ length: 60 }, (_, n) => [`elf-f-wizard-${n}`, "elf", "f", "wizard"]),
        ["kenku-x-rogue-1", "kenku", "x", "rogue"],
        ["elf-m-rogue-2", "elf", "m", "rogue"],
      ],
      total: 62,
    };
    override("GET", "/api/v1/avatars$", { status: 200, body: catalog });

    const { user } = await renderApp(`#/character/${ids["fighter-1"]}`);
    await user.click(await screen.findByRole("button", { name: /Змінити портрет/ }));
    const panel = await screen.findByRole("region", { name: /Портрет/ });
    await user.click(within(panel).getByRole("button", { name: "Усі портрети" }));
    expect(await within(panel).findByText(/знайдено 62/)).toBeInTheDocument();
    expect(within(panel).getAllByRole("button", { name: /Портрет: ельф, жіночий, чарівник/ })).toHaveLength(48);

    await user.click(within(panel).getByRole("button", { name: "Показати ще 14" }));
    expect(within(panel).getByRole("button", { name: "Портрет: кенку, пройдисвіт" })).toBeInTheDocument();

    await user.selectOptions(within(panel).getByRole("combobox", { name: "Клас" }), "rogue");
    expect(within(panel).getByText(/знайдено 2/)).toBeInTheDocument();
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Стать" }), "m");
    expect(within(panel).getByRole("button", { name: "Портрет: ельф, чоловічий, пройдисвіт (2)" })).toBeInTheDocument();
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Вид" }), "kenku");
    expect(within(panel).getByText(/знайдено 0/)).toBeInTheDocument();
  });

  it("shows the portrait on the roster card without making it a second label", async () => {
    await renderApp("#/");
    await screen.findByRole("heading", { name: "Мої персонажі" });
    await waitFor(() => expect(document.querySelector(".roster-card__portrait img")).not.toBeNull());
    expect(document.querySelector(".roster-card__portrait img")).toHaveAttribute("alt", "");
  });
});

import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { ids } from "../../test/tape";

const PLAYER = { status: 200, body: { user: { id: "u1", name: "Ігор", username: null, photo_url: null } } };
const GUEST = { status: 200, body: { user: null } };

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AI assistant (MCP) page", () => {
  it("is linked from the home page and shows this site's server address", async () => {
    override("GET", "/api/v1/auth/me", GUEST);
    const { user } = await renderApp("#/");
    expect(await screen.findByRole("heading", { name: "Персонажі в ІІ-асистенті" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Як підключити" }));
    expect(await screen.findByRole("heading", { name: "Claude Code" })).toBeInTheDocument();
    expect(screen.getByText(`${window.location.origin}/mcp`)).toBeInTheDocument();
    expect(screen.getByText(/Застосунок не створює акаунтів сам/)).toBeInTheDocument();
    expect(screen.getByText("ІІ-асистент", { exact: false, selector: "a.badge" })).toBeInTheDocument();
  });

  it("copies the server address and the Claude Code command", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    const { user } = await renderApp("#/mcp");
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    await user.click(await screen.findByRole("button", { name: "Копіювати адресу сервера" }));
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/mcp`);
    expect(await screen.findByText("Скопійовано")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Копіювати команду" }));
    expect(writeText).toHaveBeenLastCalledWith(
      `claude mcp add --transport http dnd-sheet ${window.location.origin}/mcp`,
    );
    expect(screen.getByText(/Ви вже увійшли/)).toBeInTheDocument();
  });
});

describe("deleting a character", () => {
  it("asks, deletes and goes back to the list", async () => {
    const id = ids["fighter-1"];
    override("DELETE", `/api/v1/characters/${id}$`, { status: 200, body: { deleted: id } });
    const { user } = await renderApp(`#/character/${id}`);
    await user.click(await screen.findByRole("button", { name: "Видалити персонажа…" }));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("назавжди"));
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(requests.some((item) => item.method === "DELETE" && item.url === `/api/v1/characters/${id}`)).toBe(true);
  });

  it("keeps the sheet when the player changes their mind or the server refuses", async () => {
    const id = ids["fighter-1"];
    override("DELETE", `/api/v1/characters/${id}$`, { status: 404, body: { detail: "немає персонажа" } });
    const { user } = await renderApp(`#/character/${id}`);
    vi.mocked(window.confirm).mockReturnValueOnce(false);
    await user.click(await screen.findByRole("button", { name: "Видалити персонажа…" }));
    expect(requests.some((item) => item.method === "DELETE")).toBe(false);

    await user.click(screen.getByRole("button", { name: "Видалити персонажа…" }));
    expect(await screen.findByText(/немає персонажа/)).toBeInTheDocument();
    expect(window.location.hash).toBe(`#/character/${id}`);
  });

  it("shows the count near the limit and blocks creating at it", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/characters$", { status: 200, body: { items: [], total: 50, limit: 50, draft_id: "d1" } });
    await renderApp("#/");
    expect(await screen.findByText(/Це межа: 50 персонажів/)).toBeInTheDocument();
    // Незавершену чернетку не пропонуємо «продовжити»: на фініші її однаково не приймуть.
    expect(screen.getByText(/коли звільниться місце/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Продовжити" })).not.toBeInTheDocument();
    expect(screen.getByText(/50 з 50/)).toBeInTheDocument();
    const create = screen
      .getAllByRole("button", { name: "Створити персонажа" })
      .find((button) => button.closest("#my-characters"))!;
    expect(create).toBeDisabled();
  });

  it("hides the count far from the limit", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/characters$", { status: 200, body: { items: [], total: 3, limit: 50, draft_id: null } });
    await renderApp("#/");
    expect(await screen.findByRole("heading", { name: "Мої персонажі" })).toBeInTheDocument();
    expect(screen.queryByText(/з 50/)).not.toBeInTheDocument();
  });

  it("explains the limit in the wizard instead of blaming the server", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("POST", "/api/v1/characters/wizard$", {
      status: 409,
      body: { detail: "у вас уже 50 персонажів — це межа" },
    });
    await renderApp("#/create");
    expect(await screen.findByRole("heading", { name: "Досягнуто межі персонажів" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("У вас уже 50 персонажів");
    expect(screen.queryByText(/запущено сервер/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "До моїх персонажів" })).toHaveAttribute("href", "#/");
  });
});

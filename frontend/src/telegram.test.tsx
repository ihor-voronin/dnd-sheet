import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderApp } from "./test/render";
import { override, requests } from "./test/setup";

type Fake = ReturnType<typeof fakeWebApp>;

function fakeWebApp(startParam?: string, version = "8.0") {
  const back = { show: vi.fn(), hide: vi.fn(), onClick: vi.fn(), offClick: vi.fn() };
  return {
    initData: "query_id=1&hash=abc",
    initDataUnsafe: { start_param: startParam },
    version,
    colorScheme: "light" as const,
    ready: vi.fn(),
    expand: vi.fn(),
    disableVerticalSwipes: vi.fn(),
    isVersionAtLeast: (wanted: string) => Number(version) >= Number(wanted),
    setHeaderColor: vi.fn(),
    setBackgroundColor: vi.fn(),
    setBottomBarColor: vi.fn(),
    onEvent: vi.fn(),
    BackButton: back,
    openLink: vi.fn(),
    openTelegramLink: vi.fn(),
    downloadFile: vi.fn(),
  };
}

async function load(app: Fake | null) {
  window.Telegram = app ? { WebApp: app as never } : undefined;
  vi.resetModules();
  return import("./telegram");
}

beforeEach(() => {
  document.documentElement.style.setProperty("--paper", "#11141b");
});

afterEach(() => {
  delete window.Telegram;
  document.documentElement.classList.remove("in-telegram");
});

describe("outside Telegram", () => {
  it("does nothing", async () => {
    const tg = await load(null);
    expect(tg.inTelegram).toBe(false);
    expect(tg.initialHash()).toBeNull();
    expect(tg.telegramTheme()).toBeNull();
    tg.startTelegramShell();
    tg.paintTelegramChrome();
    tg.onTelegramThemeChange(() => undefined);
    tg.telegramBackButton(true, () => undefined)();
    tg.openTelegramFile("/a.pdf", "a.pdf");
    tg.shareToTelegram("https://x", "hi");
    expect(tg.telegramShareLink("bot", "tok")).toBe("https://t.me/bot?startapp=s_tok");
  });
});

describe("inside Telegram", () => {
  it("opens a shared sheet from the start parameter", async () => {
    const tg = await load(fakeWebApp("s_abc"));
    expect(tg.inTelegram).toBe(true);
    expect(tg.initialHash()).toBe("#/s/abc");
  });

  it("replaces Telegram's own hash with the home route", async () => {
    window.location.hash = "#tgWebAppData=1";
    const tg = await load(fakeWebApp());
    expect(tg.initialHash()).toBe("#/");
    window.location.hash = "#/kb";
    expect(tg.initialHash()).toBeNull();
  });

  it("sets up the shell, the theme and external links", async () => {
    const app = fakeWebApp();
    const tg = await load(app);
    tg.startTelegramShell();
    expect(app.ready).toHaveBeenCalled();
    expect(app.disableVerticalSwipes).toHaveBeenCalled();
    expect(document.documentElement).toHaveClass("in-telegram");
    expect(tg.telegramTheme()).toBe("day");

    const outside = document.createElement("a");
    outside.href = "https://www.dndbeyond.com/";
    document.body.appendChild(outside);
    outside.click();
    expect(app.openLink).toHaveBeenCalledWith("https://www.dndbeyond.com/");
    const inside = document.createElement("a");
    inside.href = "#/kb";
    document.body.appendChild(inside);
    inside.click();
    expect(app.openLink).toHaveBeenCalledTimes(1);

    tg.paintTelegramChrome();
    expect(app.setHeaderColor).toHaveBeenCalledWith("#11141b");
    expect(app.setBottomBarColor).toHaveBeenCalled();
    const handler = vi.fn();
    tg.onTelegramThemeChange(handler);
    expect(app.onEvent).toHaveBeenCalledWith("themeChanged", handler);
  });

  it("shows and hides the back button", async () => {
    const app = fakeWebApp();
    const tg = await load(app);
    const back = vi.fn();
    const release = tg.telegramBackButton(true, back);
    expect(app.BackButton.show).toHaveBeenCalled();
    release();
    expect(app.BackButton.offClick).toHaveBeenCalledWith(back);
    tg.telegramBackButton(false, back)();
    expect(app.BackButton.hide).toHaveBeenCalledTimes(2);
  });

  it("downloads files through Telegram, or opens them on old versions", async () => {
    const app = fakeWebApp();
    const tg = await load(app);
    tg.openTelegramFile("/api/v1/x.pdf", "x.pdf");
    expect(app.downloadFile).toHaveBeenCalled();
    tg.openTelegramFile("/print");
    expect(app.openLink).toHaveBeenCalled();
    tg.shareToTelegram("https://dnd.example/#/s/t", "Лист");
    expect(app.openTelegramLink).toHaveBeenCalledWith(expect.stringContaining("t.me/share/url"));

    const old = await load(fakeWebApp(undefined, "6.0"));
    old.paintTelegramChrome();
    expect(old.telegramBackButton(true, () => undefined)).toBeTypeOf("function");
  });

  it("signs in with initData before showing the app", async () => {
    window.Telegram = { WebApp: fakeWebApp() as never };
    override("POST", "/api/v1/auth/telegram-webapp", {
      status: 200,
      body: { user: { id: "1", name: "Т" }, token: "t" },
    });
    await renderApp("#/");
    await waitFor(() => expect(requests.some((item) => item.url === "/api/v1/auth/telegram-webapp")).toBe(true));
    await waitFor(() => expect(screen.queryByText("Входимо через Telegram…")).not.toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the compendium open when Telegram sign-in fails", async () => {
    window.Telegram = { WebApp: fakeWebApp() as never };
    override("POST", "/api/v1/auth/telegram-webapp", { status: 401, body: { detail: "підпис не збігся" } });
    await renderApp("#/kb");
    expect(await screen.findByRole("alert")).toHaveTextContent("підпис не збігся");
  });
});

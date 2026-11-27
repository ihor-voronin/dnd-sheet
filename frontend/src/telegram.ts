/**
 * Mini App у Telegram: той самий сайт, відкритий усередині Telegram.
 *
 * Скрипт Telegram (`telegram-web-app.js`) вантажиться лише тоді, коли сторінку
 * справді відкрив Telegram (див. index.html), тож на звичайному сайті
 * `window.Telegram` немає і все тут — no-op.
 *
 * Що змінюється всередині Telegram:
 * - вхід без кнопки: Telegram сам передає підписаний `initData`, сервер його
 *   перевіряє й видає токен сесії — він їде заголовком (у Telegram у браузері
 *   сайт живе в iframe, де cookie не доходять);
 * - тема — світла чи темна, як у самого Telegram; шапка й тло — наших кольорів;
 * - кнопка «Назад» Telegram замість навігації браузера;
 * - файли (PDF, друк) і зовнішні посилання відкриває Telegram, а не webview.
 */

interface TelegramBackButton {
  show(): void;
  hide(): void;
  onClick(handler: () => void): void;
  offClick(handler: () => void): void;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { start_param?: string };
  version: string;
  colorScheme: "light" | "dark";
  ready(): void;
  expand(): void;
  disableVerticalSwipes?: () => void;
  isVersionAtLeast(version: string): boolean;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;
  setBottomBarColor?: (color: string) => void;
  onEvent(event: string, handler: () => void): void;
  BackButton: TelegramBackButton;
  openLink(url: string, options?: { try_instant_view?: boolean }): void;
  openTelegramLink(url: string): void;
  downloadFile?: (params: { url: string; file_name: string }, callback?: (accepted: boolean) => void) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

/** Telegram WebApp, якщо сторінку відкрив Telegram з даними користувача; інакше `null`. */
export const telegram: TelegramWebApp | null =
  typeof window !== "undefined" && window.Telegram?.WebApp?.initData ? window.Telegram.WebApp : null;

export const inTelegram = telegram !== null;

/**
 * Куди вести після запуску: `startapp=s_<токен>` — лист «лише читати».
 * Telegram кладе свої параметри в hash (`#tgWebAppData=…`) — наш роутер їх не
 * розуміє, тож hash замінюємо на справжній маршрут.
 */
export function initialHash(): string | null {
  if (!telegram) return null;
  const start = telegram.initDataUnsafe.start_param ?? "";
  if (start.startsWith("s_") && start.length > 2) return `#/s/${start.slice(2)}`;
  if (window.location.hash.includes("tgWebApp")) return "#/";
  return null;
}

/** Готовність, повна висота, свайп вниз не закриває застосунок посеред довгого листа. */
export function startTelegramShell(): void {
  if (!telegram) return;
  telegram.ready();
  telegram.expand();
  if (telegram.isVersionAtLeast("7.7")) telegram.disableVerticalSwipes?.();
  document.documentElement.classList.add("in-telegram");
  // Зовнішні посилання (книги на D&D Beyond тощо): webview Telegram не відкриває
  // `target="_blank"` — віддаємо їх Telegram, він відкриє браузер.
  document.addEventListener("click", (event) => {
    const link = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
    if (!link || link.dataset.telegramFile !== undefined) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) {
      event.preventDefault();
      telegram.openLink(url.href);
    }
  });
}

/** Тема Telegram: світла чи темна. */
export function telegramTheme(): "day" | "night" | null {
  if (!telegram) return null;
  return telegram.colorScheme === "light" ? "day" : "night";
}

export function onTelegramThemeChange(handler: () => void): void {
  telegram?.onEvent("themeChanged", handler);
}

/** Шапка й тло Telegram — кольору нашого «паперу», щоб не було смуги іншого тону. */
export function paintTelegramChrome(): void {
  if (!telegram || !telegram.isVersionAtLeast("6.1")) return;
  const paper = getComputedStyle(document.documentElement).getPropertyValue("--paper").trim();
  if (!/^#[0-9a-f]{6}$/i.test(paper)) return;
  telegram.setHeaderColor(paper);
  telegram.setBackgroundColor(paper);
  if (telegram.isVersionAtLeast("7.10")) telegram.setBottomBarColor?.(paper);
}

/** Кнопка «Назад» Telegram: видно всюди, крім головної. */
export function telegramBackButton(visible: boolean, onBack: () => void): () => void {
  if (!telegram || !telegram.isVersionAtLeast("6.1")) return () => undefined;
  const button = telegram.BackButton;
  if (!visible) {
    button.hide();
    return () => undefined;
  }
  button.onClick(onBack);
  button.show();
  return () => {
    button.offClick(onBack);
    button.hide();
  };
}

/**
 * Відкрити файл з Telegram: PDF — завантаженням Telegram (Bot API 8.0+), друк і
 * старі версії — у браузері телефона. `url` має бути доступний без сесії
 * (посилання «лише читати» або з коротким токеном `?link=`).
 */
export function openTelegramFile(url: string, fileName?: string): void {
  if (!telegram) return;
  const absolute = new URL(url, window.location.origin).href;
  if (fileName && telegram.isVersionAtLeast("8.0") && telegram.downloadFile) {
    telegram.downloadFile({ url: absolute, file_name: fileName });
    return;
  }
  telegram.openLink(absolute);
}

/** Поділитися посиланням через вибір чату в Telegram. */
export function shareToTelegram(url: string, text: string): void {
  if (!telegram) return;
  const share = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  telegram.openTelegramLink(share);
}

/** Посилання, що відкриває лист «лише читати» одразу в Mini App. */
export function telegramShareLink(bot: string, shareToken: string): string {
  return `https://t.me/${bot}?startapp=s_${shareToken}`;
}

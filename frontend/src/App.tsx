import { TooltipProvider } from "@radix-ui/react-tooltip";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import {
  fetchAuthConfig,
  fetchCharacter,
  fetchCharacters,
  fetchMe,
  fetchShared,
  loginTelegramWebApp,
  logout,
} from "./api";
import { LoginPanel } from "./features/auth/Login";
import { BugReport } from "./features/bugs/BugReport";
import { CharacterView } from "./features/character/CharacterView";
import { LevelUpWizard } from "./features/character/LevelUp";
import { CharacterCard } from "./features/home/CharacterCard";
import { Home } from "./features/home/Home";
import { KnowledgeBase, isKbSection } from "./features/knowledge/KnowledgeBase";
import type { KbSection } from "./features/knowledge/KnowledgeBase";
import { CreateWizard } from "./features/wizard/CreateWizard";
import {
  inTelegram,
  initialHash,
  onTelegramThemeChange,
  paintTelegramChrome,
  startTelegramShell,
  telegram,
  telegramBackButton,
  telegramTheme,
} from "./telegram";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000, retry: 1 } },
});

type Route =
  | { name: "home" }
  | { name: "create" }
  | { name: "character"; id: string; tab?: string }
  | { name: "levelup"; id: string }
  | { name: "shared"; token: string }
  | { name: "kb"; section?: KbSection; key?: string }
  | { name: "bugs" };

function parseRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash === "create") return { name: "create" };
  // Посилання «лише читати»: #/s/<токен> — відкривається без входу.
  if (hash.startsWith("s/")) return { name: "shared", token: decodeURIComponent(hash.slice(2)) };
  if (hash === "bugs") return { name: "bugs" };
  if (hash === "kb" || hash.startsWith("kb/")) {
    const [, section, ...rest] = hash.split("/");
    const key = rest.length ? decodeURIComponent(rest.join("/")) : undefined;
    return { name: "kb", section: isKbSection(section) ? section : undefined, key };
  }
  if (hash.startsWith("character/")) {
    const rest = hash.slice("character/".length);
    if (rest.endsWith("/level-up")) {
      return { name: "levelup", id: decodeURIComponent(rest.slice(0, -"/level-up".length)) };
    }
    // Вкладку листа можна відкрити напряму: після підвищення рівня екран
    // веде одразу до «Заклять», де й обирають нові.
    const [id, query] = rest.split("?");
    const tab = new URLSearchParams(query ?? "").get("tab") ?? undefined;
    return { name: "character", id: decodeURIComponent(id), tab };
  }
  return { name: "home" };
}

function useRoute(): [Route, (next: Route) => void] {
  const [route, setRoute] = useState<Route>(parseRoute);
  useEffect(() => {
    const onChange = () => setRoute(parseRoute());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  // Нова сторінка відкривається згори, а не на висоті, де гравець був на
  // попередній (наприклад, після «Створити персонажа» внизу візарда).
  const page = route.name + ("id" in route ? `:${route.id}` : "") + ("token" in route ? `:${route.token}` : "");
  const shownPage = useRef(page);
  useEffect(() => {
    if (shownPage.current === page) return;
    shownPage.current = page;
    window.scrollTo(0, 0);
  }, [page]);
  const navigate = useCallback((next: Route) => {
    const target =
      next.name === "home"
        ? "#/"
        : next.name === "bugs"
          ? "#/bugs"
          : next.name === "create"
            ? "#/create"
            : next.name === "kb"
              ? `#/kb${next.section ? `/${next.section}` : ""}${next.key ? `/${encodeURIComponent(next.key)}` : ""}`
              : next.name === "levelup"
                ? `#/character/${encodeURIComponent(next.id)}/level-up`
                : next.name === "shared"
                  ? `#/s/${encodeURIComponent(next.token)}`
                  : `#/character/${encodeURIComponent(next.id)}${next.tab ? `?tab=${next.tab}` : ""}`;
    if (window.location.hash === target) setRoute(next);
    else window.location.hash = target;
  }, []);
  return [route, navigate];
}

/** Прокрутити до елемента, щойно сторінка його намалює (після переходу між сторінками). */
function scrollToWhenReady(id: string, attempt = 0) {
  window.setTimeout(() => {
    const target = document.getElementById(id);
    if (target) target.scrollIntoView({ block: "start" });
    else if (attempt < 20) scrollToWhenReady(id, attempt + 1);
  }, 60);
}

function CharactersList({ navigate }: { navigate: (next: Route) => void }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["characters"],
    queryFn: fetchCharacters,
  });

  return (
    <section className="saved" id="my-characters">
      <div className="saved-head">
        <h2>Мої персонажі</h2>
        <button type="button" className="button button--primary" onClick={() => navigate({ name: "create" })}>
          Створити персонажа
        </button>
      </div>
      {isPending ? <p className="status">Читаємо збережених…</p> : null}
      {error ? (
        <p className="status status--error">
          Не вдалося прочитати список: {error instanceof Error ? error.message : String(error)}
        </p>
      ) : null}
      {data?.draft_id ? (
        <p className="hint">
          Є незавершене створення персонажа.{" "}
          <button
            type="button"
            className="link-button"
            onClick={() => {
              // Чернетка в базі: продовжити можна з будь-якого пристрою.
              try {
                window.localStorage.setItem("dndsheet.draft", data.draft_id!);
              } catch {
                // приватний режим — візард почне нову чернетку
              }
              navigate({ name: "create" });
            }}
          >
            Продовжити
          </button>
        </p>
      ) : null}
      {data && data.total === 0 ? (
        <p className="hint">
          Поки що нікого немає. Візард збере чернетку на кожному кроці — навіть якщо закрити вкладку.
        </p>
      ) : null}
      {data && data.total > 0 ? (
        <ul className="roster">
          {data.items.map((item) => (
            <li key={item.id}>
              <CharacterCard entry={item} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function CharacterPage({ id, tab, navigate }: { id: string; tab?: string; navigate: (next: Route) => void }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["character", id],
    queryFn: () => fetchCharacter(id),
  });

  if (isPending) return <p className="status">Читаємо персонажа…</p>;
  if (error) {
    return (
      <p className="status status--error">
        Не вдалося прочитати персонажа: {error instanceof Error ? error.message : String(error)}
      </p>
    );
  }
  return (
    <>
      <p className="crumbs">
        <button type="button" className="link-button" onClick={() => navigate({ name: "home" })}>
          ← до списку
        </button>
      </p>
      {/* key: інший персонаж — новий лист, а не стан попереднього (версії різних листів не порівнюються). */}
      <CharacterView key={id} initial={data.sheet} initialTab={tab} />
    </>
  );
}

/** Лист за посиланням: той самий вигляд, але без жодних змін; друк і PDF — за посиланням. */
function SharedPage({ token }: { token: string }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["shared", token],
    queryFn: () => fetchShared(token),
    retry: false,
  });
  if (isPending) return <p className="status">Відкриваємо лист…</p>;
  if (error || !data) {
    return (
      <p className="status status--error">Посилання недійсне або власник його вимкнув. Попросіть нове посилання.</p>
    );
  }
  return <CharacterView key={token} initial={data.sheet} shareToken={token} />;
}

function LevelUpPage({ id, navigate }: { id: string; navigate: (next: Route) => void }) {
  const queryClient = useQueryClient();

  return (
    <>
      <p className="crumbs">
        <button type="button" className="link-button" onClick={() => navigate({ name: "character", id })}>
          ← до листа
        </button>
      </p>
      <LevelUpWizard
        characterId={id}
        onCancel={() => navigate({ name: "character", id })}
        onOpenSpells={() => navigate({ name: "character", id, tab: "spells" })}
        onDone={() => {
          // Лист уже змінився на сервері: стара відповідь у кеші недійсна.
          void queryClient.invalidateQueries({ queryKey: ["character", id] });
          void queryClient.invalidateQueries({ queryKey: ["level-up", id] });
          void queryClient.invalidateQueries({ queryKey: ["characters"] });
          window.location.hash = `#/character/${encodeURIComponent(id)}`;
        }}
      />
    </>
  );
}

const THEME_KEY = "dndsheet.theme";

/** Темна тема — типова; світлу гравець вмикає сам, вибір памʼятає браузер.
 *  У Telegram тема — як у самого Telegram (і змінюється разом із ним). */
function useTheme(): ["night" | "day", () => void] {
  const [theme, setTheme] = useState<"night" | "day">(() => {
    const fromTelegram = telegramTheme();
    if (fromTelegram) return fromTelegram;
    try {
      return window.localStorage.getItem(THEME_KEY) === "day" ? "day" : "night";
    } catch {
      return "night";
    }
  });
  useEffect(() => {
    onTelegramThemeChange(() => setTheme(telegramTheme() ?? "night"));
  }, []);
  useEffect(() => {
    if (theme === "day") document.documentElement.dataset.theme = "day";
    else delete document.documentElement.dataset.theme;
    paintTelegramChrome();
    if (inTelegram) return;
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      // приватний режим — тема просто не запамʼятається
    }
  }, [theme]);
  return [theme, () => setTheme((current) => (current === "day" ? "night" : "day"))];
}

/** Хто зайшов: `undefined` — ще питаємо, `null` — гість. */
function useCurrentUser() {
  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: 60_000 });
  return me.isPending ? undefined : (me.data?.user ?? null);
}

function UserBar({ navigate }: { navigate: (next: Route) => void }) {
  const queryClient = useQueryClient();
  const user = useCurrentUser();
  const config = useQuery({ queryKey: ["auth-config"], queryFn: fetchAuthConfig, staleTime: Infinity });
  if (user === undefined) return null;
  if (!user) {
    return (
      <button type="button" className="link-button" onClick={() => navigate({ name: "home" })}>
        Увійти
      </button>
    );
  }
  return (
    <span className="userbar">
      <span className="meta">{user.name}</span>
      {config.data?.auth_enabled && !inTelegram ? (
        <button
          type="button"
          className="link-button"
          onClick={() => {
            void logout().finally(() => {
              try {
                window.localStorage.removeItem("dndsheet.draft");
              } catch {
                // нічого
              }
              queryClient.clear();
              navigate({ name: "home" });
            });
          }}
        >
          Вийти
        </button>
      ) : null}
    </span>
  );
}

function Shell() {
  const [route, navigate] = useRoute();
  const [theme, toggleTheme] = useTheme();
  const user = useCurrentUser();
  const needsUser = route.name === "create" || route.name === "character" || route.name === "levelup";

  // Telegram: його кнопка «Назад» — усюди, крім головної.
  useEffect(
    () =>
      telegramBackButton(route.name !== "home", () => {
        if (window.history.length > 1) window.history.back();
        else navigate({ name: "home" });
      }),
    [route.name, navigate],
  );

  // Лист персонажа має темну «дошку» на всю ширину; решта застосунку світла.
  // Клас ставимо і на <html>, інакше за межами body видно світлий canvas.
  useEffect(() => {
    const board = route.name === "character" || route.name === "shared";
    document.body.classList.toggle("board", board);
    document.documentElement.classList.toggle("board", board);
    // Нічна сесія = ті самі токени theme.css, лише інші значення.
    return () => {
      document.body.classList.remove("board");
      document.documentElement.classList.remove("board");
    };
  }, [route.name]);

  return (
    <main className={route.name === "character" || route.name === "shared" ? "app app--board" : "app"}>
      <div className="topbar">
        <a className="badge badge--home" href="#/" title="На головну">
          Книга гравця 2014 ·{" "}
          {route.name === "create"
            ? "створення персонажа"
            : route.name === "levelup"
              ? "підвищення рівня"
              : route.name === "kb"
                ? "довідник"
                : route.name === "shared"
                  ? "лист персонажа · перегляд"
                  : route.name === "home"
                    ? "головна"
                    : route.name === "bugs"
                      ? "знайшли помилку"
                      : "лист персонажа"}
        </a>
        <nav className="topnav" aria-label="Розділи">
          <button
            type="button"
            className="link-button"
            aria-current={route.name === "home" ? "page" : undefined}
            onClick={() => {
              navigate({ name: "home" });
              // «Мої персонажі» — це список, а не верх головної: на телефоні він
              // під обкладинкою й прикладами листа, тож ведемо одразу до нього.
              if (user) scrollToWhenReady("my-characters");
            }}
          >
            {user ? "Мої персонажі" : "Головна"}
          </button>
          <button
            type="button"
            className="link-button"
            aria-current={route.name === "kb" ? "page" : undefined}
            onClick={() => navigate({ name: "kb" })}
          >
            Довідник
          </button>
          <UserBar navigate={navigate} />
          {inTelegram ? null : (
            <button type="button" className="link-button theme-toggle" onClick={toggleTheme}>
              {theme === "day" ? "Темна тема" : "Світла тема"}
            </button>
          )}
        </nav>
      </div>
      {route.name === "kb" ? (
        <KnowledgeBase
          section={route.section}
          entryKey={route.key}
          go={(section, key) => navigate({ name: "kb", section, key })}
        />
      ) : null}
      {user === undefined && route.name !== "kb" ? <p className="status">Перевіряємо вхід…</p> : null}
      {user === null && needsUser ? (
        <LoginPanel
          reason={
            needsUser
              ? "Створювати й відкривати персонажів можна після входу через Telegram. Довідник доступний і без входу."
              : undefined
          }
        />
      ) : null}
      {route.name === "home" ? (
        <Home
          onOpenKb={(section) => navigate({ name: "kb", section: isKbSection(section) ? section : undefined })}
          account={
            user === undefined ? null : user ? (
              <CharactersList navigate={navigate} />
            ) : (
              <div id="login">
                <LoginPanel />
              </div>
            )
          }
          actions={
            <>
              {user ? (
                <button type="button" className="button button--primary" onClick={() => navigate({ name: "create" })}>
                  Створити персонажа
                </button>
              ) : (
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() =>
                    document.getElementById("login")?.scrollIntoView({ behavior: "smooth", block: "start" })
                  }
                >
                  Увійти й створити персонажа
                </button>
              )}
              <button type="button" className="button" onClick={() => navigate({ name: "kb" })}>
                Відкрити довідник
              </button>
            </>
          }
        />
      ) : null}
      {user && route.name === "create" ? (
        <CreateWizard onFinished={(characterId) => navigate({ name: "character", id: characterId })} />
      ) : null}
      {user && route.name === "character" ? <CharacterPage id={route.id} tab={route.tab} navigate={navigate} /> : null}
      {user && route.name === "levelup" ? <LevelUpPage id={route.id} navigate={navigate} /> : null}
      {route.name === "shared" ? <SharedPage token={route.token} /> : null}
      {route.name === "bugs" ? <BugReport /> : null}
      <footer className="site-footer">
        <a href="#/bugs" className="site-footer__bug">
          Знайшли помилку?
        </a>
        <span className="site-footer__note">
          {" "}
          · неофіційний некомерційний фанатський проєкт ·{" "}
          <a href="https://github.com/ihor-voronin/dnd-sheet" target="_blank" rel="noopener noreferrer">
            код на GitHub
          </a>
        </span>
      </footer>
    </main>
  );
}

/**
 * Mini App: до показу застосунку — вхід за `initData` від Telegram (гравцю не
 * треба нічого натискати). Невдалий вхід не ховає довідник: застосунок
 * відкривається як для гостя, з поясненням угорі.
 */
function TelegramGate({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const started = useRef(false);
  const [state, setState] = useState<"pending" | "ready" | { error: string }>(inTelegram ? "pending" : "ready");

  useEffect(() => {
    if (!telegram || started.current) return;
    started.current = true;
    startTelegramShell();
    const hash = initialHash();
    if (hash) window.history.replaceState(null, "", hash);
    loginTelegramWebApp(telegram.initData)
      .then(() => {
        void client.invalidateQueries({ queryKey: ["me"] });
        setState("ready");
      })
      .catch((failure: unknown) => setState({ error: failure instanceof Error ? failure.message : String(failure) }));
  }, [client]);

  if (state === "pending") return <p className="status telegram-status">Входимо через Telegram…</p>;
  return (
    <>
      {typeof state === "object" ? (
        <p className="status status--error telegram-status" role="alert">
          Не вдалося увійти через Telegram: {state.error}. Довідник доступний і так.
        </p>
      ) : null}
      {children}
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <TelegramGate>
          <Shell />
        </TelegramGate>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

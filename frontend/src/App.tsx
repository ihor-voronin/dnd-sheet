import { useCallback, useEffect, useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { TooltipProvider } from "@radix-ui/react-tooltip";

import {
  demoExportUrl,
  fetchCharacter,
  fetchCharacters,
  fetchDemoSheet,
  fetchRenderers,
} from "./api";
import { CharacterView } from "./features/character/CharacterView";
import { LevelUpWizard } from "./features/character/LevelUp";
import { CreateWizard } from "./features/wizard/CreateWizard";
import { SheetView } from "./features/sheet/SheetView";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000, retry: 1 } },
});

type Route =
  | { name: "home" }
  | { name: "create" }
  | { name: "character"; id: string; tab?: string }
  | { name: "levelup"; id: string };

function parseRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash === "create") return { name: "create" };
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
  const navigate = useCallback((next: Route) => {
    const target =
      next.name === "home"
        ? "#/"
        : next.name === "create"
          ? "#/create"
          : next.name === "levelup"
            ? `#/character/${encodeURIComponent(next.id)}/level-up`
            : `#/character/${encodeURIComponent(next.id)}${next.tab ? `?tab=${next.tab}` : ""}`;
    if (window.location.hash === target) setRoute(next);
    else window.location.hash = target;
  }, []);
  return [route, navigate];
}

function DemoSheet() {
  const { data, isPending, error } = useQuery({
    queryKey: ["demo-sheet"],
    queryFn: fetchDemoSheet,
  });
  const renderers = useQuery({ queryKey: ["renderers"], queryFn: fetchRenderers });
  const pdfReady = renderers.data?.available.includes("pdf") ?? false;

  if (isPending) return <p className="status">Завантаження документа…</p>;
  if (error) {
    return (
      <p className="status status--error">
        Не вдалося отримати документ: {error instanceof Error ? error.message : String(error)}
      </p>
    );
  }
  return (
    <>
      <div className="export-bar">
        <a className="button" href={demoExportUrl("markdown")} download>
          Markdown
        </a>
        {pdfReady ? (
          <a className="button" href={demoExportUrl("pdf")} download>
            PDF (A4)
          </a>
        ) : (
          <span className="meta" title="На сервері немає WeasyPrint (extra `pdf` + GTK)">
            PDF недоступний на цьому сервері
          </span>
        )}
      </div>
      <SheetView document={data} />
    </>
  );
}

function CharactersList({ navigate }: { navigate: (next: Route) => void }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["characters"],
    queryFn: fetchCharacters,
  });

  return (
    <section className="saved">
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
      {data && data.total === 0 ? (
        <p className="hint">
          Поки що нікого немає. Візард збере чернетку на кожному кроці — навіть якщо закрити вкладку.
        </p>
      ) : null}
      {data && data.total > 0 ? (
        <ul className="character-list">
          {data.items.map((item) => (
            <li key={item.id}>
              <button type="button" className="link-button" onClick={() => navigate({ name: "character", id: item.id })}>
                {item.name}
              </button>
              <span className="meta"> рівень {item.total_level}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function CharacterPage({
  id,
  tab,
  navigate,
}: {
  id: string;
  tab?: string;
  navigate: (next: Route) => void;
}) {
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
      <CharacterView initial={data.sheet} initialTab={tab} />
    </>
  );
}

function LevelUpPage({ id, navigate }: { id: string; navigate: (next: Route) => void }) {
  const queryClient = useQueryClient();

  return (
    <>
      <p className="crumbs">
        <button
          type="button"
          className="link-button"
          onClick={() => navigate({ name: "character", id })}
        >
          ← до листа
        </button>
      </p>
      <LevelUpWizard
        characterId={id}
        onCancel={() => navigate({ name: "character", id })}
        onOpenSpells={() => navigate({ name: "character", id, tab: "spells" })}
        onDone={(report) => {
          // Лист уже змінився на сервері: стара відповідь у кеші недійсна.
          void queryClient.invalidateQueries({ queryKey: ["character", id] });
          void queryClient.invalidateQueries({ queryKey: ["level-up", id] });
          void queryClient.invalidateQueries({ queryKey: ["characters"] });
          window.location.hash = `#/character/${encodeURIComponent(id)}`;
          console.info(
            `рівень ${report.total_level_before} → ${report.total_level_after}: ` +
              `${report.class_name} ${report.from_level} → ${report.to_level}`,
          );
        }}
      />
    </>
  );
}

function Shell() {
  const [route, navigate] = useRoute();

  // Лист персонажа має темну «дошку» на всю ширину; решта застосунку світла.
  // Клас ставимо і на <html>, інакше за межами body видно світлий canvas.
  useEffect(() => {
    document.body.classList.toggle("board", route.name === "character");
    document.documentElement.classList.toggle("board", route.name === "character");
    return () => {
      document.body.classList.remove("board");
      document.documentElement.classList.remove("board");
    };
  }, [route.name]);

  return (
    <main className={route.name === "character" ? "app app--board" : "app"}>
      <p className="badge">
        Правила 2014 · {route.name === "create" ? "створення персонажа" : "листок персонажа"} · сервер рахує все
      </p>
      {route.name === "home" ? (
        <>
          <CharactersList navigate={navigate} />
          <section className="demo">
            <h2>Демо-документ експорту</h2>
            <DemoSheet />
          </section>
        </>
      ) : null}
      {route.name === "create" ? (
        <CreateWizard onFinished={(characterId) => navigate({ name: "character", id: characterId })} />
      ) : null}
      {route.name === "character" ? (
        <CharacterPage id={route.id} tab={route.tab} navigate={navigate} />
      ) : null}
      {route.name === "levelup" ? <LevelUpPage id={route.id} navigate={navigate} /> : null}
    </main>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Shell />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

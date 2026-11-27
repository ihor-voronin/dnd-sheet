/** Термін із поясненням: латунний пунктир під словом.
 *
 * Усередині `GlossProvider` (візард, підвищення рівня) натискання відкриває
 * пояснення на полях — у маргіналії праворуч або в шторці на телефоні. Поза
 * ним — звичайна підказка при наведенні й фокусі.
 */

import * as Tooltip from "@radix-ui/react-tooltip";
import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { gloss } from "../glossary";
import type { GlossEntry } from "../glossary";

interface GlossState {
  active: string | null;
  open: (key: string) => void;
  close: () => void;
}

const GlossContext = createContext<GlossState | null>(null);

export function GlossProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<string | null>(null);
  const value = useMemo<GlossState>(
    () => ({ active, open: setActive, close: () => setActive(null) }),
    [active],
  );
  return <GlossContext.Provider value={value}>{children}</GlossContext.Provider>;
}

export function useGloss(): GlossState | null {
  return useContext(GlossContext);
}

export function GlossBody({ entry }: { entry: GlossEntry }) {
  return (
    <>
      <p className="gloss__title">
        {entry.term}
        {entry.en ? <span className="gloss__en"> ({entry.en})</span> : null}
      </p>
      <p className="gloss__what">{entry.what}</p>
      {entry.play ? <p className="gloss__play">{entry.play}</p> : null}
    </>
  );
}

/** `k` — ключ глосарію; `children` — слово на екрані (за замовчуванням — назва терміна). */
export function Term({ k, children }: { k: string; children?: ReactNode }) {
  const entry = gloss(k);
  const context = useGloss();
  const label = children ?? entry?.term ?? k;
  if (!entry) return <>{label}</>;

  if (context) {
    const active = context.active === k;
    return (
      <button
        type="button"
        className={`term ${active ? "term--active" : ""}`}
        aria-expanded={active}
        aria-label={`${typeof label === "string" ? label : entry.term} — пояснення`}
        onClick={(event) => {
          event.stopPropagation();
          if (active) context.close();
          else context.open(k);
        }}
      >
        {label}
      </button>
    );
  }

  return (
    <Tooltip.Root delayDuration={150}>
      <Tooltip.Trigger asChild>
        <button type="button" className="term">
          {label}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="hint-content gloss" sideOffset={6} collisionPadding={8}>
          <GlossBody entry={entry} />
          <Tooltip.Arrow className="hint-arrow" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/** Пояснення, відкрите з `Term` — для маргіналії. */
export function ActiveGloss({ fallback }: { fallback?: ReactNode }) {
  const context = useGloss();
  const entry = context?.active ? gloss(context.active) : undefined;
  if (!entry) return <>{fallback ?? null}</>;
  return (
    <div className="gloss gloss--margin" aria-live="polite">
      <GlossBody entry={entry} />
      <button type="button" className="link-button" onClick={() => context?.close()}>
        Закрити пояснення
      </button>
    </div>
  );
}

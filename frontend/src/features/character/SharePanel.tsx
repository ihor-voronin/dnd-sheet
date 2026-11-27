/**
 * «Поділитися»: посилання на лист лише для перегляду.
 *
 * За посиланням лист відкривається без входу: його видно, можна надрукувати чи
 * завантажити PDF, але змінити нічого не можна. Нове посилання замінює старе
 * (старе перестає працювати), «Вимкнути» відкликає його зовсім.
 */

import { useEffect, useState } from "react";

import { createShare, fetchShare, revokeShare } from "../../api";

export function SharePanel({ characterId, onClose }: { characterId: string; onClose: () => void }) {
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchShare(characterId)
      .then((share) => alive && setToken(share.token))
      .catch((failure: unknown) => alive && setError(failure instanceof Error ? failure.message : String(failure)));
    return () => {
      alive = false;
    };
  }, [characterId]);

  const link = token ? `${window.location.origin}/#/s/${token}` : "";

  async function act(action: () => Promise<{ token: string | null }>) {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      setToken((await action()).token);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setError("Не вдалося скопіювати — виділіть посилання й скопіюйте вручну.");
    }
  }

  return (
    <section className="share-panel" aria-label="Поділитися листом">
      <header className="share-panel__head">
        <h2 className="share-panel__title">Поділитися листом</h2>
        <button type="button" className="link-button" onClick={onClose}>
          закрити
        </button>
      </header>
      <p className="share-panel__lead">
        За посиланням лист видно без входу: його можна переглянути, надрукувати й завантажити PDF, але не
        змінити. Видно все, що на листі, разом із нотатками.
      </p>
      {token === undefined && !error ? <p className="meta">Перевіряємо…</p> : null}
      {token === null ? (
        <button type="button" className="button button--primary" disabled={busy} onClick={() => void act(() => createShare(characterId))}>
          Створити посилання
        </button>
      ) : null}
      {token ? (
        <>
          <div className="share-panel__link">
            <input
              readOnly
              value={link}
              aria-label="Посилання на лист лише для перегляду"
              onFocus={(event) => event.currentTarget.select()}
            />
            <button type="button" className="button button--primary" onClick={() => void copy()}>
              {copied ? "Скопійовано" : "Копіювати"}
            </button>
          </div>
          <div className="share-panel__actions">
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => void act(() => createShare(characterId))}
              title="Старе посилання перестане працювати"
            >
              Нове посилання
            </button>
            <button type="button" className="link-button" disabled={busy} onClick={() => void act(() => revokeShare(characterId))}>
              Вимкнути посилання
            </button>
          </div>
        </>
      ) : null}
      {error ? <p className="status status--error">{error}</p> : null}
    </section>
  );
}

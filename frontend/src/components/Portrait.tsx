/**
 * Портрет персонажа: SVG із сервера (`/assets/avatars/<версія>/<id>.svg`).
 *
 * Розмір задано в атрибутах — місце під картинку відоме ще до завантаження,
 * сторінка не стрибає. Поза екраном картинка не вантажиться (`loading="lazy"`).
 * Якщо файл не прийшов — ініціали, як було до портретів.
 */
import { useState } from "react";

export interface PortraitCard {
  id: string;
  url: string;
  label: string;
  /** Гравець обрав сам (false — типовий за видом, класом і статтю). */
  chosen?: boolean;
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.slice(0, 2).map((word) => Array.from(word)[0] ?? "");
  return letters.join("").toUpperCase() || "?";
}

export function PortraitImage({
  portrait,
  name,
  size,
  alt,
  eager = false,
}: {
  portrait?: PortraitCard | null;
  /** Імʼя героя: з нього ініціали, якщо картинки немає. */
  name: string;
  size: number;
  /** Текст для читача екрана; порожній — картинка лише прикраса поруч з іменем. */
  alt?: string;
  /** Шапка листа — видно одразу, тож не відкладаємо. */
  eager?: boolean;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  if (!portrait || failed === portrait.url) {
    return (
      <span className="portrait-monogram" aria-hidden="true">
        {initials(name)}
      </span>
    );
  }
  return (
    <img
      className="portrait-img"
      src={portrait.url}
      width={size}
      height={size}
      alt={alt ?? portrait.label}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      onError={() => setFailed(portrait.url)}
    />
  );
}

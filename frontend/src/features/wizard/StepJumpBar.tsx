/**
 * Швидкий перехід по розділах кроку — для телефона.
 *
 * На вузькому екрані крок «Передісторія» — це список на кілька екранів, а під
 * ним навички, мови й інструменти; щоб дійти до них, гравець гортав сам.
 * Панель збирає розділи кроку з розмітки (блоки `.wizard-block` і все, що
 * позначене `data-jump="Назва"`) і кнопку «Далі», тож кроки не повторюють
 * свій зміст ще й тут. Стежить за змінами: розгорнули список — зʼявився пункт.
 */
import { useEffect, useState } from "react";

type Target = { label: string; element: HTMLElement };

const CANDIDATES = "[data-jump], .wizard-block";

function labelOf(element: HTMLElement): string {
  if (element.dataset.jump) return element.dataset.jump;
  const heading = element.querySelector("h3, h4, summary");
  const text = (heading?.textContent ?? "").replace(/\s+/g, " ").trim();
  // «Навички класу — 0 з 2» → «Навички класу»: лічильник видно в самому блоці.
  return text.split(/\s[—(·]\s?|:\s/)[0].slice(0, 28);
}

function collect(host: HTMLElement): Target[] {
  const all = [...host.querySelectorAll<HTMLElement>(CANDIDATES)];
  const targets = all
    // Вкладені блоки (картка всередині позначеного розділу) — не окремі пункти.
    .filter((element) => !all.some((other) => other !== element && other.contains(element)))
    .map((element) => ({ label: labelOf(element), element }))
    .filter((target) => target.label);
  // Кнопка, що веде на наступний крок: «Далі: …», «Зберегти й далі», «Створити…».
  const next = [...host.querySelectorAll<HTMLElement>(".wizard-step .button--primary")]
    .filter((button) => /далі|створити/i.test(button.textContent ?? ""))
    .pop();
  if (next) targets.push({ label: next.textContent?.trim() || "Далі", element: next });
  return targets;
}

function sameTargets(left: Target[], right: Target[]): boolean {
  return (
    left.length === right.length &&
    left.every((target, index) => target.element === right[index].element && target.label === right[index].label)
  );
}

export function StepJumpBar({ host, step }: { host: HTMLElement | null; step: string }) {
  const [targets, setTargets] = useState<Target[]>([]);

  useEffect(() => {
    const root = host;
    if (!root) return;
    let timer = 0;
    const refresh = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const found = collect(root);
        setTargets((current) => (sameTargets(current, found) ? current : found));
      }, 30);
    };
    refresh();
    const observer = new MutationObserver(refresh);
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    return () => {
      observer.disconnect();
      window.clearTimeout(timer);
    };
  }, [host, step]);

  // Два пункти — це «угорі» й «унизу»: така панель не економить прокрутки.
  if (targets.length < 3) return null;

  return (
    <nav className="step-jump" aria-label="Розділи кроку">
      {targets.map((target, index) => (
        <button
          key={`${index}-${target.label}`}
          type="button"
          className={`step-jump__item${target.element.classList.contains("button") ? " step-jump__item--next" : ""}`}
          onClick={() =>
            target.element.scrollIntoView({
              block: target.element.classList.contains("button") ? "center" : "start",
            })
          }
        >
          {target.label}
        </button>
      ))}
    </nav>
  );
}

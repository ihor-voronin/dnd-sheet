import { act, within } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";

type User = ReturnType<typeof userEvent.setup>;

/** Buttons that leave the screen under test (navigation, sign-out). */
const LEAVE = /^(← |Вийти|Мої персонажі|Головна|Довідник|Знайшли помилку|Увійти|Світла тема|Темна тема)/;

function label(element: HTMLElement): string {
  return (element.getAttribute("aria-label") ?? element.textContent ?? "").trim().slice(0, 80);
}

async function settle(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

/**
 * Exercise a screen like a curious player: press every button once, fill number and
 * text fields, pick the second option of every select — for several rounds, since
 * pressing a button often reveals new ones (a form, a confirmation, a tab).
 *
 * It asserts nothing by itself: a component that throws fails the test, and the
 * caller checks that the screen is still there.
 */
export async function explore(
  user: User,
  root: HTMLElement = document.body,
  { rounds = 4, skip = LEAVE, maxClicks = 150 }: { rounds?: number; skip?: RegExp; maxClicks?: number } = {},
): Promise<number> {
  const seen = new Set<string>();
  let clicks = 0;
  for (let round = 0; round < rounds; round += 1) {
    let progressed = false;

    for (const field of within(root).queryAllByRole("spinbutton") as HTMLInputElement[]) {
      const key = `n:${field.name || field.id || label(field)}:${round}`;
      if (seen.has(key) || field.disabled || field.readOnly) continue;
      seen.add(key);
      try {
        await user.clear(field);
        await user.type(field, "3");
      } catch {
        // the field vanished while typing
      }
    }
    for (const field of within(root).queryAllByRole("textbox") as HTMLInputElement[]) {
      const key = `t:${field.name || field.id || field.placeholder || label(field)}`;
      if (seen.has(key) || field.disabled || field.readOnly) continue;
      seen.add(key);
      try {
        await user.type(field, "ab");
      } catch {
        // the field vanished while typing
      }
    }
    for (const select of within(root).queryAllByRole("combobox") as HTMLSelectElement[]) {
      const key = `s:${select.name || select.id || label(select)}`;
      if (seen.has(key) || select.disabled || select.tagName !== "SELECT" || select.options.length < 2) continue;
      seen.add(key);
      try {
        await user.selectOptions(select, select.options[1].value);
      } catch {
        // the select vanished
      }
    }
    for (const box of within(root).queryAllByRole("checkbox") as HTMLInputElement[]) {
      const key = `c:${box.name || box.id || label(box)}`;
      if (seen.has(key) || box.disabled) continue;
      seen.add(key);
      try {
        await user.click(box);
      } catch {
        // the checkbox vanished
      }
    }

    const buttons = [
      ...within(root).queryAllByRole("button"),
      ...within(root).queryAllByRole("tab"),
      ...within(root).queryAllByRole("radio"),
    ];
    for (const button of buttons) {
      if (clicks >= maxClicks) return clicks;
      const name = label(button);
      const key = `b:${name}:${buttons.indexOf(button)}:${round === 0 ? 0 : seen.size % 3}`;
      if (seen.has(`b:${name}`) && seen.has(key)) continue;
      // Term tooltips ("… — пояснення") are covered by their own tests and only eat clicks here.
      if (
        skip.test(name) ||
        name.endsWith("пояснення") ||
        !button.isConnected ||
        (button as HTMLButtonElement).disabled
      ) {
        continue;
      }
      seen.add(key);
      seen.add(`b:${name}`);
      try {
        await user.click(button);
        clicks += 1;
        progressed = true;
      } catch {
        // the button vanished after the previous click
      }
      await settle();
    }
    if (!progressed) break;
  }
  return clicks;
}

/**
 * Головна сторінка: що це, як виглядає лист, що в довіднику, з яких книг.
 *
 * Головний образ — надруковані аркуші (справжні сторінки PDF жреця 5 рівня,
 * `public/previews/`). Числа довідника — як зміст книги з крапками, а не
 * «великі цифри з підписом»: сторінка про книги, і зміст тут доречний.
 * Ціни й обкладинки — з `content/books_market.json` (звірено з маркетплейсом
 * D&D Beyond; дата перевірки показується поруч).
 */

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchBooksOverview } from "../../api";
import type { BookOverview } from "../../api";

/** Українська множина: 1 клас, 2 класи, 5 класів. */
function plural(count: number, forms: [string, string, string]): string {
  const tens = count % 100;
  const units = count % 10;
  if (tens >= 11 && tens <= 14) return forms[2];
  if (units === 1) return forms[0];
  if (units >= 2 && units <= 4) return forms[1];
  return forms[2];
}

const CATEGORY_FORMS: Record<string, [string, string, string]> = {
  class: ["клас", "класи", "класів"],
  subclass: ["підклас", "підкласи", "підкласів"],
  species: ["вид", "види", "видів"],
  background: ["передісторія", "передісторії", "передісторій"],
  feat: ["риса", "риси", "рис"],
  optionalfeature: ["опційне вміння", "опційні вміння", "опційних умінь"],
  spell: ["закляття", "закляття", "заклять"],
  item: ["предмет", "предмети", "предметів"],
};

/** Що в довіднику: рядок змісту і розділ бази знань, куди веде. */
const CONTENTS: { key: string; title: string; section: string; note?: (totals: Record<string, number>) => string }[] = [
  { key: "class", title: "Класи", section: "classes" },
  { key: "subclass", title: "Підкласи", section: "classes" },
  {
    key: "species",
    title: "Види",
    section: "species",
    note: (totals) => (totals.subspecies ? `і ${totals.subspecies} ${plural(totals.subspecies, ["підраса", "підраси", "підрас"])}` : ""),
  },
  { key: "background", title: "Передісторії", section: "backgrounds" },
  { key: "feat", title: "Риси", section: "feats" },
  { key: "optionalfeature", title: "Опційні вміння", section: "options" },
  { key: "spell", title: "Закляття", section: "spells" },
  { key: "item", title: "Предмети", section: "items" },
];

const GROUPS: { key: string; title: string; lead: string }[] = [
  { key: "core", title: "Основні правила", lead: "Без них гри немає: правила, класи, закляття, предмети." },
  { key: "player", title: "Для гравців", lead: "Нові підкласи, види, риси й закляття." },
  { key: "setting", title: "Світи й сеттинги", lead: "Види, передісторії й підкласи окремих світів." },
  { key: "adventure", title: "Пригоди", lead: "З пригод у довідник ідуть предмети, передісторії й кілька заклять." },
];

function priceLabel(book: BookOverview): string {
  if (book.price) return `${book.price_from ? "від " : ""}$${book.price}`;
  return book.note ?? "";
}

/** «40 підкласів, 361 закляття, 42 риси» — найбільше, що книга дає листу. */
function bookGives(book: BookOverview): string {
  return Object.entries(book.counts)
    .filter(([key]) => CATEGORY_FORMS[key])
    .sort((left, right) => right[1] - left[1])
    .slice(0, 4)
    .map(([key, count]) => `${count} ${plural(count, CATEGORY_FORMS[key])}`)
    .join(", ");
}

function checkedLabel(date: string | null): string {
  if (!date) return "";
  const [year, month, day] = date.split("-");
  return `${day}.${month}.${year}`;
}

export function Home({
  account,
  onOpenKb,
  actions,
}: {
  /** Список персонажів або вхід — залежно від того, чи гравець увійшов. */
  account: ReactNode;
  onOpenKb: (section?: string) => void;
  actions: ReactNode;
}) {
  const overview = useQuery({ queryKey: ["books-overview"], queryFn: fetchBooksOverview, staleTime: Infinity });
  const data = overview.data;
  const totals = data?.totals ?? {};

  return (
    <div className="home">
      <section className="home-hero">
        <div className="home-hero__text">
          <h1 className="home-hero__title">Лист персонажа D&amp;D українською</h1>
          <p className="home-hero__lead">
            Створіть героя за правилами Книги гравця 2014 — від виду й класу до заклять і спорядження.
            Лист сам рахує бонуси, комірки й хіти, а надрукований виглядає як папір за столом:
            чорним по білому, з місцем для олівця.
          </p>
          <div className="home-hero__actions">{actions}</div>
        </div>
        <figure className="home-sheets" aria-label="Надрукований лист персонажа: головна сторінка, закляття й пояснення вмінь">
          <div className="home-sheets__stack">
          <img className="home-sheets__page home-sheets__page--back" src="/previews/sheet-features.png" alt="" loading="lazy" />
          <img className="home-sheets__page home-sheets__page--mid" src="/previews/sheet-spells.png" alt="" loading="lazy" />
          <img
            className="home-sheets__page home-sheets__page--front"
            src="/previews/sheet-front.png"
            alt="Головна сторінка надрукованого листа: характеристики, навички, хіти, атаки"
          />
          </div>
          <figcaption className="home-sheets__caption">
            Так виглядає PDF: головна сторінка, закляття, спорядження, журнал пригод і пояснення вмінь.
          </figcaption>
        </figure>
      </section>

      <section className="home-account">{account}</section>

      <section className="home-contents" aria-labelledby="home-contents-title">
        <h2 id="home-contents-title" className="home-h2">Що всередині довідника</h2>
        <p className="home-note">
          Усе доступне без входу: розділи довідника відкриваються з цього змісту.
          {data ? ` Зібрано з ${data.sources} джерел.` : ""}
        </p>
        <ol className="home-toc">
          {CONTENTS.map((row) => (
            <li key={row.key}>
              <button type="button" className="home-toc__row" onClick={() => onOpenKb(row.section)}>
                <span className="home-toc__title">
                  {row.title}
                  {row.note && totals[row.key] ? <span className="home-toc__note"> {row.note(totals)}</span> : null}
                </span>
                <span className="home-toc__dots" aria-hidden="true" />
                <span className="home-toc__count">{totals[row.key] ?? "…"}</span>
              </button>
            </li>
          ))}
        </ol>
      </section>

      <section className="home-books" aria-labelledby="home-books-title">
        <h2 id="home-books-title" className="home-h2">Книги, з яких зібрано довідник</h2>
        <p className="home-note">
          Тексти правил належать Wizards of the Coast. Якщо граєте з довідником — купіть книги:
          так ви підтримуєте тих, хто їх пише. Ціни — цифрові версії на D&amp;D Beyond у доларах США,
          {data?.checked ? ` перевірено ${checkedLabel(data.checked)}` : " перевіряються вручну"}; вони змінюються.
        </p>
        {overview.isPending ? <p className="status">Читаємо перелік книг…</p> : null}
        {GROUPS.map((group) => {
          const books = (data?.books ?? []).filter((book) => book.group === group.key);
          if (!books.length) return null;
          return (
            <div key={group.key} className="home-shelf">
              <h3 className="home-shelf__title">{group.title}</h3>
              <p className="home-shelf__lead">{group.lead}</p>
              <ul className="home-shelf__list">
                {books.map((book) => (
                  <li key={book.id} className="home-book">
                    {book.cover ? (
                      <img
                        className="home-book__cover"
                        src={book.cover}
                        alt=""
                        loading="lazy"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <span className="home-book__cover home-book__cover--blank" aria-hidden="true" />
                    )}
                    <div className="home-book__body">
                      <span className="home-book__title">{book.title_uk ?? book.title}</span>
                      <span className="home-book__en">{book.title}</span>
                      {bookGives(book) ? <span className="home-book__gives">{bookGives(book)}</span> : null}
                    </div>
                    <div className="home-book__buy">
                      <span className="home-book__price">{priceLabel(book)}</span>
                      {book.url ? (
                        <a className="home-book__link" href={book.url} target="_blank" rel="noopener noreferrer">
                          D&amp;D Beyond
                        </a>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
        {data && data.other_sources ? (
          <p className="home-note">
            Ще {data.other_sources} {plural(data.other_sources, ["джерело", "джерела", "джерел"])} — промо-матеріали,
            безкоштовні пригоди, Unearthed Arcana й Plane Shift — дають {data.other_entries}{" "}
            {plural(data.other_entries, ["запис", "записи", "записів"])}.
          </p>
        ) : null}
      </section>

      <section className="home-disclaimer" aria-labelledby="home-disclaimer-title">
        <h2 id="home-disclaimer-title" className="home-h2">Застереження</h2>
        <p>
          Це неофіційний некомерційний фанатський проєкт для власної ігрової групи. Він безкоштовний, не має реклами
          й платних функцій і не повʼязаний з Wizards of the Coast чи D&amp;D Beyond.
        </p>
        <p>
          Dungeons &amp; Dragons, D&amp;D, назви книг, світів, персонажів і тексти правил — власність Wizards of the
          Coast LLC. Переклад українською — аматорський, для зручності за столом; офіційне формулювання правил — у
          книгах. Обкладинки показано з сайту D&amp;D Beyond як посилання на сторінку книги.
        </p>
        <p className="home-disclaimer__fcp" lang="en">
          This site is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards.
          Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
        </p>
      </section>
    </div>
  );
}

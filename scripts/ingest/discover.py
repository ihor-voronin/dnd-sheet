"""Побудова списку сторінок книги.

D&D Beyond веде сторінки книг трьома формами шляху:

    /sources/dnd/<book>[/<section>]      — корінь книги (лендінг)
    /sources/<book>/<section>            — сторінки куплених книг
    /compendium/rules/<book>/<section>   — безкоштовні правила (Basic Rules, SRD)

Slug у шляху не завжди збігається з id у sources.yml
(basic-rules-2014 -> /compendium/rules/basic-rules/..., phb-2014 -> /sources/phb/...),
тому «свою» книгу визначаємо за ключем (kind, slug), який домінує на корені,
плюс за збігом id.

Для куплених книг корінь містить повний зміст у
<div class="compendium-toc-full">, і посилання в ньому вже мають правильні href.
Такий зміст вважаємо авторитетним: беремо сторінки з нього й не обходимо кожну
сторінку заради пошуку посилань — це вдвічі менше запитів і вдвічі менший ризик
CAPTCHA. Якщо змісту немає (безкоштовні правила) — падаємо на обхід у ширину.
"""

from __future__ import annotations

import collections
import json
import re
import sys

from . import config, session

# Сторінка книги: /sources/<book>[/<tail>], /sources/dnd/<book>[/<tail>],
# /compendium/rules/<book>[/<tail>], /compendium/adventures/<book>[/<tail>].
#
# Пригоди (WDH, WDMM, LLoK) мають корінь /sources/dnd/<book>, а власні сторінки —
# під /compendium/adventures/<book>/... Це четверта форма шляху; без неї зміст
# пригоди не розпізнавався зовсім.
PAGE_RE = re.compile(
    r"/(?:(?P<compendium>compendium/(?:rules|adventures))|sources(?:/(?P<dnd>dnd))?)"
    r"/(?P<slug>[A-Za-z0-9][A-Za-z0-9-]*)"
    r"(?P<tail>(?:/[A-Za-z0-9][A-Za-z0-9-]*)*)/?",
    re.IGNORECASE,
)

# Грубий пошук кандидатів у HTML (далі кожен перевіряється PAGE_RE).
CANDIDATE_RE = re.compile(r"/(?:sources|compendium)/[A-Za-z0-9_\-/]+", re.IGNORECASE)

TOC_CLASS = "compendium-toc-full"

_DIV_TAG_RE = re.compile(r"<div\b[^>]*>|</div>", re.IGNORECASE)
_DIV_OPEN_RE = re.compile(r"<div\b[^>]*>", re.IGNORECASE)


def parse_rel(path: str) -> tuple[str, str, str] | None:
    """(kind, slug, tail) для шляху сторінки книги або None, якщо це не сторінка."""
    match = PAGE_RE.fullmatch(path if path.startswith("/") else "/" + path)
    if not match:
        return None
    kind = (match.group("compendium") or "sources").lower()
    slug = match.group("slug").lower()
    tail = (match.group("tail") or "").strip("/").lower()
    return kind, slug, tail


def normalize(path: str) -> str | None:
    """Канонічний вигляд шляху без провідного слеша; None якщо не сторінка книги."""
    match = PAGE_RE.fullmatch(path if path.startswith("/") else "/" + path)
    if not match:
        return None
    return match.group(0).strip("/").lower()


def extract_rels(html: str) -> set[str]:
    """Усі сторінки книг, згадані в HTML (і в інлайн-JSON)."""
    found: set[str] = set()
    for match in CANDIDATE_RE.finditer(html):
        rel = normalize(match.group(0))
        if rel:
            found.add(rel)
    return found


def key_of(rel: str) -> tuple[str, str]:
    """Ключ книги: (kind, slug). Саме він відрізняє одну книгу від іншої."""
    parsed = parse_rel(rel)
    if parsed is None:
        return "", ""
    kind, slug, _ = parsed
    return kind, slug


def page_url(rel: str) -> str:
    return f"{config.BASE_URL}/{rel.lstrip('/')}"


def tail_of(rel: str) -> str:
    """Частина шляху після slug книги: 'races', 'spells/fireball'; '' для кореня."""
    parsed = parse_rel(rel)
    return parsed[2] if parsed else ""


def _div_span(html: str, start: int) -> str:
    """Зріз HTML від <div у позиції start до парного </div>."""
    depth = 0
    for match in _DIV_TAG_RE.finditer(html, start):
        if match.group(0)[1] == "/":
            depth -= 1
            if depth == 0:
                return html[start : match.end()]
        else:
            depth += 1
    return html[start:]


def toc_rels(html: str) -> list[str]:
    """Сторінки з блоку змісту книги, у порядку змісту.

    Клас шукаємо саме в тегах <div ...>: рядок «compendium-toc-full» трапляється
    ще й у CSS/JS, і простий find() брав би те входження, обрізаючи блок.
    """
    for match in _DIV_OPEN_RE.finditer(html):
        if TOC_CLASS not in match.group(0):
            continue
        ordered: list[str] = []
        seen: set[str] = set()
        for candidate in CANDIDATE_RE.finditer(_div_span(html, match.start())):
            rel = normalize(candidate.group(0))
            if rel and rel not in seen:
                seen.add(rel)
                ordered.append(rel)
        if ordered:
            return ordered
    return []


def _book_keys(seed_html: str, source: str, seed: str) -> set[tuple[str, str]]:
    counts: collections.Counter[tuple[str, str]] = collections.Counter(
        key_of(rel) for rel in extract_rels(seed_html)
    )
    # Домінантні ключі — це і є книга. Поріг 3 відсікає випадкові перехресні
    # посилання з навігації на інші книги.
    allowed = {key for key, count in counts.items() if count >= 3}
    allowed |= {key for key in counts if key[1] == source.lower()}
    allowed.add(key_of(seed))
    return allowed


def discover(fetcher: session.Fetcher, source: str) -> list[str]:
    """Список сторінок книги (без кореня), відсортований за хвостом шляху."""
    seed = f"sources/dnd/{source}"
    print(f"  discover {source}/", flush=True)
    seed_html = fetcher.get(page_url(seed))

    allowed = _book_keys(seed_html, source, seed)
    print(f"  книга(-и): {sorted({f'{k[0]}:{k[1]}' for k in allowed})}", flush=True)

    toc = [rel for rel in toc_rels(seed_html) if key_of(rel) in allowed]
    if toc:
        print(f"  зміст: {len(toc)} сторінок", flush=True)
        order = [seed, *toc]
    else:
        print("  змісту немає — обхід у ширину", flush=True)
        order = _bfs(fetcher, seed, seed_html, allowed)

    return _dedupe(order)


def pages_from_toc(html: str, source: str) -> list[str]:
    """Сторінки книги з її кореня. Порожній список — не вдалося нічого знайти.

    Потрібна, коли HTML уже є під рукою: сторінку завантажив браузер, і його
    сесію не можна повторити з httpx.

    Межі книги тут визначаються не за порогом по всьому документу (він залежить
    від кількості посилань), а за ключем, що домінує всередині самого змісту:
    зміст — це і є перелік сторінок цієї книги.

    Якщо блоку змісту немає (короткі пригоди на одну сторінку: Frozen Sick,
    Lightning Keep, Monstrous Compendium...), беремо всі сторінки цієї ж книги,
    згадані на корені. Для таких книг корінь і є весь перелік.
    """
    rels = toc_rels(html)
    if rels:
        counts = collections.Counter(key_of(rel) for rel in rels)
        book_key, _ = counts.most_common(1)[0]
        kept = [rel for rel in rels if key_of(rel) == book_key]
        return _dedupe([f"sources/dnd/{source}", *kept])

    own_key = ("sources", source.lower())
    links = sorted(rel for rel in extract_rels(html) if key_of(rel) == own_key)
    if not links:
        return []
    print(f"  змісту немає: {len(links)} сторінок із кореня", flush=True)
    return _dedupe([f"sources/dnd/{source}", *links])


def _dedupe(order: list[str]) -> list[str]:
    """Одна сторінка буває під різними шляхами — лишаємо один варіант."""
    if len(order) > config.MAX_PAGES_PER_SOURCE:
        print(
            f"  УВАГА: досягнуто ліміт {config.MAX_PAGES_PER_SOURCE} сторінок, список обрізано",
            file=sys.stderr,
        )
        order = order[: config.MAX_PAGES_PER_SOURCE]

    best: dict[str, str] = {}
    for rel in order:
        tail = tail_of(rel)
        if not tail:
            continue
        current = best.get(tail)
        if current is None or _preference(rel) > _preference(current):
            best[tail] = rel
    return [best[tail] for tail in sorted(best)]


def _bfs(
    fetcher: session.Fetcher,
    seed: str,
    seed_html: str,
    allowed: set[tuple[str, str]],
) -> list[str]:
    queue: list[str] = [seed]
    visited: set[str] = set(queue)
    order: list[str] = []
    cache: dict[str, str] = {seed: seed_html}

    while queue:
        rel = queue.pop(0)
        order.append(rel)
        html = cache.pop(rel, None)
        if html is None:
            print(f"  discover {tail_of(rel) or rel}", flush=True)
            try:
                html = fetcher.get(page_url(rel))
            except session.ChallengeError:
                raise
            except session.SessionError as exc:
                print(f"    пропуск: {exc}", file=sys.stderr)
                continue

        if len(visited) > config.MAX_PAGES_PER_SOURCE:
            break

        for candidate in sorted(extract_rels(html)):
            if candidate in visited:
                continue
            if key_of(candidate) not in allowed:
                continue
            visited.add(candidate)
            queue.append(candidate)

    return order


def _preference(rel: str) -> int:
    """sources/ краще за compendium/rules/ — там актуальніша версія сторінки."""
    return 1 if rel.startswith("sources/") else 0


def save_index(source: str, rels: list[str]) -> "object":
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    target = config.INDEX_DIR / f"{source}.json"
    payload = {"source_id": source, "count": len(rels), "pages": rels}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_index(source: str) -> list[str]:
    target = config.INDEX_DIR / f"{source}.json"
    if not target.exists():
        raise FileNotFoundError(f"Немає індексу {target} — спочатку виконай discover")
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload.get("pages") or payload.get("paths") or []

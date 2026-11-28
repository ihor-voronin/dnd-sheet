"""Відкриті сторінки довідника: HTML від сервера, адреси, карта сайту, ліцензійна політика.

Сторінки читають справжній корпус (як і решта API-тестів); словники SPA —
з маленького `kb-labels.fixture.json`, бо в тестах немає зібраного `dist/`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
TMP = HERE / "_tmp_site_pages"
LABELS = HERE / "kb-labels.fixture.json"


@contextmanager
def _env(**values: str) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="module")
def tmp() -> Iterator[Path]:
    shutil.rmtree(TMP, ignore_errors=True)
    (TMP / "dist" / "assets").mkdir(parents=True)
    (TMP / "dist" / "index.html").write_text("<!doctype html><title>SPA</title><div id=root></div>", encoding="utf-8")
    (TMP / "dist" / "assets" / "alegreya-cyrillic-400-normal-abc.woff2").write_bytes(b"font")
    try:
        yield TMP
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


def _app(tmp: Path, name: str, **extra: str):  # noqa: ANN202 — FastAPI
    with _env(
        DNDSHEET_DATA_DIR=str(tmp / name),
        DNDSHEET_SPA_DIST=str(tmp / "dist"),
        DNDSHEET_KB_LABELS=str(LABELS),
        **extra,
    ):
        app = create_app()
        if not app.state.golden_cases:
            pytest.skip("немає корпусу")
        # Каталог збирається при першому запиті — поки змінні ще встановлені.
        client = TestClient(app)
        assert client.get("/kb").status_code == 200
    return app, client


@pytest.fixture(scope="module")
def site(tmp: Path):  # noqa: ANN201
    return _app(tmp, "data", DNDSHEET_KB_PROPRIETARY="full")


@pytest.fixture(scope="module")
def client(site) -> TestClient:  # noqa: ANN001
    return site[1]


@pytest.fixture(scope="module")
def catalog(site):  # noqa: ANN001, ANN201
    return site[0].state.kb_catalog


def _title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html)
    assert match
    return match.group(1)


def _jsonld(html: str) -> list[dict]:
    return [
        json.loads(block) for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    ]


# --- довідник -----------------------------------------------------------------


def test_home_links_every_section(client: TestClient) -> None:
    response = client.get("/kb")
    assert response.status_code == 200
    html = response.text
    assert _title(html).startswith("Довідник D&amp;D 5e українською")
    for section in ("species", "classes", "backgrounds", "feats", "spells", "options", "items"):
        assert f'href="/kb/{section}"' in html
    assert '<link rel="canonical" href="http://localhost:8000/kb">' in html
    assert 'href="/kb/glossary"' in html and 'href="/guides/create-character"' in html
    assert "noindex" not in html
    # Шрифти — з тієї самої збірки SPA, з хешем у назві.
    assert "url(/assets/alegreya-cyrillic-400-normal-abc.woff2)" in html
    assert response.headers["cache-control"].startswith("public")


def test_head_and_trailing_slashes(client: TestClient) -> None:
    assert client.head("/kb").status_code == 200
    for path, target in (("/kb/", "/kb"), ("/kb/spells/", "/kb/spells")):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 301
        assert response.headers["location"] == target


def test_spell_section_groups_by_level(client: TestClient) -> None:
    html = client.get("/kb/spells").text
    assert "<h2>Заговори</h2>" in html and "<h2>9 рівень</h2>" in html
    assert 'href="/kb/spells/fireball"' in html
    assert "data-filter" in html and 'data-q="fireball' in html
    crumbs = _jsonld(html)[0]
    assert crumbs["@type"] == "BreadcrumbList"
    assert [item["name"] for item in crumbs["itemListElement"]] == ["Головна", "Довідник", "Закляття"]


def test_spell_page_is_ukrainian_and_complete(client: TestClient) -> None:
    response = client.get("/kb/spells/fireball")
    assert response.status_code == 200
    html = response.text
    assert _title(html) == "Вогняна куля (Fireball) — закляття D&amp;D 5e українською"
    assert '<h1>Вогняна куля <span class="en" lang="en">Fireball</span></h1>' in html
    description = re.search(r'<meta name="description" content="(.*?)">', html).group(1)
    assert description.startswith("Закляття, 3 рівень") and len(description) <= 170
    assert "Час накладання" in html and "150 фт" in html
    # Текст — український, а не книги.
    assert "вогн" in html.lower().split("<main", 1)[1]
    assert 'href="/kb/classes/wizard"' in html, "закляття веде до класів, що його мають"
    assert "System Reference Document 5.1" in html, "SRD (CC BY 4.0) вимагає атрибуції"
    assert 'href="/#/create"' in html


def test_old_and_foreign_slugs_redirect_to_one_address(client: TestClient) -> None:
    response = client.get("/kb/spells/abi-dalzim-s-horrid-wilting", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/kb/spells/abi-dalzims-horrid-wilting"
    assert client.get(response.headers["location"]).status_code == 200


def test_unknown_pages_are_404_and_noindex(client: TestClient) -> None:
    for path in ("/kb/monsters", "/kb/spells/no-such-spell", "/kb/classes/warlock/no-such-patron"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert '<meta name="robots" content="noindex, follow">' in response.text
        assert response.headers["x-robots-tag"] == "noindex"


def test_species_page_has_facts_traits_and_subspecies(client: TestClient) -> None:
    html = client.get("/kb/species/dwarf").text
    assert _title(html) == "Дворф (Dwarf) — раса D&amp;D 5e українською"
    assert "25 фт (≈ 8 м)" in html and "+2 СТА" in html
    assert 'href="/kb/glossary#darkvision"' in html, "термін веде в глосарій"
    assert "бойова сокира" in html, "зброя — назвою предмета"
    assert "Підраса:" in html and "Особливості" in html


def test_class_page_lists_features_subclasses_and_spells(client: TestClient) -> None:
    html = client.get("/kb/classes/warlock").text
    assert _title(html).startswith("Чаклун (Warlock) — клас D&amp;D 5e")
    assert "Харизма, Статура" in html and "магія пакту" in html
    assert "1 рівень · " in html
    assert 'href="/kb/classes/warlock/the-archfey"' in html
    assert "Закляття класу" in html and 'href="/kb/spells/eldritch-blast"' in html


def test_subclass_page(client: TestClient) -> None:
    response = client.get("/kb/classes/warlock/the-archfey")
    assert response.status_code == 200
    html = response.text
    assert "— підклас D&amp;D 5e (Чаклун)" in _title(html)
    assert [item["name"] for item in _jsonld(html)[0]["itemListElement"]][-2:] == ["Чаклун", "Архіфея"]
    assert "Уміння підкласу" in html


def test_background_page(client: TestClient) -> None:
    html = client.get("/kb/backgrounds/acolyte").text
    assert _title(html) == "Послушник (Acolyte) — передісторія D&amp;D 5e українською"
    assert "Проникливість, Релігія" in html and "Спорядження" in html and "15 зм" in html


@pytest.mark.parametrize("section", ["feats", "options", "items", "species", "backgrounds"])
def test_every_section_and_its_first_entry_render(client: TestClient, catalog, section: str) -> None:  # noqa: ANN001
    assert client.get(f"/kb/{section}").status_code == 200
    first = catalog.records(section)[0]
    response = client.get(first.path)
    assert response.status_code == 200, first.path
    assert f'<link rel="canonical" href="http://localhost:8000{first.path}">' in response.text


def test_classes_section_shows_subclasses(client: TestClient) -> None:
    html = client.get("/kb/classes").text
    assert 'href="/kb/classes/warlock"' in html and 'href="/kb/classes/warlock/the-archfey"' in html


def test_glossary_and_terminology(client: TestClient) -> None:
    html = client.get("/kb/glossary").text
    assert 'id="hit_die"' in html and "Кість хітів" in html and "Hit Die" in html
    assert "Словник термінів" in html and "<td>Сила</td>" in html
    assert any(block["@type"] == "DefinedTermSet" for block in _jsonld(html))


def test_guide_leads_into_the_compendium_and_the_wizard(client: TestClient) -> None:
    html = client.get("/guides/create-character").text
    assert _title(html).startswith("Як створити персонажа D&amp;D 5e")
    assert 'href="/kb/classes/warlock"' in html and 'href="/kb/species/dwarf"' in html
    assert 'href="/kb/glossary#saving_throw"' in html
    assert 'href="/#/create"' in html


# --- карта сайту, robots, llms.txt ------------------------------------------------


def test_sitemap_index_and_parts(client: TestClient, catalog) -> None:  # noqa: ANN001
    index = client.get("/sitemap.xml")
    assert index.status_code == 200
    assert index.headers["content-type"].startswith("application/xml")
    assert "<sitemapindex" in index.text
    parts = re.findall(r"<loc>http://localhost:8000/sitemaps/(\w+)\.xml</loc>", index.text)
    assert parts[0] == "pages" and "spells" in parts and "items" in parts
    pages = client.get("/sitemaps/pages.xml").text
    assert "<loc>http://localhost:8000/</loc>" in pages and "<loc>http://localhost:8000/kb/glossary</loc>" in pages
    spells = client.get("/sitemaps/spells.xml").text
    assert "<loc>http://localhost:8000/kb/spells/fireball</loc>" in spells
    classes = client.get("/sitemaps/classes.xml").text
    assert "/kb/classes/warlock/the-archfey</loc>" in classes
    hidden = [record.path for record in catalog.all_records() if not record.publication.index]
    listed = "".join(client.get(f"/sitemaps/{part}.xml").text for part in parts)
    assert not [path for path in hidden if f"{path}</loc>" in listed], "сторінки з noindex не йдуть у карту"
    assert client.get("/sitemaps/monsters.xml").status_code == 404


def test_robots_keeps_private_paths_closed(client: TestClient) -> None:
    text = client.get("/robots.txt").text
    assert "Disallow: /mcp" in text and "Disallow: /authorize" in text
    assert "Disallow: /kb" not in text
    assert "Sitemap: http://localhost:8000/sitemap.xml" in text


def test_llms_txt_points_to_sections(client: TestClient) -> None:
    text = client.get("/llms.txt").text
    assert text.startswith("# Лист персонажа D&D 5e українською")
    assert "(http://localhost:8000/kb/spells)" in text and "/guides/create-character" in text


# --- сторінки SPA зі справжньою адресою ----------------------------------------------


def test_bugs_and_mcp_open_the_spa_in_a_browser(site) -> None:  # noqa: ANN001
    app, client = site
    assert "<title>SPA</title>" in client.get("/bugs").text
    page = client.get("/mcp", headers={"accept": "text/html,application/xhtml+xml"})
    assert page.status_code == 200 and "<title>SPA</title>" in page.text
    # Клієнт MCP і далі отримує протокол.
    with TestClient(app, base_url="http://localhost:8000") as live:
        response = live.post(
            "/mcp",
            headers={"accept": "application/json, text/event-stream", "content-type": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "t", "version": "1"},
                },
            },
        )
    assert response.status_code == 200
    assert response.json()["result"]["capabilities"]


# --- ліцензійна політика -------------------------------------------------------------


def test_summary_policy_hides_book_text_but_keeps_the_page(tmp: Path) -> None:
    app, client = _app(tmp, "summary", DNDSHEET_KB_PROPRIETARY="summary")
    catalog = app.state.kb_catalog
    closed = next(record for record in catalog.records("spells") if record.license == "proprietary")
    html = client.get(closed.path).text
    assert "Повний текст — у книзі" in html
    assert "noindex" not in html
    assert 'class="rules"' not in html, "тексту книги в HTML немає"
    srd = client.get("/kb/spells/fireball").text
    assert 'class="rules"' in srd, "SRD показується повністю за будь-якої політики"


def test_noindex_policy_keeps_text_but_leaves_the_index(tmp: Path) -> None:
    app, client = _app(tmp, "noindex", DNDSHEET_KB_PROPRIETARY="noindex")
    catalog = app.state.kb_catalog
    closed = next(record for record in catalog.records("feats") if record.license == "proprietary")
    response = client.get(closed.path)
    assert '<meta name="robots" content="noindex, follow">' in response.text
    assert 'class="rules"' in response.text
    assert f"{closed.path}</loc>" not in client.get("/sitemaps/feats.xml").text


# --- зображення: емблеми й портрети ---------------------------------------------


def _symbols(html: str) -> list[str]:
    return re.findall(r'<symbol id="e-([a-z-]+)"', html)


def test_home_has_section_emblems_inline(client: TestClient) -> None:
    html = client.get("/kb").text
    used = re.findall(r'<use href="#e-([a-z-]+)"/>', html)
    assert "section-spells" in used and "section-guide" in used
    # Лише використані форми, кожна один раз, і жодного зовнішнього файла.
    assert sorted(_symbols(html)) == sorted(set(used))
    assert "/assets/emblems/" not in html
    assert '<a href="/kb/credits">' in html


def test_spell_list_marks_schools(client: TestClient) -> None:
    html = client.get("/kb/spells").text
    assert set(_symbols(html)) <= {
        f"school-{school}"
        for school in (
            "abjuration",
            "conjuration",
            "divination",
            "enchantment",
            "evocation",
            "illusion",
            "necromancy",
            "transmutation",
        )
    }
    assert html.count('class="emblem emblem--inline"') > 100


def test_class_pages_have_emblem_and_portraits(client: TestClient) -> None:
    html = client.get("/kb/classes/wizard").text
    assert _symbols(html) == ["class-wizard"]
    portraits = re.findall(
        r'<img src="(/assets/avatars/[^"]+)" width="88" height="88" alt="([^"]+)" loading="lazy"', html
    )
    assert len(portraits) == 4
    assert all("-wizard-1.svg" in url for url, _ in portraits)
    assert all(alt.startswith("Портрет:") for _, alt in portraits)
    classes = client.get("/kb/classes").text
    assert "class-barbarian" in _symbols(classes)


def test_species_page_shows_its_portraits(client: TestClient) -> None:
    html = client.get("/kb/species/elf").text
    urls = re.findall(r'<img src="/assets/avatars/[^/]+/([a-z-]+\d)\.svg"', html)
    assert urls == ["elf-f-fighter-1", "elf-m-wizard-1", "elf-f-cleric-1", "elf-m-rogue-1"]
    kenku = client.get("/kb/species/kenku")
    if kenku.status_code == 200:
        assert "kenku-x-fighter-1" in kenku.text
    background = client.get("/kb/backgrounds/acolyte").text
    assert "/assets/avatars/" not in background
    assert _symbols(background) == ["section-backgrounds"]


def test_credits_page_names_every_author(client: TestClient) -> None:
    response = client.get("/kb/credits")
    assert response.status_code == 200
    html = response.text
    assert "CC BY 3.0" in html or "Attribution 3.0" in html
    assert "Lorc" in html and "Delapouite" in html
    assert "game-icons.net/1x1/lorc/lyre.html" in html
    assert "клас: чарівник" in html

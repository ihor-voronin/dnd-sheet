"""HTTP-експорт листа гравця: PDF і Markdown зі станом, а не з демо.

Персонаж створюється справжнім візардом і змінюється через `PATCH` — так
перевіряється весь шлях: стан → документ → рендер → байти.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dndsheet.api.app import create_app

DATA_DIR = Path(__file__).resolve().parent / "_tmp_export_api"


@pytest.fixture(scope="module")
def data_dir() -> Path:
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True)
    try:
        yield DATA_DIR
    finally:
        shutil.rmtree(DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="module")
def client(data_dir: Path) -> TestClient:
    previous = os.environ.get("DNDSHEET_DATA_DIR")
    os.environ["DNDSHEET_DATA_DIR"] = str(data_dir)
    try:
        app = create_app()
    finally:
        if previous is None:
            os.environ.pop("DNDSHEET_DATA_DIR", None)
        else:
            os.environ["DNDSHEET_DATA_DIR"] = previous
    return TestClient(app)


def _export_character(client: TestClient) -> str:
    """Воїн у бою: 5 з 12 хітів, кольчуга й довгий меч, нотатка."""
    draft = client.post("/api/v1/characters/wizard").json()
    draft_id = draft["draft"]["id"]
    steps = [
        ("species", {"name": "Дарія", "species_key": "human"}),
        ("class", {"class_key": "fighter"}),
        (
            "abilities",
            {
                "method": "standard_array",
                "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            },
        ),
        (
            "background",
            {
                "background_key": "soldier",
                "picks": [
                    {"kind": "skill", "value": "athletics", "source": {"kind": "class", "key": "fighter"}},
                    {"kind": "skill", "value": "perception", "source": {"kind": "class", "key": "fighter"}},
                ],
            },
        ),
        (
            "equipment",
            {
                "items": [
                    {"name_en": "chain mail", "kind": "armor", "armor_base": 16, "dex_cap": 0, "equipped": True},
                    {"name_en": "longsword", "kind": "weapon", "weight_lb": 3, "equipped": True},
                ],
                "money": {"gp": 10},
            },
        ),
    ]
    for step, body in steps:
        response = client.put(f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=body)
        assert response.status_code == 200, f"{step}: {response.text}"
    finished = client.post(f"/api/v1/characters/wizard/{draft_id}/finish")
    assert finished.status_code == 200, finished.text
    character_id = finished.json()["character_id"]

    patched = client.patch(
        f"/api/v1/characters/{character_id}",
        json={
            "hp": {"current": 5, "temporary": 2},
            "inspiration": True,
            "exhaustion": 1,
            "overrides": {"armor_class": 17},
            "notes": {"appearance": "шрам на щоці"},
        },
    )
    assert patched.status_code == 200, patched.text
    return character_id


def test_markdown_export_contains_the_state(client: TestClient) -> None:
    character_id = _export_character(client)
    response = client.get(f"/api/v1/characters/{character_id}/export/markdown")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]

    text = response.content.decode("utf-8")
    assert "Дарія" in text
    combat = text.split("## Бій", 1)[1]
    hp_line = next(line for line in combat.splitlines() if "Хіти: зараз" in line)
    assert hp_line.endswith("**: 5"), f"експорт показує стан, а не максимум: {hp_line}"
    assert "17" in text and "вручну" in text, "виправлений КЗ позначений"
    assert "Натхнення" in text
    assert "шрам на щоці" in text
    assert "longsword" in text
    assert "1d8+3 slashing" in text


def test_markdown_export_can_hide_originals(client: TestClient) -> None:
    character_id = _export_character(client)
    response = client.get(
        f"/api/v1/characters/{character_id}/export/markdown?originals=false"
    )
    text = response.content.decode("utf-8")
    assert "Strength" not in text
    assert "Сила" in text


def test_pdf_export_is_either_bytes_or_honest_503(client: TestClient) -> None:
    """Без WeasyPrint (Windows без GTK) — 503 із причиною, а не порожній файл."""
    character_id = _export_character(client)
    response = client.get(f"/api/v1/characters/{character_id}/export/pdf")

    if response.status_code == 503:
        assert "WeasyPrint" in response.json()["detail"]
    else:
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")


def test_unknown_format_is_404(client: TestClient) -> None:
    character_id = _export_character(client)
    response = client.get(f"/api/v1/characters/{character_id}/export/docx")
    assert response.status_code == 404
    assert "docx" in response.json()["detail"]


def test_unknown_character_is_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/characters/00000000-0000-0000-0000-000000000000/export/markdown"
    )
    assert response.status_code == 404


def test_demo_export_has_attacks_from_the_compendium(client: TestClient) -> None:
    """Демо теж іде через побудову документа — з атаками з довідника."""
    response = client.get("/api/v1/demo/export/markdown")
    assert response.status_code == 200, response.text
    text = response.content.decode("utf-8")
    assert "Елара Світлотінь" in text
    assert "Атаки" in text
    assert "shortsword" in text


def test_print_sheet_is_for_the_table(client: TestClient) -> None:
    """Аркуш для гри: усе потрібне за столом і жодних суцільних текстів правил."""
    character_id = _export_character(client)
    response = client.get(f"/api/v1/characters/{character_id}/print")
    assert response.status_code == 200
    html = response.text
    for label in ("рятівні кидки", "навички", "клас захисту", "атаки й заговори", "спорядження"):
        assert label in html
    assert "Атлетика" in html and "Спостережливість" in html
    assert "Уміння й особливості — пояснення" not in html
    # Шрифти вбудовані: аркуш однаково виглядає з диска, з сервера й у PDF.
    assert "data:font/woff2;base64," in html


def test_detailed_print_adds_explanations(client: TestClient) -> None:
    character_id = _export_character(client)
    html = client.get(f"/api/v1/characters/{character_id}/print", params={"detailed": "true"}).text
    assert "Уміння й особливості — пояснення" in html


def test_detailed_pdf_is_either_bytes_or_honest_503(client: TestClient) -> None:
    character_id = _export_character(client)
    response = client.get(f"/api/v1/characters/{character_id}/export/pdf", params={"detailed": "true"})
    if response.status_code == 503:
        assert "WeasyPrint" in response.json()["detail"]
    else:
        assert response.content.startswith(b"%PDF")
        assert "filename*=UTF-8''" in response.headers["content-disposition"]

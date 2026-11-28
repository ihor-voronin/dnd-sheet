"""HTTP-шар: здоровʼя, демо-документ, експорт."""

from __future__ import annotations

import jsonschema
import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_answers_head(client: TestClient) -> None:
    """Uptime checks (the README badge) send HEAD: a 404 there reads as "the site is down"."""
    assert client.head("/healthz").status_code == 200


def test_renderers_listed(client: TestClient) -> None:
    response = client.get("/api/v1/renderers")
    assert response.status_code == 200
    assert "markdown" in response.json()["formats"]
    assert "pdf" in response.json()["formats"]


def test_demo_sheet_matches_contract(client: TestClient, schema: dict) -> None:
    response = client.get("/api/v1/demo/sheet")
    assert response.status_code == 200
    jsonschema.validate(instance=response.json(), schema=schema)


def test_demo_sheet_has_bilingual_labels(client: TestClient) -> None:
    payload = client.get("/api/v1/demo/sheet").json()
    first_field = next(iter(payload["fields"].values()))
    assert first_field["label"]["uk"]
    assert first_field["label"]["en"], "оригінал англійською обовʼязковий для тултіпа"


def test_markdown_export(client: TestClient) -> None:
    response = client.get("/api/v1/demo/export/markdown")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Елара Світлотінь" in response.text


def test_unknown_format_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/demo/export/docx")
    assert response.status_code == 404


def test_robots_points_to_the_sitemap_and_hides_private_paths(client: TestClient) -> None:
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "User-agent: *" in text
    for path in ("/authorize", "/token", "/mcp", "/api/v1/shared/"):
        assert f"Disallow: {path}" in text
    # Довідник читається через API — його рендер пошуковиком не можна закривати.
    assert "Disallow: /api/v1/compendium" not in text
    assert "Sitemap: http://localhost:8000/sitemap.xml" in text


def test_sitemap_lists_the_site(client: TestClient) -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<loc>http://localhost:8000/</loc>" in response.text

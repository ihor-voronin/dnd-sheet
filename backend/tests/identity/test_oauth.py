"""Сайт як сервер авторизації для застосунків (ADR 0005): повний шлях і його захист.

Застосунок реєструється → гравець бачить екран згоди → код → токени → `/mcp`.
Окремо перевіряється те, що мусить не працювати: чужий PKCE, повтор коду, чужа
адреса повернення, токен для іншого ресурсу, повторне використання токена
оновлення, сесія сайту замість токена, новий акаунт з екрана згоди.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from dndsheet.api.app import create_app
from dndsheet.identity.application.auth import NO_ACCOUNT
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent / "_tmp_oauth"
BASE = "http://localhost:8000"
REDIRECT = "http://localhost:33418/callback"
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}


@pytest.fixture(scope="module", autouse=True)
def _cleanup() -> None:
    yield
    shutil.rmtree(ROOT, ignore_errors=True)


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> TestClient:
    data = ROOT / request.node.name
    shutil.rmtree(data, ignore_errors=True)
    data.mkdir(parents=True)
    monkeypatch.setenv("DNDSHEET_DATA_DIR", str(data))
    monkeypatch.setenv("DNDSHEET_AUTH", "on")
    monkeypatch.setenv("DNDSHEET_DEV_LOGIN", "1")
    monkeypatch.setenv("DNDSHEET_PUBLIC_URL", BASE)
    monkeypatch.delenv("DNDSHEET_OWNER_TELEGRAM_ID", raising=False)
    with TestClient(create_app(), base_url=BASE) as client:
        yield client


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def _register(site: TestClient, **extra: object) -> str:
    response = site.post(
        "/register",
        json={
            "redirect_uris": [REDIRECT],
            "client_name": "Тестовий асистент",
            "token_endpoint_auth_method": "none",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


def _authorize(site: TestClient, client_id: str, challenge: str, **extra: str) -> str:
    """`/authorize` → id запиту на екрані згоди."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "st-1",
        "resource": f"{BASE}/mcp",
        **extra,
    }
    response = site.get("/authorize", params=params, follow_redirects=False)
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    assert location.startswith(f"{BASE}/#/oauth/"), location
    return location.rsplit("/", 1)[-1]


def _login(site: TestClient, name: str = "Ігор") -> None:
    assert site.post("/api/v1/auth/dev", json={"name": name}).status_code == 200


def _consent(site: TestClient, request_id: str, approve: bool = True) -> dict[str, list[str]]:
    response = site.post(f"/api/v1/oauth/requests/{request_id}", json={"approve": approve})
    assert response.status_code == 200, response.text
    redirect = response.json()["redirect"]
    assert redirect.startswith(REDIRECT)
    return parse_qs(urlsplit(redirect).query)


def _tokens(site: TestClient, client_id: str, code: str, verifier: str) -> dict:
    response = site.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
            "resource": f"{BASE}/mcp",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _connect(site: TestClient) -> tuple[str, dict]:
    """Повний шлях підключення: застосунок і його токени."""
    _login(site)
    client_id = _register(site)
    verifier, challenge = _pkce()
    query = _consent(site, _authorize(site, client_id, challenge))
    return client_id, _tokens(site, client_id, query["code"][0], verifier)


def _mcp(site: TestClient, token: str | None, method: str = "tools/call", params: dict | None = None):  # noqa: ANN202
    headers = dict(MCP_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # Окремий клієнт без cookie: MCP не має бачити сесію сайту.
    bare = TestClient(site.app, base_url=BASE)
    return bare.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {"name": "list_characters", "arguments": {}},
        },
    )


# --- метадані -----------------------------------------------------------------


def test_metadata_describes_both_servers(site: TestClient) -> None:
    resource = site.get("/.well-known/oauth-protected-resource/mcp").json()
    assert site.get("/.well-known/oauth-protected-resource").json() == resource
    assert resource["resource"] == f"{BASE}/mcp"
    assert resource["authorization_servers"] == [BASE]
    assert resource["scopes_supported"] == ["characters"]

    server = site.get("/.well-known/oauth-authorization-server").json()
    assert server["issuer"] == BASE
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert server["client_id_metadata_document_supported"] is True
    assert "none" in server["token_endpoint_auth_methods_supported"]
    assert server["registration_endpoint"] == f"{BASE}/register"


def test_mcp_without_token_points_to_metadata(site: TestClient) -> None:
    response = _mcp(site, None)
    assert response.status_code == 401
    assert (
        'resource_metadata="http://localhost:8000/.well-known/oauth-protected-resource/mcp"'
        in (response.headers["www-authenticate"])
    )


# --- повний шлях --------------------------------------------------------------


def test_full_flow_gives_tools_of_the_player(site: TestClient) -> None:
    client_id, tokens = _connect(site)
    assert tokens["token_type"] == "Bearer"
    assert tokens["scope"] == "characters"
    assert tokens["expires_in"] == 3600

    response = _mcp(site, tokens["access_token"])
    assert response.status_code == 200, response.text
    assert response.json()["result"]["structuredContent"] == {"items": [], "total": 0, "limit": 50, "draft_id": None}

    grants = site.get("/api/v1/oauth/grants").json()["items"]
    assert [(grant["client_id"], grant["name"]) for grant in grants] == [(client_id, "Тестовий асистент")]


def test_consent_screen_names_client_and_redirect_host(site: TestClient) -> None:
    client_id = _register(site)
    request_id = _authorize(site, client_id, _pkce()[1])
    shown = site.get(f"/api/v1/oauth/requests/{request_id}").json()
    assert shown["client"]["name"] == "Тестовий асистент"
    assert shown["client"]["local_only"] is True
    assert shown["redirect_host"] == "localhost"
    assert [scope["key"] for scope in shown["scopes"]] == ["characters"]
    assert shown["signed_in"] is False


def test_denied_consent_returns_access_denied(site: TestClient) -> None:
    _login(site)
    client_id = _register(site)
    query = _consent(site, _authorize(site, client_id, _pkce()[1]), approve=False)
    assert query["error"] == ["access_denied"]
    assert query["state"] == ["st-1"]
    assert query["iss"] == [BASE]


def test_consent_needs_a_signed_in_player(site: TestClient) -> None:
    client_id = _register(site)
    request_id = _authorize(site, client_id, _pkce()[1])
    assert site.post(f"/api/v1/oauth/requests/{request_id}", json={"approve": True}).status_code == 401


def test_consent_screen_does_not_create_accounts(site: TestClient) -> None:
    refused = site.post("/api/v1/auth/dev?existing_only=1", json={"name": "Новенький"})
    assert refused.status_code == 422
    assert refused.json()["detail"] == NO_ACCOUNT
    _login(site, "Старий")
    site.post("/api/v1/auth/logout")
    assert site.post("/api/v1/auth/dev?existing_only=1", json={"name": "Старий"}).status_code == 200


def test_consent_decision_is_json_only(site: TestClient) -> None:
    _login(site)
    client_id = _register(site)
    request_id = _authorize(site, client_id, _pkce()[1])
    response = site.post(f"/api/v1/oauth/requests/{request_id}", data={"approve": "true"})
    assert response.status_code in {415, 422}


# --- що мусить не працювати ---------------------------------------------------


def test_wrong_pkce_verifier_is_refused(site: TestClient) -> None:
    _login(site)
    client_id = _register(site)
    query = _consent(site, _authorize(site, client_id, _pkce()[1]))
    response = site.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": _pkce()[0],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


def test_code_works_once(site: TestClient) -> None:
    _login(site)
    client_id = _register(site)
    verifier, challenge = _pkce()
    code = _consent(site, _authorize(site, client_id, challenge))["code"][0]
    _tokens(site, client_id, code, verifier)
    again = site.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert again.status_code == 400
    assert again.json()["error"] == "invalid_grant"


def test_unregistered_redirect_is_not_followed(site: TestClient) -> None:
    client_id = _register(site)
    response = site.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://evil.example/callback",
            "code_challenge": _pkce()[1],
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "evil.example" not in response.headers.get("location", "")


def test_registration_accepts_only_https_or_localhost(site: TestClient) -> None:
    response = site.post("/register", json={"redirect_uris": ["http://evil.example/cb"]})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


def test_token_for_another_resource_is_not_issued(site: TestClient) -> None:
    client_id = _register(site)
    response = site.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "code_challenge": _pkce()[1],
            "code_challenge_method": "S256",
            "state": "s",
            "resource": "https://other.example/mcp",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "error=invalid_target" in response.headers["location"]


def test_site_session_is_not_an_mcp_token(site: TestClient) -> None:
    _login(site)
    session = site.cookies.get("dndsheet_session")
    assert session
    assert _mcp(site, session).status_code == 401


def test_refresh_rotates_and_reuse_revokes_everything(site: TestClient) -> None:
    client_id, tokens = _connect(site)

    def refresh(token: str):  # noqa: ANN202
        return site.post(
            "/token", data={"grant_type": "refresh_token", "refresh_token": token, "client_id": client_id}
        )

    fresh = refresh(tokens["refresh_token"])
    assert fresh.status_code == 200, fresh.text
    rotated = fresh.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]
    assert _mcp(site, rotated["access_token"]).status_code == 200

    # Старий токен оновлення вдруге — ознака крадіжки: відкликається вся згода.
    assert refresh(tokens["refresh_token"]).status_code == 400
    assert _mcp(site, rotated["access_token"]).status_code == 401
    assert refresh(rotated["refresh_token"]).status_code == 400


def test_revocation_endpoint_and_disconnect(site: TestClient) -> None:
    client_id, tokens = _connect(site)
    # SDK вимагає поле client_secret навіть від публічного клієнта (порожнє).
    revoked = site.post("/revoke", data={"token": tokens["access_token"], "client_id": client_id, "client_secret": ""})
    assert revoked.status_code == 200
    assert _mcp(site, tokens["access_token"]).status_code == 401

    client_id, tokens = _connect(site)
    response = site.delete("/api/v1/oauth/grants", params={"client_id": client_id})
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert _mcp(site, tokens["access_token"]).status_code == 401
    assert site.delete("/api/v1/oauth/grants", params={"client_id": client_id}).status_code == 404


def test_tokens_see_only_their_players_characters(site: TestClient) -> None:
    from test_auth import _create  # noqa: PLC0415 — той самий візард, що в тестах входу

    _login(site, "Інша")
    foreign = _create(site)
    site.post("/api/v1/auth/logout")
    _, tokens = _connect(site)
    response = _mcp(
        site, tokens["access_token"], params={"name": "get_character", "arguments": {"character_id": foreign}}
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert "немає персонажа" in result["content"][0]["text"]


def test_expired_request_is_reported(site: TestClient) -> None:
    assert site.get("/api/v1/oauth/requests/nope").status_code == 404
    _login(site)
    assert site.post("/api/v1/oauth/requests/nope", json={"approve": True}).status_code == 404

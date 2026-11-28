"""Застосунки OAuth: опис за адресою (CIMD), його обмеження (SSRF), реєстрація, крайні випадки токенів."""

from __future__ import annotations

import asyncio
import io
import json
import shutil
import socket
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from dndsheet.identity.api import oauth_provider
from dndsheet.identity.api.oauth_provider import SiteOAuthProvider, client_summary, redirect_allowed
from dndsheet.identity.application.oauth import OAuthService, canonical, with_query
from dndsheet.identity.domain.oauth import ACCESS_TTL, CODE_TTL, REFRESH_TTL
from dndsheet.identity.domain.user import User
from dndsheet.identity.infrastructure import client_metadata
from dndsheet.identity.infrastructure.client_metadata import MetadataError, check_url, fetch_client_metadata
from dndsheet.identity.infrastructure.sqlite_oauth import SqliteOAuthStore
from dndsheet.shared.errors import NotFoundError, ValidationError
from mcp.server.auth.provider import AuthorizationParams, AuthorizeError, RegistrationError, TokenError
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

ROOT = Path(__file__).resolve().parent / "_tmp_oauth_clients"
CLIENT_URL = "https://claude.example/oauth/client.json"
RESOURCE = "https://dnd.example/mcp"
PLAYER = User(id="u1", telegram_id=1, first_name="Ігор")


@pytest.fixture(scope="module", autouse=True)
def _cleanup() -> None:
    yield
    shutil.rmtree(ROOT, ignore_errors=True)


@pytest.fixture
def store(request: pytest.FixtureRequest) -> SqliteOAuthStore:
    path = ROOT / f"{request.node.name}.sqlite3"
    path.unlink(missing_ok=True)
    return SqliteOAuthStore(path)


@pytest.fixture
def service(store: SqliteOAuthStore) -> OAuthService:
    return OAuthService(store=store, issuer="https://dnd.example", resource=RESOURCE)


def _provider(service: OAuthService, store: SqliteOAuthStore, fetch: Any = None) -> SiteOAuthProvider:  # noqa: ANN401
    def missing(url: str) -> dict:
        raise MetadataError("немає")

    return SiteOAuthProvider(
        service=service, store=store, consent_url="https://dnd.example/#/oauth/", fetch_metadata=fetch or missing
    )


def _document(**extra: Any) -> dict:  # noqa: ANN401
    return {"client_id": CLIENT_URL, "client_name": "Claude", "redirect_uris": ["https://claude.example/cb"], **extra}


# --- адреса опису ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://claude.example/client.json",
        "https://user:pw@claude.example/client.json",
        "https://claude.example:8443/client.json",
        "https://claude.example/",
        "https://claude.example/client.json#x",
        "https:///client.json",
    ],
)
def test_bad_metadata_urls_are_refused(url: str) -> None:
    with pytest.raises(MetadataError):
        check_url(url)


def test_good_metadata_url_gives_host() -> None:
    assert check_url(CLIENT_URL) == "claude.example"


def _addresses(*ips: str):  # noqa: ANN202
    def resolve(host: str, port: int, **kwargs: Any) -> list:  # noqa: ANN401
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]

    return resolve


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "192.168.0.5", "169.254.169.254", "::1"])
def test_private_addresses_are_refused(monkeypatch: pytest.MonkeyPatch, ip: str) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _addresses("93.184.216.34", ip))
    with pytest.raises(MetadataError, match="непублічну"):
        client_metadata.check_public("claude.example")


def test_unknown_host_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> list:  # noqa: ANN401
        raise OSError("nope")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(MetadataError, match="не знайдено"):
        client_metadata.check_public("claude.example")


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _serve(monkeypatch: pytest.MonkeyPatch, body: bytes | Exception) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _addresses("93.184.216.34"))

    class Opener:
        def open(self, request: urllib.request.Request, timeout: float) -> _Response:
            assert timeout == client_metadata.TIMEOUT
            if isinstance(body, Exception):
                raise body
            return _Response(body)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())


def test_metadata_is_fetched_as_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, json.dumps(_document()).encode())
    assert fetch_client_metadata(CLIENT_URL)["client_name"] == "Claude"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"x" * (client_metadata.MAX_BYTES + 1), "завеликий"),
        (b"<html>", "не JSON"),
        (b"[1, 2]", "обʼєктом"),
        (OSError("timeout"), "не вдалося"),
        (MetadataError("переадресації не дозволені"), "переадресації"),
    ],
)
def test_bad_metadata_is_refused(monkeypatch: pytest.MonkeyPatch, body: bytes | Exception, message: str) -> None:
    _serve(monkeypatch, body)
    with pytest.raises(MetadataError, match=message):
        fetch_client_metadata(CLIENT_URL)


def test_redirects_are_not_followed() -> None:
    with pytest.raises(MetadataError):
        client_metadata._NoRedirects().redirect_request()


# --- застосунок за адресою ------------------------------------------------------


def test_url_client_is_fetched_once_and_cached(service: OAuthService, store: SqliteOAuthStore) -> None:
    calls: list[str] = []

    def fetch(url: str) -> dict:
        calls.append(url)
        return _document(client_uri="https://claude.example")

    provider = _provider(service, store, fetch)
    client = asyncio.run(provider.get_client(CLIENT_URL))
    assert client is not None
    assert client.client_name == "Claude"
    assert client.token_endpoint_auth_method == "none"
    assert client.scope == "characters"
    assert asyncio.run(provider.get_client(CLIENT_URL)) is not None
    assert calls == [CLIENT_URL]
    summary = client_summary(client)
    assert summary["verified_by_url"] is True
    assert summary["local_only"] is False
    assert summary["redirect_hosts"] == ["claude.example"]


@pytest.mark.parametrize(
    "document",
    [
        _document(client_id="https://other.example/client.json"),
        _document(redirect_uris=[]),
        _document(redirect_uris=["http://evil.example/cb"]),
        _document(client_uri="not a url"),
    ],
)
def test_unfit_url_client_is_unknown(service: OAuthService, store: SqliteOAuthStore, document: dict) -> None:
    provider = _provider(service, store, lambda url: document)
    assert asyncio.run(provider.get_client(CLIENT_URL)) is None


def test_unreachable_url_client_is_unknown(service: OAuthService, store: SqliteOAuthStore) -> None:
    assert asyncio.run(_provider(service, store).get_client(CLIENT_URL)) is None
    assert asyncio.run(_provider(service, store).get_client("never-registered")) is None


@pytest.mark.parametrize(
    ("uri", "allowed"),
    [
        ("https://claude.ai/api/mcp/auth_callback", True),
        ("http://localhost:33418/cb", True),
        ("http://127.0.0.1/cb", True),
        ("http://claude.ai/cb", False),
        ("https://claude.ai/cb#frag", False),
        ("myapp://cb", False),
    ],
)
def test_redirect_rules(uri: str, allowed: bool) -> None:
    assert redirect_allowed(uri) is allowed


def test_registrations_are_limited(
    service: OAuthService, store: SqliteOAuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(oauth_provider, "REGISTER_LIMIT", 2)
    provider = _provider(service, store)

    def info(n: int) -> OAuthClientInformationFull:
        return OAuthClientInformationFull(client_id=f"c{n}", redirect_uris=[AnyUrl("http://localhost/cb")])

    asyncio.run(provider.register_client(info(1)))
    asyncio.run(provider.register_client(info(2)))
    with pytest.raises(RegistrationError, match="забагато"):
        asyncio.run(provider.register_client(info(3)))
    assert asyncio.run(provider.get_client("c1")).scope == "characters"


def test_authorize_rejects_unknown_scope(service: OAuthService, store: SqliteOAuthStore) -> None:
    provider = _provider(service, store)
    client = OAuthClientInformationFull(client_id="c", redirect_uris=[AnyUrl("http://localhost/cb")])
    params = AuthorizationParams(
        state=None,
        scopes=["admin"],
        code_challenge="x" * 43,
        redirect_uri=AnyUrl("http://localhost/cb"),
        redirect_uri_provided_explicitly=True,
    )
    with pytest.raises(AuthorizeError) as caught:
        asyncio.run(provider.authorize(client, params))
    assert caught.value.error == "invalid_scope"


# --- сервіс: терміни й крайні випадки -------------------------------------------


def _code(service: OAuthService, now: float = 1000.0) -> str:
    pending = service.start(
        client_id="c",
        redirect_uri="http://localhost/cb?keep=1",
        redirect_uri_explicit=True,
        scopes=None,
        code_challenge="x" * 43,
        state="s",
        resource=RESOURCE + "/",
        now=now,
    )
    redirect = service.decide(pending.id, PLAYER, True, now=now)
    assert "keep=1" in redirect
    return redirect.split("code=")[1].split("&")[0]


def test_code_expires(service: OAuthService) -> None:
    code = _code(service)
    with pytest.raises(ValidationError, match="застарів"):
        service.exchange_code(code, "c", now=1000.0 + CODE_TTL + 1)


def test_code_is_bound_to_its_client(service: OAuthService) -> None:
    code = _code(service)
    with pytest.raises(ValidationError):
        service.exchange_code(code, "other", now=1001.0)


def test_tokens_expire(service: OAuthService) -> None:
    pair = service.exchange_code(_code(service), "c", now=1001.0)
    assert service.access(pair.access_token, now=1001.0 + ACCESS_TTL - 1) is not None
    assert service.access(pair.access_token, now=1001.0 + ACCESS_TTL + 1) is None
    assert service.access(pair.refresh_token, now=1002.0) is None
    assert service.refresh_token(pair.refresh_token, "c", now=1001.0 + REFRESH_TTL + 1) is None
    assert service.refresh_token(pair.access_token, "c", now=1002.0) is None
    assert service.refresh_token(pair.refresh_token, "other", now=1002.0) is None


def test_rotation_narrows_scopes_and_rejects_bad_tokens(service: OAuthService) -> None:
    pair = service.exchange_code(_code(service), "c", now=1001.0)
    rotated = service.rotate(pair.refresh_token, "c", ("characters", "admin"), now=1002.0)
    assert rotated.scopes == ("characters",)
    with pytest.raises(ValidationError):
        service.rotate("nope", "c", ("characters",), now=1003.0)


def test_requests_and_resources_are_checked(service: OAuthService) -> None:
    with pytest.raises(ValidationError, match="лише для"):
        service.start(
            client_id="c",
            redirect_uri="http://localhost/cb",
            redirect_uri_explicit=True,
            scopes=None,
            code_challenge="x" * 43,
            state=None,
            resource="https://other.example/mcp",
        )
    with pytest.raises(NotFoundError):
        service.pending("nope")
    with pytest.raises(NotFoundError):
        service.decide("nope", PLAYER, True)
    with pytest.raises(NotFoundError):
        service.disconnect(PLAYER, "nobody")
    service.revoke("unknown token")


def test_helpers() -> None:
    assert canonical("HTTPS://Dnd.Example/mcp/") == "https://dnd.example/mcp"
    assert with_query("https://a.example/cb?x=1", code="c", state=None) == "https://a.example/cb?x=1&code=c"


def test_provider_token_errors(service: OAuthService, store: SqliteOAuthStore) -> None:
    provider = _provider(service, store)
    client = OAuthClientInformationFull(client_id="c", redirect_uris=[AnyUrl("http://localhost/cb")])
    code = _code(service, now=time.time())
    loaded = asyncio.run(provider.load_authorization_code(client, code))
    assert loaded is not None and loaded.subject == PLAYER.id
    other = OAuthClientInformationFull(client_id="other", redirect_uris=[AnyUrl("http://localhost/cb")])
    assert asyncio.run(provider.load_authorization_code(other, code)) is None
    asyncio.run(provider.exchange_authorization_code(client, loaded))
    with pytest.raises(TokenError):
        asyncio.run(provider.exchange_authorization_code(client, loaded))
    assert asyncio.run(provider.load_refresh_token(client, "nope")) is None
    assert asyncio.run(provider.load_access_token("nope")) is None

"""Опис застосунку за адресою (Client ID Metadata Document, MCP 2026-07-28).

Застосунок називає себе адресою (`client_id = https://…/client.json`), сервер
авторизації сам завантажує опис за нею. Це запит із нашого сервера на адресу,
яку дав хтось ззовні, тож обмеження жорсткі (захист від SSRF):

* лише https і лише стандартний порт, з шляхом, без логіна в адресі;
* хост має резолвитися тільки в публічні адреси (не localhost, не приватні мережі);
* без переадресацій, 5 секунд на все, не більше 64 КБ, лише JSON-обʼєкт.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.request
from typing import Any
from urllib.parse import urlsplit

TIMEOUT = 5.0
MAX_BYTES = 64 * 1024


class MetadataError(Exception):
    """Опис застосунку не вдалося отримати чи він не годиться."""


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401 — підпис базового класу
        raise MetadataError("переадресації не дозволені")


def check_url(url: str) -> str:
    """Перевірити адресу опису; повертає хост. Інакше `MetadataError`."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise MetadataError("адреса опису має бути https")
    if parts.username or parts.password:
        raise MetadataError("адреса опису без логіна й пароля")
    if parts.port not in (None, 443):
        raise MetadataError("адреса опису — лише на стандартному порту")
    if not parts.path or parts.path == "/":
        raise MetadataError("адреса опису має містити шлях")
    if parts.fragment:
        raise MetadataError("адреса опису без #фрагмента")
    if not parts.hostname:
        raise MetadataError("в адресі опису немає хоста")
    return parts.hostname


def check_public(host: str) -> None:
    """Хост резолвиться лише в публічні адреси."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise MetadataError(f"хост {host} не знайдено") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise MetadataError(f"хост {host} веде в непублічну мережу")


def fetch_client_metadata(url: str) -> dict[str, Any]:
    """Завантажити й розібрати опис застосунку."""
    check_public(check_url(url))
    opener = urllib.request.build_opener(_NoRedirects())
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "dndsheet-oauth"})
    try:
        with opener.open(request, timeout=TIMEOUT) as response:  # noqa: S310 — схему перевірено вище
            body = response.read(MAX_BYTES + 1)
    except MetadataError:
        raise
    except Exception as exc:  # мережа, TLS, HTTP-помилки — усе це «опису немає»
        raise MetadataError(f"не вдалося завантажити опис застосунку: {exc}") from exc
    if len(body) > MAX_BYTES:
        raise MetadataError("опис застосунку завеликий")
    try:
        document = json.loads(body)
    except ValueError as exc:
        raise MetadataError("опис застосунку — не JSON") from exc
    if not isinstance(document, dict):
        raise MetadataError("опис застосунку має бути JSON-обʼєктом")
    return document

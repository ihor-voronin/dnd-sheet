"""Виклик HTTP API сайту зсередини процесу — від імені власника токена.

Інструменти MCP не переписують правила й перевірки: вони звертаються до тих
самих обробників, що й SPA (валідація, «чужий персонаж — як відсутній»,
коди помилок). Мережі тут немає: запит іде прямо в ASGI-застосунок.

Хто робить запит — у `scope["state"]["user"]`: ззовні цей ключ поставити
неможливо (його заповнює лише сервер), а `current_user` бере саме його, тож
токени MCP не стають сесіями сайту і навпаки.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import anyio
from starlette.types import ASGIApp, Message

from dndsheet.identity.domain.user import User


@dataclass(frozen=True, slots=True)
class Reply:
    status: int
    body: Any  # noqa: ANN401 — JSON або сирі байти
    headers: dict[str, str]

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def detail(self) -> str:
        if isinstance(self.body, dict) and self.body.get("detail"):
            return str(self.body["detail"])
        return f"статус {self.status}"


def segment(value: str) -> str:
    """Частина шляху: id персонажа не може вийти за свій сегмент."""
    return quote(value, safe="")


async def call(
    app: ASGIApp,
    user: User,
    method: str,
    path: str,
    *,
    body: Any = None,  # noqa: ANN401
    query: dict[str, Any] | None = None,
) -> Reply:
    payload = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": urlencode(query or {}, doseq=True).encode("utf-8"),
        "root_path": "",
        "headers": [
            (b"host", b"mcp.internal"),
            (b"accept", b"application/json"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode("ascii")),
        ],
        "client": ("mcp", 0),
        "server": ("mcp.internal", 80),
        "state": {"user": user},
    }
    status = 500
    headers: dict[str, str] = {}
    chunks: list[bytes] = []
    finished = anyio.Event()
    delivered = False

    async def receive() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": payload, "more_body": False}
        await finished.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = int(message["status"])
            headers.update({key.decode("latin-1"): value.decode("latin-1") for key, value in message["headers"]})
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))
            if not message.get("more_body"):
                finished.set()

    await app(scope, receive, send)
    finished.set()
    raw = b"".join(chunks)
    if headers.get("content-type", "").startswith("application/json"):
        return Reply(status=status, body=json.loads(raw or b"null"), headers=headers)
    return Reply(status=status, body=raw, headers=headers)

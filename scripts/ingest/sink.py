"""Локальний приймач HTML від браузера.

Навіщо: куплені книги D&D Beyond віддаються лише з авторизованою сесією, а
сесія живе в браузері. Замість того щоб витягати cookies на диск і повторювати
вхід із httpx (це і є кукі-файл, і зайвий ризик витоку), сторінки завантажує
сам браузер — тим самим сеансом, яким користувач уже увійшов — і надсилає HTML
сюди. Приймач пише його у той самий content/raw/<source>/, що й httpx-шлях,
тож етапи parse/records далі працюють без змін.

Запуск (окремий процес, слухає лише 127.0.0.1):

    python -m scripts.ingest.sink --port 8765

Протокол (усе з тілом як text/plain, щоб не було preflight):

    GET  /health
    POST /index?source=<id>          тіло: {"pages": ["sources/phb/races", ...]}
    POST /page?source=<id>&rel=<rel> тіло: HTML сторінки

Чому не можна просто fetch із сторінки DDB до localhost: Chrome вимагає для
запитів із публічного origin у приватну мережу (Private Network Access)
заголовок Access-Control-Allow-Private-Network — його віддає цей сервер.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, discover, fetch


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pages = 0
        self.indexes = 0

    def bump(self, kind: str) -> None:
        with self.lock:
            if kind == "page":
                self.pages += 1
            else:
                self.indexes += 1


STATE = _State()


def _known_sources() -> set[str]:
    return set(records_ids())


def records_ids() -> list[str]:
    import yaml

    raw = yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))
    return [entry["id"] for entry in raw.get("sources", [])]


class Handler(BaseHTTPRequestHandler):
    server_version = "ddbsink/1"

    def log_message(self, fmt: str, *args) -> None:  # тихіше в stdout
        pass

    # --- допоміжне ---
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        # Chrome Private Network Access: без цього публічна сторінка не дістане
        # до 127.0.0.1.
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _ok(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _fail(self, code: int, message: str) -> None:
        data = json.dumps({"ok": False, "error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _query(self) -> tuple[str, dict[str, list[str]]]:
        parsed = urllib.parse.urlparse(self.path)
        return parsed.path, urllib.parse.parse_qs(parsed.query)

    # --- маршрути ---
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path, query = self._query()
        if path == "/health":
            self._ok({"ok": True, "pages": STATE.pages, "indexes": STATE.indexes})
            return
        if path == "/index":
            source = (query.get("source") or [""])[0]
            if source not in _known_sources():
                self._fail(400, f"невідоме джерело: {source!r}")
                return
            self._get_index(source)
            return
        if path == "/todo":
            source = (query.get("source") or [""])[0]
            if source not in _known_sources():
                self._fail(400, f"невідоме джерело: {source!r}")
                return
            self._get_todo(source)
            return
        self._fail(404, "невідомий шлях")

    def _get_index(self, source: str) -> None:
        try:
            pages = discover.load_index(source)
        except FileNotFoundError as exc:
            self._fail(404, str(exc))
            return
        self._ok({"ok": True, "source": source, "pages": pages})

    def _get_todo(self, source: str) -> None:
        """Сторінки індексу, яких ще немає на диску (для докачки після обриву)."""
        try:
            pages = discover.load_index(source)
        except FileNotFoundError as exc:
            self._fail(404, str(exc))
            return
        done = set(fetch.load_checkpoint(source).get("done") or [])
        todo = [page for page in pages if page not in done]
        self._ok({"ok": True, "source": source, "todo": todo, "done": len(done)})

    def do_POST(self) -> None:
        path, query = self._query()
        if path == "/quit":
            # Штатна зупинка: інакше на Windows при allow_reuse_address старий
            # приймач лишається жити й перехоплює частину запитів.
            self._ok({"ok": True, "bye": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        source = (query.get("source") or [""])[0]
        if source not in _known_sources():
            self._fail(400, f"невідоме джерело: {source!r}")
            return

        body = self._body()
        if path == "/index":
            self._save_index(source, body)
        elif path == "/discover":
            self._discover(source, body)
        elif path == "/page":
            self._save_page(source, (query.get("rel") or [""])[0], body)
        else:
            self._fail(404, "невідомий шлях")

    # --- обробники ---
    def _discover(self, source: str, body: bytes) -> None:
        """Корінь книги від браузера -> індекс сторінок (розбір робить Python)."""
        html = body.decode("utf-8", errors="replace")
        pages = discover.pages_from_toc(html, source)
        if not pages:
            self._ok(
                {
                    "ok": True,
                    "via": "none",
                    "pages": [],
                    "hint": "у корені немає блоку змісту — потрібен обхід у ширину",
                    "diag": {
                        "htmlLen": len(html),
                        "hasClass": discover.TOC_CLASS in html,
                        "divsWithClass": sum(
                            1 for tag in discover._DIV_OPEN_RE.finditer(html) if discover.TOC_CLASS in tag.group(0)
                        ),
                        "tocRels": len(discover.toc_rels(html)),
                        "marker": "p-article" if "p-article" in html else None,
                    },
                }
            )
            return
        target = discover.save_index(source, pages)
        print(f"  discover {source}: {len(pages)} → {target.name}", flush=True)
        self._ok({"ok": True, "via": "toc", "pages": pages, "count": len(pages)})

    def _save_index(self, source: str, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._fail(400, f"не JSON: {exc}")
            return
        pages = payload.get("pages") if isinstance(payload, dict) else payload
        if not isinstance(pages, list):
            self._fail(400, "очікувався список сторінок")
            return
        cleaned: list[str] = []
        for page in pages:
            rel = discover.normalize(str(page))
            if rel and not discover.tail_of(rel):
                continue  # корінь книги у списку не потрібен
            if rel and rel not in cleaned:
                cleaned.append(rel)
        target = discover.save_index(source, cleaned)
        STATE.bump("index")
        print(f"  index {source}: {len(cleaned)} → {target.name}", flush=True)
        self._ok({"ok": True, "saved": len(cleaned)})

    def _save_page(self, source: str, rel: str, body: bytes) -> None:
        rel = discover.normalize(rel)
        if not rel:
            self._fail(400, f"не схоже на сторінку книги: {rel!r}")
            return
        html = body.decode("utf-8", errors="replace")
        lowered = html.lower()
        from .session import CONTENT_MARKERS, looks_like_not_found

        if looks_like_not_found(html):
            # Сторінка-заглушка DDB теж містить «compendium-content» у скриптах,
            # тому перевіряємо її окремо, інакше в корпус потрапляє порожня 404.
            self._fail(404, "сторінки не існує (заглушка D&D Beyond)")
            return
        if not any(marker in lowered for marker in CONTENT_MARKERS):
            self._fail(422, "у відповіді немає тіла статті")
            return

        target = fetch.raw_path(source, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")

        state = fetch.load_checkpoint(source)
        done = set(state.get("done") or [])
        done.add(rel)
        state["done"] = sorted(done)
        state["challenge"] = False
        fetch.save_checkpoint(source, state)

        STATE.bump("page")
        print(f"  page {rel} ({len(html)} B)", flush=True)
        self._ok({"ok": True, "rel": rel, "bytes": len(html)})


class _Server(ThreadingHTTPServer):
    # На Windows SO_REUSEADDR дозволяє ДВОМ процесам сісти на один порт, і
    # запити розподіляються між ними випадково: старий приймач перехоплює
    # частину запитів і відповідає своїм набором маршрутів. Тому забороняємо.
    allow_reuse_address = False
    daemon_threads = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.ingest.sink")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    try:
        server = _Server(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        print(
            f"Не вдалося зайняти порт {args.port}: {exc}\n"
            f"Уже працює інший приймач — зупини його (netstat -ano | findstr :{args.port})",
            file=sys.stderr,
            flush=True,
        )
        return 1

    print(f"sink слухає http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("sink зупинено", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

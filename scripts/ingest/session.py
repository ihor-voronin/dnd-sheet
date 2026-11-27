"""HTTP-сесія до D&D Beyond: cookies, тротлінг, розпізнавання CAPTCHA."""

from __future__ import annotations

import json
import pathlib
import random
import time
from typing import Never

import httpx

from . import config

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Ознаки того, що сервер віддав справжню сторінку книги, а не заглушку.
# Перевіряти треба саме наявність контенту: тег(и) reCAPTCHA стоять на кожній
# сторінці DDB (це лише лоадер скрипта), тому за ними CAPTCHA не визначити.
CONTENT_MARKERS = (
    "p-article",
    "compendium-toc-full",
    "article-content",
    "compendium-content",
)

# Використовується лише для формулювання причини, коли контенту немає.
BLOCK_MARKERS = (
    "just a moment",
    "cf-challenge",
    "challenge-platform",
    "access denied",
    "are you a robot",
)

# Сторінка-заглушка «Not found - D&D Beyond». Вона теж містить
# «compendium-content» (у скриптах), тому сама по собі наявність маркера
# контенту ще не означає, що сторінка справжня.
NOT_FOUND_MARKERS = ("not found - d&d beyond", "page not found")


def looks_like_not_found(body: str) -> bool:
    lowered = body.lower()
    return any(marker in lowered for marker in NOT_FOUND_MARKERS)


class ChallengeError(RuntimeError):
    """Сервер вимагає ручної верифікації — конвеєр має зупинитися."""


class SessionError(RuntimeError):
    pass


def load_cookie_header(path: pathlib.Path = config.COOKIE_FILE) -> str:
    """Будує заголовок Cookie з експорту браузера (список обʼєктів name/value/domain)."""
    if not path.exists():
        raise SessionError(f"Немає файлу сесії {path}. Експортуй cookies браузера у цей файл.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("cookies", [])
    pairs = []
    for cookie in data:
        name = cookie.get("name")
        value = cookie.get("value")
        domain = (cookie.get("domain") or "dndbeyond.com").lstrip(".")
        if not name or value is None:
            continue
        if "dndbeyond.com" not in domain:
            continue
        pairs.append(f"{name}={value}")
    if not pairs:
        raise SessionError("У файлі сесії немає cookies для dndbeyond.com")
    return "; ".join(pairs)


class Fetcher:
    def __init__(
        self,
        cookie_file: pathlib.Path = config.COOKIE_FILE,
        delay: float = config.DEFAULT_DELAY,
        jitter: float = config.DEFAULT_JITTER,
        anonymous: bool = False,
    ) -> None:
        self.delay = delay
        self.jitter = jitter
        self.anonymous = anonymous
        self._last_at = 0.0
        self.requests_made = 0
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if not anonymous:
            headers["Cookie"] = load_cookie_header(cookie_file)
            self.has_cookies = True
        else:
            self.has_cookies = False
        self.client = httpx.Client(follow_redirects=True, timeout=config.TIMEOUT, headers=headers)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _throttle(self) -> None:
        wait = self.delay + random.uniform(0, self.jitter)
        elapsed = time.monotonic() - self._last_at
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_at = time.monotonic()

    def get(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(config.MAX_RETRIES):
            self._throttle()
            try:
                response = self.client.get(url)
            except httpx.HTTPError as exc:  # мережа
                last_error = exc
                time.sleep(2**attempt)
                continue

            self.requests_made += 1
            if response.status_code in (429, 502, 503, 504):
                last_error = SessionError(f"HTTP {response.status_code} на {url}")
                time.sleep(min(60, 4 * 2**attempt))
                continue
            if response.status_code in (401, 403):
                raise ChallengeError(f"HTTP {response.status_code} — сесія недійсна або закінчилась ({url})")

            # DDB віддає UTF-8, але без явного charset у заголовку httpx може
            # вгадати неправильно — декодуємо самі, щоб не ловити «?» замість апострофів.
            body = response.content.decode("utf-8", errors="replace")
            if response.status_code == 404 or looks_like_not_found(body):
                raise SessionError(f"404: {url}")
            lowered = body.lower()
            if not any(marker in lowered for marker in CONTENT_MARKERS):
                self._missing_content(url, lowered)
            return body

        raise SessionError(f"Не вдалося завантажити {url}: {last_error}")

    def _missing_content(self, url: str, lowered: str) -> Never:
        """У відповіді немає тіла статті — пояснюємо, чому саме."""
        if any(marker in lowered for marker in BLOCK_MARKERS):
            raise ChallengeError(f"CAPTCHA/верифікація: розвʼяжи її у вікні браузера, потім перезапусти етап ({url})")
        if not self.has_cookies:
            raise SessionError(f"потрібна сесія: без cookies сервер віддає заглушку замість статті ({url})")
        raise ChallengeError(f"сесія прострочена або недійсна — у відповіді немає тіла статті ({url})")

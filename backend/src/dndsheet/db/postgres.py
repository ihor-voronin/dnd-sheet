"""Звідки брати базу і як тримати зʼєднання.

`DNDSHEET_DATABASE_URL` (`postgresql://роль:пароль@pg:5432/dndsheet`) вмикає PostgreSQL;
без неї застосунок працює на SQLite, як і раніше. Обробники FastAPI синхронні й
виконуються в пулі потоків, тож і пул зʼєднань синхронний: кожна операція бере
зʼєднання на одну транзакцію й повертає його.
"""

from __future__ import annotations

import os

from psycopg_pool import ConnectionPool

from dndsheet.db.migrate import pending

URL_ENV = "DNDSHEET_DATABASE_URL"
POOL_ENV = "DNDSHEET_DATABASE_POOL_MAX"


def database_url() -> str | None:
    """Адреса бази із середовища; порожньо — PostgreSQL вимкнено."""
    value = os.environ.get(URL_ENV, "").strip()
    return value or None


def open_pool(conninfo: str, *, max_size: int | None = None) -> ConnectionPool:
    """Пул для застосунку: невеликий (спільний сервер, мало памʼяті), зʼєднання перевіряються.

    `check` ловить зʼєднання, що зникли після перезапуску сервера бази, до того, як їх
    отримає запит. Пул відкривається одразу й чекає першого зʼєднання: якщо бази немає,
    застосунок не стартує з незрозумілою помилкою посеред запиту.
    """
    size = max_size or int(os.environ.get(POOL_ENV, "") or 5)
    pool = ConnectionPool(
        conninfo,
        min_size=1,
        max_size=size,
        open=False,
        check=ConnectionPool.check_connection,
        kwargs={"application_name": "dndsheet"},
    )
    pool.open(wait=True, timeout=30)
    return pool


def require_schema(conninfo: str) -> None:
    """Зупинити старт, якщо в базі бракує міграцій: їх запускає деплой, а не застосунок."""
    missing = pending(conninfo)
    if missing:
        names = ", ".join(f"{migration.version}_{migration.name}" for migration in missing)
        raise RuntimeError(f"у базі не застосовано міграції: {names} — запустіть `python -m dndsheet.db migrate`")

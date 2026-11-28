"""Команди бази: `python -m dndsheet.db <команда>` (docs/database.md).

    migrate                       застосувати міграції (роль власника схеми)
    status                        які міграції застосовані, яких бракує
    copy-from-sqlite FILE         SQLite → Postgres у одній транзакції з перевіркою
    verify FILE                   порівняти SQLite з Postgres (кількість і SHA-256 по таблицях)
    copy-to-sqlite NEW_FILE       Postgres → новий файл SQLite (відкат)

Адреса бази — `--url` або `DNDSHEET_DATABASE_URL`. Код виходу 0 — усе гаразд.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from dndsheet.db import transfer
from dndsheet.db.migrate import MigrationError, load, migrate, pending
from dndsheet.db.postgres import URL_ENV, database_url


def _out(line: str) -> None:
    sys.stdout.write(line + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dndsheet.db", description=__doc__.splitlines()[0])
    parser.add_argument("--url", help=f"адреса бази (типово — {URL_ENV})")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    commands.add_parser("status")
    copy_from = commands.add_parser("copy-from-sqlite")
    copy_from.add_argument("source", type=Path)
    copy_from.add_argument("--replace", action="store_true", help="очистити таблиці, якщо в них уже є дані")
    copy_from.add_argument("--drop-orphans", action="store_true", help="пропустити сесії й токени без користувача")
    check = commands.add_parser("verify")
    check.add_argument("source", type=Path)
    copy_to = commands.add_parser("copy-to-sqlite")
    copy_to.add_argument("target", type=Path)
    args = parser.parse_args(argv)

    url = args.url or database_url()
    if not url:
        sys.stderr.write(f"не задано адресу бази: --url або {URL_ENV}\n")
        return 2
    try:
        if args.command == "migrate":
            applied = migrate(url)
            for migration in applied:
                _out(f"застосовано {migration.version}_{migration.name}")
            _out("схема актуальна" if not applied else f"готово: {len(applied)}")
        elif args.command == "status":
            missing = {migration.version for migration in pending(url)}
            for migration in load():
                mark = "  бракує" if migration.version in missing else "  є    "
                _out(f"{mark} {migration.version}_{migration.name}")
            return 1 if missing else 0
        elif args.command == "copy-from-sqlite":
            transfer.format_report(
                transfer.copy_to_postgres(args.source, url, replace=args.replace, drop_orphans=args.drop_orphans), _out
            )
            _out("скопійовано й перевірено")
        elif args.command == "verify":
            transfer.format_report(transfer.verify(args.source, url), _out)
            _out("збігається")
        else:
            transfer.format_report(transfer.copy_to_sqlite(url, args.target), _out)
            _out(f"записано й перевірено: {args.target}")
    except (MigrationError, transfer.TransferError, psycopg.Error) as error:
        sys.stderr.write(f"помилка: {error}\n")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

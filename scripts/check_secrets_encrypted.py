#!/usr/bin/env python3
"""Хук pre-commit і крок CI: усе, що має шифрувати git-crypt, в індексі — зашифроване.

git-crypt шифрує файли фільтром `clean` під час `git add` — це секрети деплою
(deploy/secrets/) і корпус довідника з текстами книг (content/compendium,
bestiary, index). Якщо фільтр не спрацював (git-crypt не встановлено,
репозиторій не розблоковано, зламане правило в .gitattributes), у публічний
GitHub пішов би відкритий текст.

Перевіряємо саме індекс: кожен файл з атрибутом `filter=git-crypt` має бути
blob-ом, що починається з `\\0GITCRYPT\\0`. Файли беремо з `git ls-files`, а не
від pre-commit: так перевірка не залежить від exclude і однакова локально й у CI.

    python scripts/check_secrets_encrypted.py
"""

from __future__ import annotations

import subprocess
import sys

MAGIC = b"\x00GITCRYPT\x00"


def git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], input=data, capture_output=True, check=True).stdout


def encrypted_paths() -> list[str]:
    """Файли індексу, які за .gitattributes мають бути зашифровані."""
    listed = git("ls-files", "-z").split(b"\0")
    paths = b"\0".join(path for path in listed if path)
    attributes = git("check-attr", "-z", "--stdin", "--cached", "filter", data=paths).split(b"\0")
    # Формат -z: шлях, атрибут, значення — трійками.
    return [
        attributes[index].decode("utf-8")
        for index in range(0, len(attributes) - 2, 3)
        if attributes[index + 2] == b"git-crypt"
    ]


def leaked(paths: list[str]) -> list[str]:
    """Шляхи, чий blob в індексі не починається з підпису git-crypt."""
    if not paths:
        return []
    request = "".join(f":{path}\n" for path in paths).encode("utf-8")
    process = subprocess.run(["git", "cat-file", "--batch"], input=request, capture_output=True, check=True)
    out = process.stdout
    bad: list[str] = []
    position = 0
    for path in paths:
        newline = out.index(b"\n", position)
        header = out[position:newline].split()
        position = newline + 1
        if len(header) < 3 or header[1] != b"blob":  # missing — файл видаляють
            continue
        size = int(header[2])
        if not out[position : position + size].startswith(MAGIC):
            bad.append(path)
        position += size + 1  # вміст і завершальний \n
    return bad


def main() -> int:
    bad = leaked(encrypted_paths())
    if bad:
        sys.stderr.write(
            "Ці файли мають іти в git зашифрованими (git-crypt), але в індексі — відкритий текст:\n"
            + "".join(f"  {path}\n" for path in bad[:20])
            + (f"  … і ще {len(bad) - 20}\n" if len(bad) > 20 else "")
            + "Приберіть з індексу (git restore --staged <файл>), перевірте `git-crypt status`\n"
            "і правило в .gitattributes, потім додайте знову.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

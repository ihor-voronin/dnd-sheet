#!/usr/bin/env python3
"""Хук pre-commit: файли з deploy/secrets/ ідуть у коміт лише зашифрованими.

git-crypt шифрує їх фільтром `clean` під час `git add`. Якщо фільтр не спрацював
(git-crypt не встановлено, репозиторій не розблоковано, правило в
.gitattributes зламане), у git потрапив би відкритий текст — і в GitHub теж.
Тому перевіряємо саме те, що стоїть в індексі: зашифрований blob git-crypt
починається з `\\0GITCRYPT\\0`.

    python scripts/check_secrets_encrypted.py deploy/secrets/prod.env ...
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

MAGIC = b"\x00GITCRYPT\x00"
#: Сам файл з правилом шифрування лишається відкритим — інакше git не знав би, що шифрувати.
PLAIN = {".gitattributes"}


def staged_blob(path: str) -> bytes | None:
    result = subprocess.run(["git", "cat-file", "blob", f":{path}"], capture_output=True, check=False)
    return result.stdout if result.returncode == 0 else None


def main(paths: Sequence[str] = sys.argv[1:]) -> int:
    leaked = []
    for path in paths:
        if path.replace("\\", "/").rsplit("/", 1)[-1] in PLAIN:
            continue
        blob = staged_blob(path)
        if blob is None:  # файл видаляють або він не в індексі — нічого не потрапить у git
            continue
        if not blob.startswith(MAGIC):
            leaked.append(path)
    if leaked:
        sys.stderr.write(
            "Ці файли йдуть у коміт НЕзашифрованими (git-crypt не спрацював):\n"
            + "".join(f"  {path}\n" for path in leaked)
            + "Приберіть з індексу (git restore --staged <файл>), перевірте `git-crypt status`\n"
            "і правило в deploy/secrets/.gitattributes, потім додайте знову.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

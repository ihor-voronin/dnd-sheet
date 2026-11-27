#!/usr/bin/env python3
"""A pre-commit hook and CI step: everything git-crypt should encrypt is encrypted in the index.

git-crypt encrypts files with the `clean` filter during `git add` — the deploy secrets
(deploy/secrets/) and the compendium corpus with book texts (content/compendium,
bestiary, index). If the filter didn't run (git-crypt isn't installed, the repository
isn't unlocked, a broken rule in .gitattributes), plaintext would reach the public
GitHub repository.

We check the index itself: every file with the `filter=git-crypt` attribute must be
a blob starting with `\\0GITCRYPT\\0`. Files come from `git ls-files`, not from
pre-commit: that way the check doesn't depend on exclude and is the same locally and in CI.

    python scripts/check_secrets_encrypted.py
"""

from __future__ import annotations

import subprocess
import sys

MAGIC = b"\x00GITCRYPT\x00"


def git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], input=data, capture_output=True, check=True).stdout


def encrypted_paths() -> list[str]:
    """Index files that .gitattributes says must be encrypted."""
    listed = git("ls-files", "-z").split(b"\0")
    paths = b"\0".join(path for path in listed if path)
    attributes = git("check-attr", "-z", "--stdin", "--cached", "filter", data=paths).split(b"\0")
    # The -z format: path, attribute, value — in triples.
    return [
        attributes[index].decode("utf-8")
        for index in range(0, len(attributes) - 2, 3)
        if attributes[index + 2] == b"git-crypt"
    ]


def leaked(paths: list[str]) -> list[str]:
    """Paths whose blob in the index doesn't start with the git-crypt signature."""
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
        if len(header) < 3 or header[1] != b"blob":  # missing — the file is being deleted
            continue
        size = int(header[2])
        if not out[position : position + size].startswith(MAGIC):
            bad.append(path)
        position += size + 1  # the content and the trailing \n
    return bad


def main() -> int:
    bad = leaked(encrypted_paths())
    if bad:
        sys.stderr.write(
            "These files must go into git encrypted (git-crypt), but the index holds plaintext:\n"
            + "".join(f"  {path}\n" for path in bad[:20])
            + (f"  … and {len(bad) - 20} more\n" if len(bad) > 20 else "")
            + "Remove them from the index (git restore --staged <file>), check `git-crypt status`\n"
            "and the rule in .gitattributes, then add them again.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

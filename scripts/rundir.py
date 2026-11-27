#!/usr/bin/env python3
"""Run a command from a given directory (for the frontend pre-commit hooks).

Arguments after `--` are paths from the repository root; they're rewritten relative
to the directory. It uses subprocess: on Windows `os.execvp` doesn't find
`npx.cmd`, while `shutil.which` respects PATHEXT.

    python scripts/rundir.py frontend npx --no-install eslint -- frontend/src/App.tsx
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence


def main(argv: Sequence[str] = sys.argv[1:]) -> int:
    if len(argv) < 2:
        sys.stderr.write("usage: rundir.py <dir> <command> [args...] [-- <paths...>]\n")
        return 2

    directory, command, *rest = argv
    args: list[str] = []
    paths = False
    for arg in rest:
        if arg == "--":
            paths = True
            args.append(arg)
        elif paths:
            args.append(os.path.relpath(arg, directory))
        else:
            args.append(arg)

    executable = shutil.which(command)
    if executable is None:
        sys.stderr.write(f"rundir.py: command '{command}' not found in PATH\n")
        return 127
    return subprocess.run([executable, *args], cwd=directory, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())

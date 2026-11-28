"""Кожен файл пакета, що не є кодом, потрапляє у wheel (а отже в образ).

Тести запускаються з `src/`, тож забутий рядок у `[tool.setuptools.package-data]` вони не
бачать: образ збирається без файлу й падає вже на сервері (так було з emblems.json, #17).
"""

from __future__ import annotations

import tomllib
from fnmatch import fnmatch
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SRC = BACKEND / "src"
#: Файли, яким у пакеті не місце в рантаймі: setuptools їх і не мусить везти.
IGNORED = {"README.md"}


def _patterns() -> dict[str, list[str]]:
    config = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    return config["tool"]["setuptools"]["package-data"]


def _shipped(path: Path, patterns: dict[str, list[str]]) -> bool:
    relative = path.relative_to(SRC)
    for package, globs in patterns.items():
        package_dir = Path(*package.split("."))
        if package_dir in relative.parents:
            inside = relative.relative_to(package_dir).as_posix()
            if any(fnmatch(inside, glob) and inside.count("/") == glob.count("/") for glob in globs):
                return True
    return False


def test_every_data_file_is_in_package_data() -> None:
    patterns = _patterns()
    data_files = [
        path
        for path in SRC.rglob("*")
        if path.is_file()
        and path.suffix not in {".py", ".pyc"}
        and "__pycache__" not in path.parts
        and ".egg-info" not in str(path)
        and path.name not in IGNORED
    ]
    missing = [path.relative_to(SRC).as_posix() for path in data_files if not _shipped(path, patterns)]
    assert not missing, f"додайте в [tool.setuptools.package-data] backend/pyproject.toml: {missing}"

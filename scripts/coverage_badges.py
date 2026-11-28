#!/usr/bin/env python3
"""shields.io endpoint JSON for the README badges, from the CI reports.

Reads what the backend and frontend jobs leave behind and writes one small JSON per
badge; CI pushes them to the `badges` branch, and the README asks shields.io to draw
them (https://shields.io/badges/endpoint-badge).

    python scripts/coverage_badges.py --out badges/

Inputs (missing ones are skipped):
    coverage/backend.xml                       Cobertura from pytest-cov
    coverage/backend-junit.xml                 JUnit from pytest
    frontend/coverage/coverage-summary.json    json-summary from vitest
    frontend/coverage/junit.xml                JUnit from vitest
    $RECORDS                                   compendium + bestiary records
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def color(percent: float) -> str:
    if percent >= 90:
        return "brightgreen"
    if percent >= 80:
        return "green"
    if percent >= 70:
        return "yellow"
    return "red"


def badge(label: str, message: str, badge_color: str, logo: str | None = None) -> dict:
    payload = {"schemaVersion": 1, "label": label, "message": message, "color": badge_color}
    if logo:
        payload["namedLogo"] = logo
    return payload


def backend_coverage(path: Path) -> float | None:
    if not path.exists():
        return None
    return float(ET.parse(path).getroot().get("line-rate", "0")) * 100


def frontend_coverage(path: Path) -> float | None:
    if not path.exists():
        return None
    return float(json.loads(path.read_text(encoding="utf-8"))["total"]["lines"]["pct"])


def junit_tests(path: Path) -> int:
    """Passed tests in a JUnit report (pytest writes <testsuites><testsuite>, vitest the same)."""
    if not path.exists():
        return 0
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = 0
    for suite in suites:
        failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0)) + int(suite.get("skipped", 0))
        total += int(suite.get("tests", 0)) - failed
    return total


def build(root: Path) -> dict[str, dict]:
    badges: dict[str, dict] = {}
    backend = backend_coverage(root / "coverage" / "backend.xml")
    if backend is not None:
        badges["backend-coverage"] = badge("backend coverage", f"{backend:.0f}%", color(backend), "python")
    frontend = frontend_coverage(root / "frontend" / "coverage" / "coverage-summary.json")
    if frontend is not None:
        badges["frontend-coverage"] = badge("frontend coverage", f"{frontend:.0f}%", color(frontend), "react")
    tests = junit_tests(root / "coverage" / "backend-junit.xml") + junit_tests(
        root / "frontend" / "coverage" / "junit.xml"
    )
    if tests:
        badges["tests"] = badge("tests", f"{tests} passing", "brightgreen", "pytest")
    records = os.environ.get("RECORDS", "").strip()
    if records.isdigit():
        badges["records"] = badge("compendium", f"{int(records):,} records".replace(",", " "), "8a2be2")
    return badges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    badges = build(ROOT)
    if not badges:
        sys.stderr.write("no reports found\n")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for name, payload in badges.items():
        (args.out / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{name}: {payload['message']}")  # noqa: T201 — a CI script
    return 0


if __name__ == "__main__":
    sys.exit(main())

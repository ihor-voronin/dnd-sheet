"""Зібрати аркуш для друку з еталонних персонажів — щоб дивитися на оформлення.

    python scripts/print_preview.py            # HTML у logs/print-preview/*.html
    python scripts/print_preview.py --pdf      # ще й PDF (потрібен WeasyPrint, напр. у Docker)

Персонажі — еталонні (`golden`) у тимчасовому каталозі даних: `var/` не чіпається.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("DNDSHEET_CONTENT_DIR", str(ROOT / "content"))
os.environ["DNDSHEET_AUTH"] = "off"
os.environ["DNDSHEET_DATA_DIR"] = tempfile.mkdtemp(prefix="print-preview-")

from types import SimpleNamespace  # noqa: E402

from dndsheet.api.app import create_app  # noqa: E402
from dndsheet.characters.api.router import _print_view  # noqa: E402
from dndsheet.export.domain.renderer import RenderOptions  # noqa: E402


def main(pdf: bool) -> None:
    app = create_app()
    # Без HTTP-клієнта: у робочому образі Docker немає httpx, а тут він і не потрібен.
    request = SimpleNamespace(app=app)
    renderer = app.state.renderers.get("pdf")
    out = ROOT / "logs" / "print-preview"
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from print_samples import SAMPLES  # noqa: PLC0415 — лише для цього скрипта

    cases = [(case.key, replace(case.character, id=case.key)) for case in app.state.golden_cases]
    cases += [(key, build(app.state.rules)) for key, build in SAMPLES.items()]
    for key, character in cases:
        case = SimpleNamespace(key=key)
        view = _print_view(request, character)
        html = renderer.character_html(view, RenderOptions())
        (out / f"{case.key}.html").write_text(html, encoding="utf-8")
        print("html:", out / f"{case.key}.html")
        if pdf:
            result = renderer.render_character(view, RenderOptions())
            (out / f"{case.key}.pdf").write_bytes(result.content)
            print("pdf: ", out / f"{case.key}.pdf")


if __name__ == "__main__":
    main("--pdf" in sys.argv)

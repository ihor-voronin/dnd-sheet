"""Точка входу: `uvicorn dndsheet.main:app --reload`."""

from __future__ import annotations

from dndsheet.api.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dndsheet.main:app", host="127.0.0.1", port=8000, reload=True)

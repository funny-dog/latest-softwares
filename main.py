"""Latest Softwares FastAPI Cloud entrypoint for the international edition.

Responsibilities:
  - GET /api/packages returns international package data filtered by edition
  - GET /api/health returns health metadata
  - GET / serves the static frontend built by build_web.py --edition intl

Deployment note:
  dist/ is ignored by .gitignore and re-included for FastAPI Cloud through
  .fastapicloudignore. Build it before deployment:
    python scripts/build_web.py --edition intl
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from scripts.editions import filter_data_by_edition

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "latest.json"
DIST_DIR = ROOT / "dist"

# This deployment serves the international edition only.
EDITION = "intl"

app = FastAPI(
    title="Latest Softwares API (International)",
    description=(
        "Daily metadata sync for latest software releases, with a JSON API "
        "and static web frontend for the international edition."
    ),
    version="1.0.0",
)


def _load_data() -> dict:
    """Load data/latest.json or return an empty shell when it is missing."""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"schema_version": 2, "packages": [], "stats": {}}


# JSON API
@app.get("/api/health", tags=["meta"])
def health():
    """Return health metadata."""
    data = filter_data_by_edition(_load_data(), EDITION)
    return {
        "status": "ok",
        "edition": EDITION,
        "packages_count": len(data.get("packages", [])),
        "generated_at": data.get("generated_at"),
    }


@app.get("/api/packages", tags=["packages"])
def list_packages():
    """Return all international package data."""
    data = filter_data_by_edition(_load_data(), EDITION)
    return JSONResponse(content=data)


# Static frontend. dist/ must be built with build_web.py --edition intl.
if DIST_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(DIST_DIR), html=True),
        name="static",
    )

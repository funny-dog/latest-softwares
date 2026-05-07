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
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from scripts.editions import filter_data_by_edition

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "latest.json"
DIST_DIR = ROOT / "dist"
DB_PATH = Path(
    os.environ.get(
        "LATEST_SOFTWARES_STATS_DB", str(ROOT / "data" / "site_metrics.db")
    )
)
SEED_FILE = Path(
    os.environ.get(
        "LATEST_SOFTWARES_STATS_SEED", str(ROOT / "data" / "site_metrics.json")
    )
)
STATS_LOCK = threading.Lock()

# This deployment serves the international edition only.
EDITION = "intl"


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _seed_db_from_json()
    yield


app = FastAPI(
    title="Latest Softwares API (International)",
    description=(
        "Daily metadata sync for latest software releases, with a JSON API "
        "and static web frontend for the international edition."
    ),
    version="1.0.0",
    lifespan=_lifespan,
)


def _load_data() -> dict:
    """Load data/latest.json or return an empty shell when it is missing."""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"schema_version": 2, "packages": [], "stats": {}}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visits (
            path TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            package_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (package_id, platform)
        )
        """
    )
    conn.commit()
    conn.close()


def _seed_db_from_json() -> None:
    if not SEED_FILE.exists():
        return
    try:
        seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not seed.get("visits") and not seed.get("downloads"):
        return
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT value FROM metrics WHERE key = 'visits_total'"
    ).fetchone()
    if row is not None and int(row[0]) > 0:
        conn.close()
        return
    visits_total = seed.get("visits", {}).get("total", 0)
    if visits_total:
        conn.execute(
            "INSERT INTO metrics (key, value) VALUES ('visits_total', ?)",
            (str(visits_total),),
        )
    for path, count in seed.get("visits", {}).get("paths", {}).items():
        if count:
            conn.execute(
                "INSERT INTO visits (path, count) VALUES (?, ?)", (path, count)
            )
    downloads_total = seed.get("downloads", {}).get("total", 0)
    if downloads_total:
        conn.execute(
            "INSERT INTO metrics (key, value) VALUES ('downloads_total', ?)",
            (str(downloads_total),),
        )
    for asset_key, count in seed.get("downloads", {}).get("assets", {}).items():
        if ":" in asset_key and count:
            package_id, platform = asset_key.split(":", 1)
            conn.execute(
                "INSERT INTO downloads (package_id, platform, count) VALUES (?, ?, ?)",
                (package_id, platform, count),
            )
    updated_at = seed.get("updated_at")
    if updated_at:
        conn.execute(
            "INSERT INTO metrics (key, value) VALUES ('updated_at', ?)",
            (updated_at,),
        )
    conn.commit()
    conn.close()


def _empty_metrics() -> dict:
    return {
        "schema_version": 1,
        "scope": "instance-local",
        "storage": "persistent-sqlite",
        "updated_at": None,
        "visits": {"total": 0, "paths": {}},
        "downloads": {"total": 0, "packages": {}, "platforms": {}, "assets": {}},
    }


def _load_metrics() -> dict:
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    metrics = _empty_metrics()

    # 加载总访问量
    row = conn.execute(
        "SELECT value FROM metrics WHERE key = 'visits_total'"
    ).fetchone()
    metrics["visits"]["total"] = int(row[0]) if row else 0

    # 加载各路径访问量
    for path, count in conn.execute("SELECT path, count FROM visits"):
        metrics["visits"]["paths"][path] = count

    # 加载总下载量
    row = conn.execute(
        "SELECT value FROM metrics WHERE key = 'downloads_total'"
    ).fetchone()
    metrics["downloads"]["total"] = int(row[0]) if row else 0

    # 加载各包下载量
    packages = {}
    platforms = {}
    assets = {}
    for package_id, platform, count in conn.execute(
        "SELECT package_id, platform, count FROM downloads"
    ):
        assets[f"{package_id}:{platform}"] = count
        packages[package_id] = packages.get(package_id, 0) + count
        platforms[platform] = platforms.get(platform, 0) + count

    metrics["downloads"]["packages"] = packages
    metrics["downloads"]["platforms"] = platforms
    metrics["downloads"]["assets"] = assets

    # 加载更新时间
    row = conn.execute(
        "SELECT value FROM metrics WHERE key = 'updated_at'"
    ).fetchone()
    metrics["updated_at"] = row[0] if row else None

    conn.close()
    return metrics


def _increment_visit(path: str) -> None:
    with STATS_LOCK:
        _init_db()
        conn = sqlite3.connect(str(DB_PATH))
        # 更新总访问量
        conn.execute(
            """
            INSERT INTO metrics (key, value) VALUES ('visits_total', '1')
            ON CONFLICT(key) DO UPDATE SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
            """
        )
        # 更新路径访问量
        conn.execute(
            """
            INSERT INTO visits (path, count) VALUES (?, 1)
            ON CONFLICT(path) DO UPDATE SET count = count + 1
            """,
            (path,),
        )
        # 更新时间
        conn.execute(
            """
            INSERT INTO metrics (key, value) VALUES ('updated_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = ?
            """,
            (_utc_now_iso(), _utc_now_iso()),
        )
        conn.commit()
        conn.close()


def _increment_download(package_id: str, platform: str) -> None:
    with STATS_LOCK:
        _init_db()
        conn = sqlite3.connect(str(DB_PATH))
        # 更新总下载量
        conn.execute(
            """
            INSERT INTO metrics (key, value) VALUES ('downloads_total', '1')
            ON CONFLICT(key) DO UPDATE SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
            """
        )
        # 更新包下载量
        conn.execute(
            """
            INSERT INTO downloads (package_id, platform, count) VALUES (?, ?, 1)
            ON CONFLICT(package_id, platform) DO UPDATE SET count = count + 1
            """,
            (package_id, platform),
        )
        # 更新时间
        conn.execute(
            """
            INSERT INTO metrics (key, value) VALUES ('updated_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = ?
            """,
            (_utc_now_iso(), _utc_now_iso()),
        )
        conn.commit()
        conn.close()


def _log_metric_event(event: str, **payload: str) -> None:
    record = {"event": event, "timestamp": _utc_now_iso(), **payload}
    print(
        "latest_softwares_event "
        + json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )


def _find_asset(package_id: str, platform: str) -> dict:
    data = filter_data_by_edition(_load_data(), EDITION)
    for package in data.get("packages", []):
        if package.get("id") != package_id:
            continue
        for asset in package.get("assets", []):
            if asset.get("platform") == platform and asset.get("url"):
                return asset
    raise HTTPException(status_code=404, detail="download asset not found")


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


@app.post("/api/visit", tags=["metrics"])
def record_visit():
    """Record a frontend page view."""
    _increment_visit("/")
    _log_metric_event("visit", path="/")
    return JSONResponse(content={"status": "ok", "metrics": _load_metrics()})


@app.get("/api/download/{package_id}/{platform}", tags=["metrics"])
def redirect_download(package_id: str, platform: str):
    """Record a download click and redirect to the upstream asset URL."""
    asset = _find_asset(package_id, platform)
    _increment_download(package_id, platform)
    _log_metric_event(
        "download",
        package_id=package_id,
        platform=platform,
        url=asset["url"],
    )
    return RedirectResponse(asset["url"])


@app.get("/api/metrics", tags=["metrics"])
def metrics():
    """Return lightweight visit and download-click counters."""
    return JSONResponse(content=_load_metrics())


# Static frontend. dist/ must be built with build_web.py --edition intl.
if DIST_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(DIST_DIR), html=True),
        name="static",
    )

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
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from scripts.editions import filter_data_by_edition

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "latest.json"
DIST_DIR = ROOT / "dist"
STATS_FILE = Path(
    os.environ.get(
        "LATEST_SOFTWARES_STATS_FILE", str(ROOT / "data" / "site_metrics.json")
    )
)
STATS_LOCK = threading.Lock()

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_metrics() -> dict:
    return {
        "schema_version": 1,
        "scope": "instance-local",
        "storage": "ephemeral-file",
        "note": (
            "FastAPI Cloud can autoscale to multiple instances; use runtime "
            "logs for aggregate visit and download counts."
        ),
        "updated_at": None,
        "visits": {"total": 0, "paths": {}},
        "downloads": {"total": 0, "packages": {}, "platforms": {}, "assets": {}},
    }


def _load_metrics() -> dict:
    if not STATS_FILE.exists():
        return _empty_metrics()
    try:
        data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_metrics()

    metrics = _empty_metrics()
    metrics.update({key: data.get(key, metrics[key]) for key in metrics})
    metrics["visits"].setdefault("total", 0)
    metrics["visits"].setdefault("paths", {})
    metrics["downloads"].setdefault("total", 0)
    metrics["downloads"].setdefault("packages", {})
    metrics["downloads"].setdefault("platforms", {})
    metrics["downloads"].setdefault("assets", {})
    return metrics


def _write_metrics(metrics: dict) -> None:
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _increment_visit(path: str) -> None:
    with STATS_LOCK:
        metrics = _load_metrics()
        metrics["visits"]["total"] += 1
        metrics["visits"]["paths"][path] = metrics["visits"]["paths"].get(path, 0) + 1
        metrics["updated_at"] = _utc_now_iso()
        _write_metrics(metrics)


def _increment_download(package_id: str, platform: str) -> None:
    asset_key = f"{package_id}:{platform}"
    with STATS_LOCK:
        metrics = _load_metrics()
        metrics["downloads"]["total"] += 1
        metrics["downloads"]["packages"][package_id] = (
            metrics["downloads"]["packages"].get(package_id, 0) + 1
        )
        metrics["downloads"]["platforms"][platform] = (
            metrics["downloads"]["platforms"].get(platform, 0) + 1
        )
        metrics["downloads"]["assets"][asset_key] = (
            metrics["downloads"]["assets"].get(asset_key, 0) + 1
        )
        metrics["updated_at"] = _utc_now_iso()
        _write_metrics(metrics)


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

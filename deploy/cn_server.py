"""Latest Softwares 国内版 API 后端。

部署在阿里云 VPS 上，由 nginx 反向代理（/api/ → 127.0.0.1:8001）。
提供访问统计、下载点击追踪和重定向功能。

统计数据存储在独立于部署目录的位置（默认 /var/lib/latest-softwares/metrics.json），
不受 rsync --delete 影响。

环境变量：
  LATEST_SOFTWARES_METRICS_FILE — 统计文件路径（默认 /var/lib/latest-softwares/metrics.json）
  LATEST_SOFTWARES_DATA_FILE    — 包数据文件路径（默认 data/latest.json）
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = Path(
    os.environ.get("LATEST_SOFTWARES_DATA_FILE", str(ROOT / "data" / "latest.json"))
)
STATS_FILE = Path(
    os.environ.get(
        "LATEST_SOFTWARES_METRICS_FILE", "/var/lib/latest-softwares/metrics.json"
    )
)
STATS_LOCK = threading.Lock()

EDITION = "cn"

app = FastAPI(
    title="Latest Softwares API (CN)",
    description="国内版访问统计与下载追踪 API",
    version="1.0.0",
)


def _load_data() -> dict:
    """加载包数据，文件不存在时返回空结构。"""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"schema_version": 2, "packages": [], "stats": {}}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_metrics() -> dict:
    return {
        "schema_version": 1,
        "scope": "instance-local",
        "storage": "persistent-file",
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


def _find_asset(package_id: str, platform: str) -> dict:
    data = _load_data()
    for package in data.get("packages", []):
        if package.get("id") != package_id:
            continue
        editions = package.get("editions", ["cn", "intl"])
        if EDITION not in editions:
            continue
        for asset in package.get("assets", []):
            if asset.get("platform") == platform and asset.get("url"):
                return asset
    raise HTTPException(status_code=404, detail="download asset not found")


# ── API 端点 ──────────────────────────────────────


@app.get("/api/health", tags=["meta"])
def health():
    """健康检查。"""
    data = _load_data()
    cn_packages = [
        p
        for p in data.get("packages", [])
        if EDITION in p.get("editions", ["cn", "intl"])
    ]
    return {
        "status": "ok",
        "edition": EDITION,
        "packages_count": len(cn_packages),
        "generated_at": data.get("generated_at"),
    }


@app.post("/api/visit", tags=["metrics"])
def record_visit():
    """记录一次页面访问。"""
    _increment_visit("/")
    return JSONResponse(content={"status": "ok", "metrics": _load_metrics()})


@app.get("/api/metrics", tags=["metrics"])
def metrics():
    """返回访问和下载统计。"""
    return JSONResponse(content=_load_metrics())


@app.get("/api/download/{package_id}/{platform}", tags=["metrics"])
def redirect_download(package_id: str, platform: str):
    """记录下载点击并重定向到上游资源。"""
    asset = _find_asset(package_id, platform)
    _increment_download(package_id, platform)
    return RedirectResponse(asset["url"])

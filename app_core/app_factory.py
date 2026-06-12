"""共享的 FastAPI 应用工厂。

两版后端的端点(health / visit / download / metrics,以及 intl 的 packages)
逻辑完全相同,只在这里写一遍。差异通过参数注入:
  - store          : 存储后端(JsonFileMetricsStore / SqlMetricsStore)
  - edition        : "cn" / "intl",决定数据过滤
  - serve_static_dir       : intl 挂载 dist/;cn 由 nginx 服务静态文件,传 None
  - with_packages_endpoint : 是否暴露 /api/packages(目前仅 intl)
  - log_events     : 是否打结构化事件日志(intl 给 FastAPI Cloud 日志用)
  - lifespan       : 可选启动钩子(intl 用于 seed)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app_core.editions import filter_data_by_edition
from app_core.metrics import load_data, utc_now_iso
from app_core.store import MetricsStore


def _log_event(event: str, **payload: str) -> None:
    """打印一行结构化事件日志(供日志平台采集)。"""
    record = {"event": event, "timestamp": utc_now_iso(), **payload}
    print(
        "latest_softwares_event "
        + json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        flush=True,
    )


def create_app(
    *,
    edition: str,
    store: MetricsStore,
    data_file: Path | str,
    serve_static_dir: Path | str | None = None,
    with_packages_endpoint: bool = False,
    log_events: bool = False,
    lifespan: Callable[..., Any] | None = None,
    title: str | None = None,
    description: str = "",
) -> FastAPI:
    """组装并返回一个 FastAPI 应用。两版入口各自选好参数后调用即可。"""
    data_file = Path(data_file)
    app = FastAPI(
        title=title or f"Latest Softwares API ({edition})",
        description=description,
        version="1.0.0",
        lifespan=lifespan,
    )

    def _find_asset(package_id: str, platform: str) -> dict[str, Any]:
        data = filter_data_by_edition(load_data(data_file), edition)
        for package in data.get("packages", []):
            if package.get("id") != package_id:
                continue
            for asset in package.get("assets", []):
                if asset.get("platform") == platform and asset.get("url"):
                    return asset
        raise HTTPException(status_code=404, detail="download asset not found")

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, Any]:
        """健康检查 + 元数据。"""
        data = filter_data_by_edition(load_data(data_file), edition)
        return {
            "status": "ok",
            "edition": edition,
            "packages_count": len(data.get("packages", [])),
            "generated_at": data.get("generated_at"),
        }

    if with_packages_endpoint:

        @app.get("/api/packages", tags=["packages"])
        def list_packages() -> JSONResponse:
            """返回按 edition 过滤后的包数据。"""
            return JSONResponse(
                content=filter_data_by_edition(load_data(data_file), edition)
            )

    @app.post("/api/visit", tags=["metrics"])
    def record_visit() -> JSONResponse:
        """记录一次页面访问。"""
        store.increment_visit("/")
        if log_events:
            _log_event("visit", path="/")
        return JSONResponse(content={"status": "ok", "metrics": store.load()})

    @app.get("/api/download/{package_id}/{platform}", tags=["metrics"])
    def redirect_download(package_id: str, platform: str) -> RedirectResponse:
        """记录下载点击并重定向到上游资源 URL。"""
        asset = _find_asset(package_id, platform)
        store.increment_download(package_id, platform)
        if log_events:
            _log_event(
                "download",
                package_id=package_id,
                platform=platform,
                url=asset["url"],
            )
        return RedirectResponse(asset["url"])

    @app.get("/api/metrics", tags=["metrics"])
    def metrics() -> JSONResponse:
        """返回访问与下载点击统计。"""
        return JSONResponse(content=store.load())

    # 静态前端必须最后挂载:mount("/") 会兜底所有未匹配路径,先注册的 /api/* 优先。
    if serve_static_dir is not None and Path(serve_static_dir).is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(serve_static_dir), html=True),
            name="static",
        )

    return app

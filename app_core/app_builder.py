"""按 profile 装配 FastAPI 应用 —— cn/intl 与未来部署目标的统一装配层。

差异(edition / 存储后端 / 是否挂静态 / 是否暴露 packages / 日志 / seed)全部由
config/profiles/<name>.json 声明,这里只负责:读 profile → 造 store → 调 create_app。

为何 JSON 而非 TOML/YAML:国内版后端 venv 仅含 fastapi+uvicorn 且不会自动加依赖,
运行时配置解析必须 stdlib-only;json 是其中唯一兼具「全 Python 版本(≥3.10)兼容
+ 公认配置格式」的。secret(TURSO_*)始终走环境变量,不进文件。
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app_core.app_factory import create_app
from app_core.store import JsonFileMetricsStore, MetricsStore, SqlMetricsStore

# 仓库根:app_core/ 的上一级。app.py / main.py / deploy.cn_server 都靠它定位资源。
ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "config" / "profiles"
DEFAULT_PROFILE = "intl"


def _resolve(path: str, root: Path) -> Path:
    """相对路径按仓库根解析,绝对路径原样返回。"""
    p = Path(path)
    return p if p.is_absolute() else root / p


def load_profile(name: str, *, profiles_dir: Path = PROFILES_DIR) -> dict[str, Any]:
    """读取并返回 config/profiles/<name>.json 的内容。"""
    profile_path = profiles_dir / f"{name}.json"
    if not profile_path.is_file():
        raise FileNotFoundError(f"未找到部署 profile: {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def build_store(store_cfg: dict[str, Any], *, root: Path = ROOT) -> MetricsStore:
    """按 profile 的 store 段造出存储后端实例。

    路径支持环境变量覆盖(向后兼容现网 systemd 的 Environment= 配置):
      - json_file: LATEST_SOFTWARES_METRICS_FILE > store.metrics_file
      - sql      : LATEST_SOFTWARES_STATS_DB     > store.db_path
    secret(TURSO_*)由 SqlMetricsStore.from_env 读环境变量,不进 profile。
    """
    kind = store_cfg.get("type")
    if kind == "json_file":
        metrics_file = os.environ.get(
            "LATEST_SOFTWARES_METRICS_FILE", store_cfg["metrics_file"]
        )
        return JsonFileMetricsStore(_resolve(metrics_file, root))
    if kind == "sql":
        db_path = os.environ.get("LATEST_SOFTWARES_STATS_DB", store_cfg["db_path"])
        return SqlMetricsStore.from_env(db_path=_resolve(db_path, root))
    raise ValueError(f"未知的 store.type: {kind!r}")


def build_app(
    name: str | None = None,
    *,
    root: Path = ROOT,
    profiles_dir: Path = PROFILES_DIR,
) -> FastAPI:
    """按 profile 名装配 app。name 缺省时取环境变量 APP_PROFILE,再缺省 intl。"""
    name = name or os.environ.get("APP_PROFILE", DEFAULT_PROFILE)
    profile = load_profile(name, profiles_dir=profiles_dir)
    store = build_store(profile["store"], root=root)

    data_file = _resolve(
        os.environ.get("LATEST_SOFTWARES_DATA_FILE", profile["data_file"]), root
    )

    # seed lifespan 仅当 sql 存储且 profile 指定 seed_file(国际版历史 workaround)。
    lifespan = None
    seed = profile["store"].get("seed_file")
    if isinstance(store, SqlMetricsStore) and seed:
        seed_path = _resolve(os.environ.get("LATEST_SOFTWARES_STATS_SEED", seed), root)

        @asynccontextmanager
        async def lifespan(_app: FastAPI):  # noqa: F811
            store.seed_if_empty(seed_path)
            yield

    serve_static = (root / "dist") if profile.get("serve_static") else None

    return create_app(
        edition=profile["edition"],
        store=store,
        data_file=data_file,
        serve_static_dir=serve_static,
        with_packages_endpoint=profile.get("packages_endpoint", False),
        log_events=profile.get("log_events", False),
        lifespan=lifespan,
        title=profile.get("title"),
        description=profile.get("description", ""),
    )

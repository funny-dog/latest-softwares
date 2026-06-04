"""Latest Softwares FastAPI Cloud 入口(国际版)。

职责:装配国际版 app —— 选 SqlMetricsStore(本地 SQLite 或远程 Turso)作为统计
存储,套用 app_core.create_app 提供的共享端点。端点/指标/edition 逻辑全部在
app_core 内,两版共享。

存储说明:
  serverless 容器(FastAPI Cloud)文件系统是临时的,本地 SQLite 不能跨冷启动/
  多实例持久。配置 TURSO_DATABASE_URL + TURSO_AUTH_TOKEN 后写远程 libSQL
  (跨实例持久);未配置则回退本地 SQLite。

部署说明:
  dist/ 被 .gitignore 忽略,通过 .fastapicloudignore 重新纳入 FastAPI Cloud。
  部署前需构建: python scripts/build_web.py --edition intl
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app_core.app_factory import create_app
from app_core.store import SqlMetricsStore

ROOT = Path(__file__).resolve().parent
DATA_FILE = Path(
    os.environ.get("LATEST_SOFTWARES_DATA_FILE", str(ROOT / "data" / "latest.json"))
)
DIST_DIR = ROOT / "dist"
DB_PATH = Path(
    os.environ.get("LATEST_SOFTWARES_STATS_DB", str(ROOT / "data" / "site_metrics.db"))
)
SEED_FILE = Path(
    os.environ.get(
        "LATEST_SOFTWARES_STATS_SEED", str(ROOT / "data" / "site_metrics.json")
    )
)

EDITION = "intl"

store = SqlMetricsStore.from_env(db_path=DB_PATH)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # 启动时从种子文件回填计数(仅当库为空)。接入 Turso 后基本是 no-op。
    store.seed_if_empty(SEED_FILE)
    yield


app = create_app(
    edition=EDITION,
    store=store,
    data_file=DATA_FILE,
    serve_static_dir=DIST_DIR,
    with_packages_endpoint=True,
    log_events=True,
    lifespan=_lifespan,
    title="Latest Softwares API (International)",
    description=(
        "Daily metadata sync for latest software releases, with a JSON API "
        "and static web frontend for the international edition."
    ),
)

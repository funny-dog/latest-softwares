"""Latest Softwares 国内版 API 后端入口(阿里云 VPS)。

由 systemd 跑 `uvicorn deploy.cn_server:app`,nginx 反代 /api/ → 127.0.0.1:8001。
装配国内版 app —— 选 JsonFileMetricsStore(持久文件)作为统计存储,套用
app_core.create_app 的共享端点。端点/指标/edition 逻辑全部在 app_core 内,与
国际版共享。

统计存储在【部署目录之外】(默认 /var/lib/latest-softwares/metrics.json),
不受 rsync --delete 影响;VPS 持久磁盘 + 单实例常驻,本地文件存储即可。

环境变量:
  LATEST_SOFTWARES_METRICS_FILE — 统计文件路径(默认 /var/lib/latest-softwares/metrics.json)
  LATEST_SOFTWARES_DATA_FILE    — 包数据文件路径(默认 data/latest.json)
"""

from __future__ import annotations

import os
from pathlib import Path

from app_core.app_factory import create_app
from app_core.store import JsonFileMetricsStore

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = Path(
    os.environ.get("LATEST_SOFTWARES_DATA_FILE", str(ROOT / "data" / "latest.json"))
)
STATS_FILE = Path(
    os.environ.get(
        "LATEST_SOFTWARES_METRICS_FILE", "/var/lib/latest-softwares/metrics.json"
    )
)

EDITION = "cn"

store = JsonFileMetricsStore(STATS_FILE)

# 国内版:静态文件由 nginx 服务(不挂 dist/),前端数据已内嵌(不需 /api/packages)。
app = create_app(
    edition=EDITION,
    store=store,
    data_file=DATA_FILE,
    title="Latest Softwares API (CN)",
    description="国内版访问统计与下载追踪 API",
)

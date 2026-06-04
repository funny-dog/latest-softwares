"""两个真实入口的装配 smoke 测试。

端点/存储的完整行为见 test_app_core.py。这里只验证 main.py(intl) 与
deploy/cn_server.py(cn) 各自装配出正确的 app —— 包括部署写死的 `app` 变量
仍然存在(main:app / deploy.cn_server:app 是部署入口点,不能丢)。
"""

from __future__ import annotations

import deploy.cn_server as cn_server
import main
from app_core.store import JsonFileMetricsStore, SqlMetricsStore

SHARED_PATHS = {
    "/api/health",
    "/api/visit",
    "/api/metrics",
    "/api/download/{package_id}/{platform}",
}


def _api_paths(app) -> set[str]:
    return {r.path for r in app.routes if getattr(r, "methods", None)}


def test_main_is_intl_assembly():
    assert main.EDITION == "intl"
    assert isinstance(main.store, SqlMetricsStore)
    paths = _api_paths(main.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" in paths  # intl 独有


def test_cn_server_is_cn_assembly():
    assert cn_server.EDITION == "cn"
    assert isinstance(cn_server.store, JsonFileMetricsStore)
    paths = _api_paths(cn_server.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" not in paths  # cn 不暴露

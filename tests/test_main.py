"""三个部署入口的装配 smoke 测试。

端点/存储完整行为见 test_app_core.py;装配逻辑见 test_app_builder.py。
这里只守住「部署锚点存在且契约正确」:
  - app:app                  —— 统一入口(默认 intl)
  - main:app                 —— FastAPI Cloud 锚点(intl)
  - deploy.cn_server:app     —— 现网 systemd 锚点(cn)
"""

from __future__ import annotations

import app as app_entry
import deploy.cn_server as cn_server
import main

SHARED_PATHS = {
    "/api/health",
    "/api/visit",
    "/api/metrics",
    "/api/download/{package_id}/{platform}",
}


def _api_paths(app) -> set[str]:
    return {r.path for r in app.routes if getattr(r, "methods", None)}


def test_main_is_intl_anchor():
    paths = _api_paths(main.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" in paths  # intl 独有


def test_cn_server_is_cn_anchor():
    paths = _api_paths(cn_server.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" not in paths  # cn 不暴露


def test_app_entry_defaults_to_intl():
    # app.py 未设 APP_PROFILE 时默认 intl
    paths = _api_paths(app_entry.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" in paths

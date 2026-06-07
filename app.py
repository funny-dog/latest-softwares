"""统一部署入口:按环境变量 APP_PROFILE 装配 app(缺省 intl)。

新部署目标只需:加一份 config/profiles/<name>.json + 设 APP_PROFILE=<name>,
进程指向 `app:app` 即可,无需新增 Python 入口。装配逻辑见 app_core.app_builder。
"""

from app_core.app_builder import build_app

app = build_app()

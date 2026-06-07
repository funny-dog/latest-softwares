"""国际版入口 —— FastAPI Cloud 部署锚点 `main:app`。

装配逻辑已统一到 app_core.app_builder;本文件只把锚点绑到 intl profile。
差异声明见 config/profiles/intl.json。
"""

from app_core.app_builder import build_app

app = build_app("intl")

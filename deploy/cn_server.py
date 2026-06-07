"""国内版入口 —— 阿里云现网 systemd 部署锚点 `deploy.cn_server:app`。

装配逻辑已统一到 app_core.app_builder;本文件只把锚点绑到 cn profile。
差异声明见 config/profiles/cn.json。保留本文件是为了「合并代码零运维动作」:
现网 systemd 仍按 deploy.cn_server:app 启动即可,迁移到统一 app:app 是可选项。
"""

from app_core.app_builder import build_app

app = build_app("cn")

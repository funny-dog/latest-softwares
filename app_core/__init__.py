"""国内版(阿里云 VPS)与国际版(FastAPI Cloud)共享的 Web API 内核。

设计目标:把两版后端相同的部分(端点契约、指标 schema、edition 过滤、统计读写
语义)抽到这里,差异只剩「存储后端」——由 store.MetricsStore 的不同实现吸收。

重要:本包【零外部仓库依赖】(不 import scripts/ 下任何模块),因为国内版后端的
部署 rsync 排除了 scripts/。__init__ 故意保持为空,避免 `import app_core` 触发
app_factory(进而 import fastapi)——让 editions/metrics 这类纯逻辑模块可被
sync/build 等轻量工具单独导入。
"""

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

每日自动抓取最新软件版本元数据，生成 README 并部署双版本网站（国内版 + 国际版）。不托管二进制文件，只提供下载链接。

## 核心命令

```bash
# 开发流程（固定顺序：sync → render）
python -m scripts.sync           # 抓取版本 → data/latest.json
python -m scripts.render         # 渲染模板 → README.md

# 构建前端
python scripts/build_web.py --edition intl   # 国际版
python scripts/build_web.py --edition cn     # 国内版

# 测试
pytest                           # 全部测试
pytest tests/test_sync.py        # 单个文件
pytest -k "test_name"            # 按名称匹配

# 本地运行国际版 API
uvicorn main:app --reload

# 配置校验
python scripts/validate_config.py
```

## Pre-commit Hooks

```bash
# 一次性安装 pre-commit hooks
pip install pre-commit && pre-commit install

# 手动运行所有 hooks
pre-commit run --all-files
```

## 架构要点

完整架构说明见 `AGENTS.md`，以下为 Claude Code 高频关注的要点：

- **唯一手动编辑的配置**：`packages/` 目录（软件清单，按版本拆分）。README.md 和 data/latest.json 都是自动生成的，不要手动修改。
- **fetcher 插件机制**：`scripts/fetchers/` 下按模块实现 `fetch(args) -> FetchResult`，在 `__init__.py` 的 `FETCHERS` 字典注册。90% 的软件用 `github_release` fetcher。
- **Edition 系统**：每个软件通过 `editions: [cn]` / `[intl]` / `[cn, intl]` 标记归属版本，过滤逻辑在 `scripts/editions.py`。
- **容错设计**：单个 fetcher 失败不影响其他软件，失败的沿用旧数据并标记 ⚠️。
- **自动发现管道**：`scripts/discover/`（入口 `python -m scripts.discover`）双周从 GitHub 高星 repo + winget/Scoop 交叉验证发现热门软件，自动生成条目追加到 `packages/shared.yaml` 并开 PR 供人工 review（`.github/workflows/discover.yml`，不自动合并）。详见 `AGENTS.md`。

## 编码注意事项

- Python 3.12（`.python-version`），最低兼容 3.10
- CI 运行在 `windows-latest`（Fido.ps1 硬要求 Windows），本地开发可在 macOS/Linux
- `sync.py` 和 `render.py` 开头将 stdout/stderr reconfigure 为 UTF-8（应对 Windows cp1252）
- 前端 vendor JS 本地化并 pin 版本，升级需改 `web/vendor/manifest.json` 后运行 `python scripts/update_vendor.py --update`

## 依赖管理

依赖精确 pin 在 `requirements.txt`。升级流程：改版本号 → 本地 pip install 验证 → 跑 pytest → 提交。

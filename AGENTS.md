# AGENTS.md — `latest-softwares`

## 仓库用途

由 GitHub Actions 每日自动从上游源抓取最新软件版本元数据，生成带下载链接的 README。**不托管二进制包**。

## 运行命令

```bash
# 推荐（包导入方式）
python -m scripts.sync      # 抓取版本 → data/latest.json
python -m scripts.render    # 渲染 Jinja2 模板 → README.md

# 备用（直接运行）
python scripts/sync.py
python scripts/render.py
```

运行顺序固定为 **sync → render**，render 依赖 sync 产出的 `data/latest.json`。

## 架构概览

```
packages.yaml          ← 用户编辑的"控制面板"（唯一手动修改的配置）
    ↓ scripts/sync.py  ← 派发到 fetcher，写出 data/latest.json
data/latest.json       ← 结构化抓取结果（schema_version: 1）
    ↓ scripts/render.py ← Jinja2 渲染
README.template.md     ← Jinja2 模板
    ↓
README.md              ← 最终产物（自动覆盖，禁止手动修改）
```

### Fetcher 插件

| fetcher | 文件 | 备注 |
|---------|------|------|
| `github_release` | `scripts/fetchers/github_release.py` | 最常用；支持 `tag_pattern` 过滤 monorepo |
| `windows11_fido` | `scripts/fetchers/windows11_fido.py` | 调用 `third_party/Fido.ps1`（PowerShell） |
| `vscode_official` | `scripts/fetchers/vscode.py` | 从 VSCode build manifest API 抓取 |
| `chrome_official` | `scripts/fetchers/chrome.py` | 版本号来自 versionhistory API，下载链接写死在 yaml |

新增 fetcher 需要两步：
1. 在 `scripts/fetchers/` 下创建 Python 模块，实现 `fetch(args) -> FetchResult`
2. 在 `scripts/fetchers/__init__.py` 的 `FETCHERS` 字典中注册

## 添加新软件

编辑 `packages.yaml`，在 `packages:` 列表末尾追加一项：

```yaml
  - id: powertoys
    name: PowerToys
    category: 通用工具
    fetcher: github_release
    args:
      repo: microsoft/PowerToys
      assets:
        - { platform: win-x64, pattern: "PowerToysUserSetup-*-x64.exe" }
```

- **90% 情况用 `github_release` fetcher**
- `tag_pattern`（正则）：用于 monorepo，如 Bitwarden 用 `^desktop-v`、Codex 用 `^rust-v`
- `assets[].pattern`：fnmatch 通配符（不是正则），匹配 GitHub Release asset 文件名

## CI 关键信息

- Runner：**必须 `windows-latest`**（`Fido.ps1` 做了 Windows 平台硬检查，非 Windows 直接 exit 403）
- 触发：每日 UTC 01:00 + `packages.yaml` / scripts 变更时 push 触发 + 手动 workflow_dispatch
- 权限：`contents: write`（auto-commit 回主分支）
- Token：通过 `GITHUB_TOKEN` 环境变量传入，提升 API 速率限制（5000/h vs 60/h）
- 流程：checkout → setup python → pip install → sync → render → auto-commit（`[skip ci]`）

## 编码与平台陷阱

- **Windows runner 默认 cp1252**：`sync.py` 和 `render.py` 都在最早时机把 `sys.stdout/stderr` reconfigure 为 UTF-8，否则中文/emoji 的 `print` 会 `UnicodeEncodeError` 崩掉整个脚本
- Fido 需要 `pwsh`（PowerShell Core 7+），且传 `-PlatformArch x64` 避免 WMI 调用在 Linux 上崩溃
- Windows 11 ISO 链接有效期约 24 小时，每天同步会刷新

## 容错机制

- 单个 software 的 fetcher 失败不会中断整体流程，其他软件继续
- 失败的软件复用上一次 `data/latest.json` 中的旧数据，并在 README 标记 ⚠️
- 退出码：仅全部失败时为 1，部分失败为 0

## 不要做的事

- **不要手动编辑 README.md**——每次同步都会被 `scripts/render.py` 覆盖
- **不要手动编辑 `data/latest.json`**——由 `scripts/sync.py` 自动生成
- 新增软件不要直接改 fetcher 代码——正确方式是在 `packages.yaml` 中添加配置项

## 依赖

- Python 3.10+，依赖见 `requirements.txt`（PyYAML, requests, Jinja2）
- `pwsh`（PowerShell Core）用于 Windows 11 ISO 抓取

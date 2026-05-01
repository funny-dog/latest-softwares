# 🚀 最新 Windows / macOS 软件速递

> 由 GitHub Actions 每日自动同步上游官方源的**最新版本元数据**。
> 仓库**不托管二进制安装包**，下载按钮直接跳到上游官方下载链接。
>
> 📅 **最后更新**：`{{ updated_at }}` (UTC)　{{ "·" if updated_at else "" }} 共 {{ total }} 项软件{% if failed > 0 %}（其中 {{ failed }} 项使用上次数据，标 ⚠️）{% endif %}

---

## 🌐 在线站点

- 站点：<https://latest-softwares-064facea.fastapicloud.dev/>

---

## 📦 软件清单

{% for category, items in grouped %}
### {{ category }}

| 软件 | 最新版本 | 发布日期 | 下载链接 | 来源 |
|------|---------|---------|---------|------|
{%- for it in items %}
| {% if it.homepage %}[**{{ it.name }}**]({{ it.homepage }}){% else %}**{{ it.name }}**{% endif %}{% if it._stale or it.warnings %} ⚠️{% endif %} | `{{ it.version }}` | {{ it.released_at | fmt_date }} | {% for a in it.assets %}[{{ a.platform }}]({{ a.url }}){% if not loop.last %} · {% endif %}{% endfor %} | {{ it.source }}{% if it._stale_reason %}<br>⚠ {{ it._stale_reason }}{% endif %}{% if it.warnings %}<br>⚠ {{ it.warnings | join("; ") }}{% endif %} |
{%- endfor %}

{% endfor %}

---

## 🔧 添加新软件

仓库的"控制面板"是根目录的 [`packages.yaml`](packages.yaml)。要加新软件，只需追加一项：

```yaml
  - id: powertoys                    # 唯一短标识
    name: PowerToys                  # 显示名
    category: 通用工具               # README 分组
    fetcher: github_release          # 抓取器（多数情况选这个）
    args:
      repo: microsoft/PowerToys
      assets:
        - { platform: win-x64, pattern: "PowerToysUserSetup-*-x64.exe" }
```

提交后定时任务（或 push 时立即触发）会在下次运行时自动抓取，README 表格里就会出现新行。

### 可用的 fetcher

| fetcher | 适用场景 | 关键 args 字段 | 版本号来源 | 下载链接 |
|---------|---------|--------------|----------|--------|
| `github_release` | GitHub Releases 发布的软件（**通用首选**） | `repo`、`assets[].{platform, pattern}` | Release tag | 直链（GitHub asset） |
| `vscode_official` | VS Code | `builds[].{platform, build}`（`build` 为 VSCode API 的 `platform.os`，如 `win32-x64-user`） | VSCode Build Manifest API | 直链 |
| `chrome_official` | Google Chrome | `platforms[].{platform, os_key, channel, download_url}` | Google Version History API | 取决于 `download_url` |
| `steam_official` | Steam 客户端 | `platforms[].{platform, download_url}` | Valve Client Update API（构建时间戳） | 取决于 `download_url` |
| `windows11_fido` | Windows 11 ISO | `lang`（默认 `Chinese (Simplified)`）、`edition`（默认 `Pro`）、`arch`（默认 `x64`） | ISO URL 解析（如 `24H2`） | 直链，约 24 h 有效 |
| `ubuntu_releases` | Ubuntu | `platforms[].{platform, pattern}` | Ubuntu releases index | 直链 |
| `fedora_releases` | Fedora Workstation | `platforms[].{platform, pattern}` | Fedora release directory | 直链 |
| `baidunetdisk` | 百度网盘 | `platforms[].{platform, download_url}` | 页面 `__V20_VER__`（构建日期，非客户端版本） | 取决于 `download_url` |
| `geek` | Geek Uninstaller | `platforms[].{platform, download_url}` | 官网 HTML 解析 | 取决于 `download_url` |
| `everything` | Everything 搜索 | `platforms[].{platform, download_url}` | 官网 HTML 解析 | 取决于 `download_url` |
| `wechat_official` | 微信 PC 客户端 | `platforms[].{platform, download_url}` | 官网 HTML 解析；失败时退为当天日期 | 取决于 `download_url` |
| `wegame_official` | WeGame | `platforms[].{platform, download_url?}`（可整体省略；缺 URL 时使用下载页） | 当天日期（SPA，无公开 API） | 固定跳转页 |
| `nvidia_app` | NVIDIA App | `platforms[].{platform, download_url?}`（可整体省略；缺 URL 时使用下载页） | 当天日期（SPA，无公开 API） | 固定跳转页 |
| `qq_official` | 腾讯 QQ（QQNT） | `platforms[].{platform, download_url?}`（可整体省略；缺 URL 时使用下载页） | 当天日期（SPA，无公开 API） | 固定跳转页 |
| `yy_official` | YY 语音 | `platforms[].{platform, download_url?}`（可整体省略；缺 URL 时使用下载页） | 当天日期（SPA，无公开 API） | 固定跳转页 |

**`github_release` 扩展参数**

- `tag_pattern`（正则）—— monorepo 场景，用正则从 release 列表中筛出目标子产品的 tag。
- `release_scan_pages`（整数，默认 `1`）—— 仅当 `tag_pattern` 存在时有意义，控制翻页深度（每页 30 个 release）。
- `warnings` —— 运行时字段，不在 yaml 中配置。当某个 platform 的 `pattern` 在当次 Release 的 assets 里未找到匹配文件时，该 platform 跳过并记入 `warnings`。

**直链 vs 跳转页**

系统根据 `download_url` 的路径后缀自动判断类型，无需手动标注：

- **直链**：URL 以 `.exe` / `.dmg` / `.iso` / `.zip` / `.tar.gz` / `.msi` / `.pkg` 等文件扩展名结尾，点击立即开始下载。Web 界面中对应**实心填充**徽章。
- **跳转页**：URL 指向一个下载网页（无文件后缀），点击后需在页面上再手动选择下载。Web 界面中对应**空心描边**徽章。

如 URL 后缀无法可靠判断，可在 `packages.yaml` 的 platform 配置中显式写 `link_kind: direct` 或 `link_kind: landing_page`。

**版本字段语义**

`data/latest.json` 每个软件条目都会写入 `version_kind` 和 `version_source`：

- `release_version`：上游发布版本号，例如 GitHub Release tag、官方 manifest。
- `release_label`：发行标签，例如 Windows 11 ISO 文件名中的 `25H2`。
- `build_date` / `page_date`：上游只暴露构建时间或页面更新时间时，展示为日期。
- `sync_date`：上游没有公开版本 API，只能确认下载入口，本字段表示本次同步日期。

当前数据契约版本为 `schema_version: 2`。

---

## ⚙️ 工作流

- **定时**：每日 UTC `01:00`（北京时间 09:00）
- **手动**：仓库 Actions 页面点 *Run workflow*
- **配置变更**：`packages.yaml` 改动 push 时立即触发

工作流文件：[`.github/workflows/sync.yml`](.github/workflows/sync.yml)

抓取结果原始数据：[`data/latest.json`](data/latest.json)

本地调试时可以只同步部分软件：

```bash
python -m scripts.sync --only vscode,chrome
python -m scripts.sync --skip windows11
python -m scripts.render
```

---

## 🤝 致谢

- [pbatard/Fido](https://github.com/pbatard/Fido) —— Windows ISO 直链生成器，GPL v3 协议
- 各软件上游官方源

> 本仓库由 GitHub Actions 自动维护，README 内容请勿手动修改（每次同步会被覆盖）。

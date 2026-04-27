# 🚀 最新 Windows / macOS 软件速递

> 由 GitHub Actions 每日自动同步上游官方源的**最新版本元数据**。
> 仓库**不托管二进制安装包**，下载按钮直接跳到上游官方下载链接。
>
> 📅 **最后更新**：`{{ updated_at }}` (UTC)　{{ "·" if updated_at else "" }} 共 {{ total }} 项软件{% if failed > 0 %}（其中 {{ failed }} 项使用上次数据，标 ⚠️）{% endif %}

---

## 📦 软件清单

{% for category, items in grouped %}
### {{ category }}

| 软件 | 最新版本 | 发布日期 | 下载链接 | 来源 |
|------|---------|---------|---------|------|
{%- for it in items %}
| {% if it.homepage %}[**{{ it.name }}**]({{ it.homepage }}){% else %}**{{ it.name }}**{% endif %}{% if it._stale or it.warnings %} ⚠️{% endif %} | `{{ it.version }}` | {{ it.released_at | fmt_date }} | {% for a in it.assets %}[{{ a.platform }}]({{ a.url }}){% if not loop.last %} · {% endif %}{% endfor %} | {{ it.source }}{% if it.warnings %}<br>⚠ {{ it.warnings | join("; ") }}{% endif %} |
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

| fetcher | 适用场景 | 必要参数 |
|---------|---------|---------|
| `github_release` | 任何在 GitHub Releases 发布的软件 | `repo`, `assets[].pattern`（fnmatch 通配符） |
| `windows11_fido` | Windows 11 ISO（微软官方下载页） | `lang`, `edition` |
| `vscode_official` | VS Code | `builds[].build`（如 `win32-x64-user`） |
| `chrome_official` | Google Chrome | `platforms[].os_key` + 固定 `download_url` |

monorepo（一个仓库发多个产品）可加 `tag_pattern` 正则筛选标签，如 Bitwarden 就用 `^desktop-v` 把 desktop 客户端的 release 挑出来。

---

## ⚙️ 工作流

- **定时**：每日 UTC `01:00`（北京时间 09:00）
- **手动**：仓库 Actions 页面点 *Run workflow*
- **配置变更**：`packages.yaml` 改动 push 时立即触发

工作流文件：[`.github/workflows/sync.yml`](.github/workflows/sync.yml)

抓取结果原始数据：[`data/latest.json`](data/latest.json)

---

## 🤝 致谢

- [pbatard/Fido](https://github.com/pbatard/Fido) —— Windows ISO 直链生成器，GPL v3 协议
- 各软件上游官方源

> 本仓库由 GitHub Actions 自动维护，README 内容请勿手动修改（每次同步会被覆盖）。

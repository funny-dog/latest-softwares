# 🚀 最新 Windows / macOS 软件速递

> 由 GitHub Actions 每日自动同步上游官方源的**最新版本元数据**。
> 仓库**不托管二进制安装包**，下载按钮直接跳到上游官方下载链接。
>
> 📅 **最后更新**：`2026-04-26 06:09:30` (UTC)　· 共 7 项软件（其中 1 项使用上次数据，标 ⚠️）

---

## 📦 软件清单


### 网络代理

| 软件 | 最新版本 | 发布日期 | 下载链接 | 来源 |
|------|---------|---------|---------|------|
| [**v2rayN**](https://github.com/2dust/v2rayN) | `7.20.4` | 2026-04-16 | [win-x64](https://github.com/2dust/v2rayN/releases/download/7.20.4/v2rayN-windows-64-desktop.zip) · [win-arm64](https://github.com/2dust/v2rayN/releases/download/7.20.4/v2rayN-windows-arm64-desktop.zip) · [mac-arm64](https://github.com/2dust/v2rayN/releases/download/7.20.4/v2rayN-macos-arm64.dmg) · [mac-x64](https://github.com/2dust/v2rayN/releases/download/7.20.4/v2rayN-macos-64.dmg) | GitHub Release: 2dust/v2rayN |


### 开发工具

| 软件 | 最新版本 | 发布日期 | 下载链接 | 来源 |
|------|---------|---------|---------|------|
| [**Visual Studio Code**](https://code.visualstudio.com) | `1.117.0` | 2026-04-21 | [win-x64](https://vscode.download.prss.microsoft.com/dbazure/download/stable/10c8e557c8b9f9ed0a87f61f1c9a44bde731c409/VSCodeUserSetup-x64-1.117.0.exe) · [win-arm64](https://vscode.download.prss.microsoft.com/dbazure/download/stable/10c8e557c8b9f9ed0a87f61f1c9a44bde731c409/VSCodeUserSetup-arm64-1.117.0.exe) · [mac-arm64](https://vscode.download.prss.microsoft.com/dbazure/download/stable/10c8e557c8b9f9ed0a87f61f1c9a44bde731c409/VSCode-darwin-arm64.dmg) · [mac-x64](https://vscode.download.prss.microsoft.com/dbazure/download/stable/10c8e557c8b9f9ed0a87f61f1c9a44bde731c409/VSCode-darwin-x64.dmg) | VSCode Build Manifest |
| [**OpenAI Codex**](https://github.com/openai/codex) | `0.125.0` | 2026-04-24 | [win-x64](https://github.com/openai/codex/releases/download/rust-v0.125.0/codex-x86_64-pc-windows-msvc.exe) · [win-arm64](https://github.com/openai/codex/releases/download/rust-v0.125.0/codex-aarch64-pc-windows-msvc.exe) · [mac-arm64](https://github.com/openai/codex/releases/download/rust-v0.125.0/codex-aarch64-apple-darwin.dmg) · [mac-x64](https://github.com/openai/codex/releases/download/rust-v0.125.0/codex-x86_64-apple-darwin.tar.gz) | GitHub Release: openai/codex |


### 浏览器

| 软件 | 最新版本 | 发布日期 | 下载链接 | 来源 |
|------|---------|---------|---------|------|
| [**Google Chrome**](https://www.google.com/chrome/) | `148.0.7778.56` | — | [win-x64](https://dl.google.com/chrome/install/standalonesetup64.exe) · [mac-arm64](https://dl.google.com/chrome/mac/stable/GGRO/googlechrome.dmg) | Google Version History API |


### 通用工具

| 软件 | 最新版本 | 发布日期 | 下载链接 | 来源 |
|------|---------|---------|---------|------|
| [**LocalSend**](https://localsend.org) | `1.17.0` | 2025-02-20 | [win-x64](https://github.com/localsend/localsend/releases/download/v1.17.0/LocalSend-1.17.0-windows-x86-64.exe) · [mac-arm64](https://github.com/localsend/localsend/releases/download/v1.17.0/LocalSend-1.17.0.dmg) | GitHub Release: localsend/localsend |
| [**Bitwarden Desktop**](https://bitwarden.com/download/) | `2026.3.1` | 2026-04-02 | [win-x64](https://github.com/bitwarden/clients/releases/download/desktop-v2026.3.1/Bitwarden-Installer-2026.3.1.exe) · [mac-universal](https://github.com/bitwarden/clients/releases/download/desktop-v2026.3.1/Bitwarden-2026.3.1-universal.dmg) | GitHub Release: bitwarden/clients |



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

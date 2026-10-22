# 软件来源配置漂移修复报告 (2026-10-23)

## 1. 概述与任务边界

针对 CI 审计快照中发现的 33 项 `_stale` 软件源异常及 `link-health.json` 中检测到的失效/未验证入口，按 `AGENTS.md` 规范与 Ponytail 最小完整改动原则进行了系统性修复。

共调整 40 个软件配置，涉及原 33 个 stale 软件中的 32 个；剩余 Ubuntu 为网络超时，不盲目改源，真实 CI 重试成功后 stale 为 0。目录 ID 与必收录平台覆盖保持。依据上游元数据与官方入口响应修正配置；HTTP 200、元数据抓取和 pattern 匹配不等于安装包已通过验证，实际质量由同快照 CI 门禁确认。

---

## 2. 已修复条目清单与证据

### 2.1 重点合规项：Docker Desktop 官方安装文档
根据主代理真实探测验证（证据文件 `/tmp/latest-softwares-ci-audit/docker-alternative-checks.json`，HTTP 200 `verified`），`docker-desktop` 统一切换至 Docker 官方跨平台安装文档入口，保留 `landing_page` 与 `mac-universal` 页面语义：
* **win-x64**: `https://docs.docker.com/desktop/setup/install/windows-install/`
* **mac-universal**: `https://docs.docker.com/desktop/setup/install/mac-install/`
* **linux-x64**: `https://docs.docker.com/desktop/setup/install/linux/`

### 2.2 资产命名模式漂移与多资产匹配收紧 (GitHub Release)
针对当次资产列表修正命名与歧义，关键变体匹配补回归 fixture。GitHub fetcher 新增 `{version}` 替换，使用 Release 已提取版本精确匹配，消除下列规则对版本位数的限制：

1. **Another Redis Desktop Manager (`another-redis-desktop-manager`)**:
   * 上游自 `v1.7.4` 调整了构建命名，系统标识移至版本号前：
     * `win-x64`: `Another-Redis-Desktop-Manager-win-*-x64.exe`
     * `mac-arm64`: `Another-Redis-Desktop-Manager-mac-*-arm64.dmg`
     * `mac-x64`: `Another-Redis-Desktop-Manager-mac-*-x64.dmg`
     * `linux-x64`: `Another-Redis-Desktop-Manager-linux-*-x86_64.AppImage`
2. **ClickHouse (`clickhouse`)**:
   * `linux-x64`: `clickhouse-common-static-[0-9]*-amd64.tgz`（精确排除 `clickhouse-common-static-dbg-*` 调试包）
3. **PowerShell (`powershell`)**:
   * `mac-arm64`: `powershell-[0-9]*-osx-arm64.pkg`（精确排除 `powershell-lts-*` 干扰）
   * `mac-x64`: `powershell-[0-9]*-osx-x64.pkg`（精确排除 `powershell-lts-*` 干扰）
4. **Rufus (`rufus`)**:
   * `win-x64`: `rufus-{version}.exe`，排除便携版及 ARM/x86 变体，不限制版本位数。
5. **ShareX (`sharex`)**:
   * `win-x64`: `ShareX-*-setup-x64.exe`（适配 `v21.0.0` 增加的 `-x64` 后缀并统一大小写）
6. **Transmission (`transmission`)**:
   * `win-x64`: `transmission-{version}-x64.msi`，排除 `-qt5-` 变体，不限制补丁版本位数。
7. **nvm-windows (`nvm-windows`)**:
   * `win-x64`: `nvm-*-x64-setup.exe`（上游 `v2.0.1` 弃用旧 `nvm-setup.exe`，按架构重命名）
8. **Obsidian (`obsidian`)**:
   * `linux-x64`: `Obsidian-{version}.AppImage`，排除 ARM64，不限制补丁版本位数。
9. **Sunshine (`sunshine`)**:
   * `win-x64`: `Sunshine-Windows-AMD64-installer.msi`（由 `.exe` 迁移至 `.msi`）
   * `win-x64-portable`: `Sunshine-Windows-AMD64-lite.zip`（命名由 `portable.zip` 改为 `lite.zip`）
   * `linux-x64`: `sunshine_*ubuntu24.04_amd64.deb`（适配包名前缀格式）
10. **Difftastic (`difftastic`)**:
    * 通用添加版本通配符：`difft-*-x86_64-pc-windows-msvc.zip`、`difft-*-aarch64-apple-darwin.tar.gz`、`difft-*-x86_64-unknown-linux-gnu.tar.gz`
11. **ImageGlass (`imageglass`)**:
    * `win-x64`: `ImageGlass_*_win-x64.msi`（上游 `10.0+` 引入 `win-` 架构标识）
12. **GE-Proton (`proton-ge`)**:
    * `linux-x64`: `GE-Proton*-x86_64.tar.gz`（收紧排除 `aarch64` 构建）
13. **xemu (`xemu`)**:
    * `win-x64`: `xemu-*[0-9]-windows-x86_64.zip`（排除 `-dbg-` 构建）
    * `mac-universal`: `xemu-[0-9]*-macos-universal.zip`（同步为通用包语义）
    * `linux-x64`: `xemu-*[0-9]-x86_64.AppImage`（排除 `-dbg-` 构建）
14. **OpenMW (`openmw`)**:
    * `win-x64`: `OpenMW-*-Windows-x64.exe`（大写与命名同步）
    * `mac-arm64`: `OpenMW-*-macOS-arm64.dmg`（同步 `macOS` 大写）
    * `linux-x64`: `openmw-*-Linux-64Bit.tar.gz`（排除 `-debug` 包）
15. **LocalSend (`localsend`)**:
    * `win-x64`: `LocalSend-[0-9]*-windows-x86-64.exe`（排除 `LocalSend-CLI-*`）
16. **Insomnia (`insomnia`)**:
    * `win-x64`: `Insomnia.Core-[0-9]*.exe`（排除 `Insomnia.Core-nsis-*`）
17. **KeePassXC (`keepassxc`)**:
    * `win-x64`: `KeePassXC-*-x64.msi`（上游 `2.8.0` 将 `Win64.msi` 改为 `x64.msi`）
18. **Telegram Desktop (`telegram`)**:
    * `win-x64`: `td-setup-win-x64-*.exe`（上游由 `tsetup.*.exe` 升级为 `td-setup-win-x64-*`）
19. **mihomo (`mihomo`)**:
    * `win-x64`: `mihomo-windows-amd64-v{version}.zip`，排除兼容/Go 工具链构建，不限制主版本位数。
20. **MarkText (`marktext`)**:
    * `win-x64`: `marktext-win-x64-*-setup.exe`（适配 `v0.23.0` 新架构命名）
21. **Audacity (`audacity`)**:
    * `win-x64`: `audacity-win-*-x86_64.msi`（Audacity 4 全面将 `.exe` 改用 `.msi`）
22. **mpv (`mpv`)**:
    * `win-x64`: `mpv-x86_64-[0-9]*-git-*.7z`（精确排除 `mpv-x86_64-v3-*` 兼容分支）
23. **Input Source Pro (`input-source-pro`)**:
    * `mac-universal`: `Input-Source-Pro-*.dmg`（点号分隔改为连字符分隔）
24. **Prometheus (`prometheus`)**:
    * 修正平台分隔符（点号）：`prometheus-*.linux-amd64.tar.gz`、`prometheus-*.darwin-arm64.tar.gz`、`prometheus-*.darwin-amd64.tar.gz`

### 2.3 无 Release 二进制分发项改用准确官方页面或 Manifest
部分上游仅以容器镜像、脚本或自有 CDN 分发，GitHub Release 资产常年为空或存在占位 tag，按规则优先复用可靠 manifest 或切换为官方落地页：
1. **Thorium Browser (`thorium`)**:
   * 当次 GitHub tag (`M156...`) 无二进制资产；切换至 `package_manifest` (provider: `scoop`, package: `extras/thorium`)。委派检查取得清单版本 `138.0.7204.303` 与下载 URL；这是 Scoop 清单版本，不宣称等于上游最新 tag。清单声明 SHA256，不代表本项目完整下载并验算过安装包。
2. **DevToys (`devtoys`)**:
   * 上游 v2.0 仍处 prerelease，最新正式版 `v1.0.13.0` 无 Mac 资产；切换为 `download_page` 指向 `https://devtoys.app`，完全覆盖 `coverage.json` 要求的 `mac-arm64` 与 `mac-x64`。
3. **Chatbox (`chatbox`)**:
   * 上游自建 CDN 分发客户端；切换为 `download_page` 指向官方页面 `https://chatboxai.app/` (HTTP 200)。
4. **容器/脚本服务类 (`sub-store`, `vaultwarden`, `n8n`, `appsmith`, `nocodb`)**:
   * 当次 Release 没有配置预期的二进制；切换至 `download_page` 指向官方 GitHub/官网安装入口，保留 sync_date 版本语义。抓取与链接结果由真实同步确认。

### 2.4 链接健康配置纠正 (Link Health)
1. **Ardour (`ardour`)**: 修正 404 URL 为官方标准下载页 `https://ardour.org/download.html` (HTTP 200)。
2. **Termius (`termius`)**: 修正 404 URL `https://termius.com/download/mac` 为官方入口 `https://termius.com/download/macos` (HTTP 200)。
3. **网易邮箱大师 (`netease-mail`)**: 修正下线旧链接 `mail.163.com/dashi/download.htm` 为官方主站 `https://dashi.163.com/` (HTTP 200)。
4. **bottom (`bottom`)**: 修复 404 落地页，改用真实 `ClementTsang/bottom` 的 `github_release`，直出多平台安装包。
5. **tealdeer (`tealdeer`)**: 修复 404 落地页，改用真实 `dbrgn/tealdeer` 的 `github_release`。
6. **navi-cli (`navi-cli`)**: 修复错配的 `midnight-commander/mc`（404 且身份错误），纠正为官方仓库 `denisidoro/navi`。

---

## 3. 未解决项及证据记录

以下条目因上游客观失效或外部网络防护，本次未做伪造或放宽，如实归档：

1. **FastGithub (`fastgithub`)**:
   * **证据**：检查返回 `https://github.com/dotnetcore/FastGithub` HTTP 404，不能仅凭响应推断封禁或删除原因。非必收录条目，本次未找到可核实的官方替代。
2. **QQ影音 (`qqplayer`)**:
   * **证据**：当次检查 `https://player.qq.com/` 返回 HTTP 404；本次未找到可核实的替代官方下载入口，不推断产品永久下线。
3. **酷我音乐 (`kuwo-music`)**:
   * **证据**：官方下载页面 `https://www.kuwo.cn/download` 在外部探测时持续返回 HTTP 500 Internal Server Error，需等待服务商上游自身修复。
4. **部分受限域名 (`apifox`, `adobe-photoshop`)**:
   * **证据**：`apifox.com/download/` 自动请求返回 403；`adobe.com/products/photoshop.html` 返回 403，为已有声明式长期豁免项。均不标为可用下载。

---

## 4. 验证与回归测试

首次整合 CI 的不可用入口从 67 降到 49，但阿里云盘的 SPA 页面没有静态下载证据，正确阻止了发布。因此补充 `aliyundrive_official`：只读取官方页面 `Global` 中三个明确的客户端 URL 字段，限定官方 CDN、版本文件名与架构后缀，不执行 JavaScript；拒绝缺失、重复、不同版本或不可信下载域名。版本从客户端文件名取得，不把页面里无关的 `latest_version: V2.1.7` 当客户端版本。配置增加官方已有的 Mac ARM64 安装包。

本地真实取得 6.9.3 的 Windows、Mac Intel、Mac ARM64 URL，三者均通过项目的有界下载验证（HTTP 206，检查响应与文件类型/平台线索），未完整下载安装包。证据保存在 `/tmp/latest-softwares-ci-audit/aliyundrive-client-checks.json`。新增回归及相关 fetcher/配置/同步/工作流测试 55 passed。

新增专用回归测试文件 `tests/test_catalog_source_repairs.py`，测试涵盖：
1. Docker Desktop 官方三平台安装文档配置校验；
2. Rufus、Transmission、Obsidian 的实际变体及多位版本回归；
3. ClickHouse、PowerShell、LocalSend、Insomnia、GE-Proton、xemu、mihomo、mpv 排除中间构建/调试包唯一匹配；
4. KeePassXC、Telegram、Audacity、ShareX、nvm-windows、Sunshine、ImageGlass、MarkText、Input Source Pro 上游更名校验；
5. Thorium (Scoop manifest) 与 DevToys/服务类落地页逻辑校验。

运行命令：
```bash
.venv/bin/pytest tests/test_catalog_source_repairs.py
```
整合后的定向配置验收：`tests/test_catalog_source_repairs.py tests/test_catalog.py tests/test_validate_config.py` 共 39 passed；另通过全目录配置验证。`{version}` 的真实 fetcher 单测验证版本替换及错误变体排除。

---

## 5. 续批：redirect host 复核（2026-10-23 发布验收后）

针对 `link-state` 中 6 条 `redirect host needs review` 逐条核对最终跳转域名，改用经官方跳转确认的稳定入口，未使用通配符放开域名：

| 软件 | 原入口 | 实际跳转 | 处理 |
|---|---|---|---|
| ardour | `ardour.org/download.html` | `community.ardour.org/download` | 入口改为 https 社区下载页 |
| teracopy | `www.codesector.com/teracopy` | `codesector.com/teracopy` | 入口改为 apex 域 |
| xmind | `xmind.app/download/` | `xmind.com:443` | 入口与主页改为 `xmind.com/download/` |
| tor-browser | `www.torproject.org/download/` | `download.torproject.org/` | 保留官方入口，`allowed_hosts` 精确放行官方下载域 |
| skype | `www.skype.com/get-skype/` | `teams.live.com/free?source=skype` | 微软已停止 Skype 下载，入口改为 Teams 免费版官方页并同步说明 |
| kimi | `kimi.moonshot.cn/download` | `www.kimi.com`（SPA） | 静态 HTML 无下载词条，未找到可核实直链，保持 unverified |

同批复查 5 条网络类失败：`crystaldiskinfo`、`crystaldiskmark`、`cajviewer` 本地实测已 `verified`，CI 中为瞬时超时，无需改配置；`potplayer-cn` 仍报 SSLError、`quark` 需在 CI 网络复核，本批未改配置。

验收：`validate_config` 通过；5 个改动条目共 10 个平台入口以项目验证器实测 `verified`；`tests/test_validate_config.py tests/test_catalog.py` 22 passed。

# 国际版软件扩容策略

## 目标规模

国际版不追求覆盖所有软件仓库，而是维护一个可信、可同步、可验证的热门软件目录。当前目标规模是 **350 个左右**，硬上限暂定 **400 个**。

这样做的原因：

- Ninite 这类同类精选工具覆盖的是常用软件集合，而不是完整包仓库。
- winget、Chocolatey、Scoop 是上千到上万级包仓库，适合作为候选来源，不适合全量照搬。
- 本仓库每天自动同步、渲染和部署，条目过多会提高上游失败率、链接失效率、GitHub API 压力和页面噪音。

## 候选来源优先级

1. **Ninite**：用来识别普通用户常装软件和分类缺口。参考：`https://ninite.com/`
2. **Microsoft winget-pkgs**：用来确认 Windows 生态里是否有稳定发布者、安装器和元数据。参考：`https://github.com/microsoft/winget-pkgs`
3. **Chocolatey Community Repository**：用下载量和搜索结果辅助判断流行度，但不直接信任历史下载量。参考：`https://community.chocolatey.org/packages`
4. **Scoop Main / Extras**：用来补开发者工具、CLI、便携工具和开源 GUI。参考：`https://github.com/ScoopInstaller/Main`、`https://github.com/ScoopInstaller/Extras`
5. **官方主页 / 厂商下载页 / GitHub Releases**：最终落库时必须回到发布者官方源。

## 收录标准

优先收录：

- 普通用户、开发者或企业装机高频软件。
- 官方站点提供稳定下载页或 GitHub Releases 的软件。
- 多平台软件，或者 Windows/macOS 用户明显需要的软件。
- 对国内版不合适、但国际版用户常用的软件。

谨慎收录：

- 只有第三方镜像、下载站或论坛分发的软件。
- 发布资产命名频繁漂移，无法稳定匹配 GitHub Release asset 的软件。
- 历史下载量高但已过时的软件，例如旧运行时、旧插件、废弃浏览器插件。
- 需要登录、付费订阅或地区跳转后才能下载的软件。可以收录官方下载页，但不要伪装成直链。

不收录：

- 破解、补丁、激活工具、规避授权的软件。
- 纯网页服务且没有明确桌面客户端的软件。
- 浏览器扩展、移动端专用应用、商店内无法稳定公开下载的应用。
- 非官方 fork，除非 fork 本身已经成为事实上的主维护版本。

## Fetcher 选择

优先级：

1. `github_release`：适合开源项目，能拿到 release version、发布时间、资产文件名。
2. 专用 official fetcher：适合 Chrome、Firefox、VSCode、Node.js 这类有稳定 API 的项目。
3. `download_page`：适合商业软件和官方下载页稳定、但没有公共版本 API 的软件。

`download_page` 的版本语义是同步日期，不是软件真实版本。使用时必须满足：

- `homepage` 和 `download_url` 都指向官方域名。
- 如果不是实际安装包直链，`link_kind` 必须是 `landing_page`。
- `source` 说明清楚“无公共版本 API”。

## 当前补充批次

本轮把国际版从 310 个补到 350 个，重点补普通用户和企业常装软件，而不是继续堆开发者 CLI：

| 类别 | 新增方向 |
| --- | --- |
| Browsers | Edge、Opera、Vivaldi、Tor Browser、LibreWolf、Mullvad Browser |
| Messaging | Teams、WhatsApp、Thunderbird、Skype |
| Productivity | LibreOffice、Zotero、Notion、Figma、Dropbox、Google Drive、OneDrive、Foxit Reader |
| Security & Privacy | 1Password、Proton VPN、Malwarebytes、AdGuard |
| Developer Tools | Docker Desktop、Postman、Cursor、JetBrains Toolbox、VirtualBox |
| Network & Proxy | Wireshark、WinSCP、FileZilla |
| System Utilities / Utilities | Sysinternals Suite、WinRAR、WizTree、TeraCopy、AnyDesk、TeamViewer |
| Media / Gaming | Kodi、Plex Media Server、foobar2000、Epic Games Launcher |

## 后续扩容流程

每批最多 20-30 个，除非只是补齐明显缺口。推荐流程：

```bash
python -m scripts.validate_config
python -m scripts.sync --edition intl --only <comma-separated-new-ids>
python -m scripts.render --edition intl
python -m scripts.build_web --edition intl
python -m scripts.validate_links --edition intl
ruff check .
pytest
```

新增 GitHub Release 软件时，先用 GitHub API 或 `python -m scripts.sync --only <id>` 验证 asset pattern，确认至少一个平台能匹配。新增 `download_page` 软件时，优先跑链接校验，确认官方页没有明显 404、证书或跳转错误。

## 下一批候选池

暂不立即收录，但可以作为后续候选：

- Office / notes：Evernote、OnlyOffice Desktop Editors、Apache OpenOffice、WPS Office international
- Design / creative：DaVinci Resolve、Affinity apps、Paint.NET、IrfanView、XnView MP
- Dev / cloud：minikube、kind、Podman Desktop、Lens Desktop、GitKraken、Sourcetree
- Security：NordVPN、Bitdefender、ESET、Sophos Home
- Remote / support：RealVNC、RustDesk 已收录，后续可评估 Splashtop、Parsec
- Gaming launchers：Battle.net、EA app、GOG Galaxy、Ubisoft Connect

下一批应该优先补“官方源可验证 + 当前分类明显偏少”的软件，不按数量目标盲目扩张。

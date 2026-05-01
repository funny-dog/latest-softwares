[English](README.md) | [中文](README_zh.md)

# 🚀 Latest Windows / macOS Software Releases

> **Latest version metadata** automatically synced from official upstream sources daily by GitHub Actions.
> This repository **does not host binary installers** — download buttons link directly to upstream official downloads.
>
> 📅 **Last updated**: `2026-05-01 18:58:34` (UTC) · 2 software items

---

## 🌐 Live Site

- Site: <https://latest-softwares-064facea.fastapicloud.dev/>

---

## 📦 Software List


### Browsers

| Software | Latest Version | Released | Download | Source |
|----------|---------------|----------|----------|--------|
| [**Mozilla Firefox**](https://www.mozilla.org/firefox/new/) | `150.0.1` | — | [win-x64](https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=en-US) · [mac-universal](https://download.mozilla.org/?product=firefox-latest-ssl&os=osx&lang=en-US) · [linux-x64](https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US) | Mozilla product-details API |
| [**Google Chrome**](https://www.google.com/chrome/) | `148.0.7778.97` | — | [win-x64](https://dl.google.com/chrome/install/standalonesetup64.exe) · [mac-arm64](https://dl.google.com/chrome/mac/stable/GGRO/googlechrome.dmg) | Google Version History API |



---

## 🔧 Adding New Software

The project's "control panel" is the [`packages/`](packages/) directory. To add a new software item, simply append an entry to the appropriate yaml file:

```yaml
  - id: powertoys                    # unique slug
    name: PowerToys                  # display name
    category: Utilities              # README grouping
    fetcher: github_release          # fetcher plugin (this one works for most)
    args:
      repo: microsoft/PowerToys
      assets:
        - { platform: win-x64, pattern: "PowerToysUserSetup-*-x64.exe" }
```

After committing, the scheduled task (or an immediate push trigger) will pick it up on the next run, and the new row will appear in the README table.

### Available Fetchers

| Fetcher | Use Case | Key `args` Fields | Version Source | Download Link |
|---------|----------|-------------------|----------------|---------------|
| `github_release` | Software published via GitHub Releases (**default choice**) | `repo`, `assets[].{platform, pattern}` | Release tag | Direct (GitHub asset) |
| `vscode_official` | VS Code | `builds[].{platform, build}` (`build` is VSCode API `platform.os`, e.g. `win32-x64-user`) | VSCode Build Manifest API | Direct |
| `chrome_official` | Google Chrome | `platforms[].{platform, os_key, channel, download_url}` | Google Version History API | Depends on `download_url` |
| `steam_official` | Steam client | `platforms[].{platform, download_url}` | Valve Client Update API (build timestamp) | Depends on `download_url` |
| `windows11_fido` | Windows 11 ISO | `lang` (default `Chinese (Simplified)`), `edition` (default `Pro`), `arch` (default `x64`) | ISO URL parsing (e.g. `25H2`) | Direct, ~24h expiry |
| `ubuntu_releases` | Ubuntu | `platforms[].{platform, pattern}` | Ubuntu releases index | Direct |
| `fedora_releases` | Fedora Workstation | `platforms[].{platform, pattern}` | Fedora release directory | Direct |
| `baidunetdisk` | Baidu Netdisk | `platforms[].{platform, download_url}` | Page `__V20_VER__` (build date, not client version) | Depends on `download_url` |
| `geek` | Geek Uninstaller | `platforms[].{platform, download_url}` | Official HTML parsing | Depends on `download_url` |
| `everything` | Everything Search | `platforms[].{platform, download_url}` | Official HTML parsing | Depends on `download_url` |
| `wechat_official` | WeChat PC | `platforms[].{platform, download_url}` | Official HTML parsing; falls back to today's date | Depends on `download_url` |
| `wegame_official` | WeGame | `platforms[].{platform, download_url?}` (can be omitted entirely) | Today's date (SPA, no public API) | Fixed redirect page |
| `nvidia_app` | NVIDIA App | `platforms[].{platform, download_url?}` (can be omitted entirely) | Today's date (SPA, no public API) | Fixed redirect page |
| `qq_official` | Tencent QQ (QQNT) | `platforms[].{platform, download_url?}` (can be omitted entirely) | Today's date (SPA, no public API) | Fixed redirect page |
| `yy_official` | YY Voice | `platforms[].{platform, download_url?}` (can be omitted entirely) | Today's date (SPA, no public API) | Fixed redirect page |

**`github_release` Extended Parameters**

- `tag_pattern` (regex) — For monorepos, filters release tags to find the target sub-product.
- `release_scan_pages` (integer, default `1`) — Only meaningful with `tag_pattern`; controls pagination depth (30 releases per page).
- `warnings` — Runtime field, not configured in yaml. When a platform's `pattern` doesn't match any asset in the release, that platform is skipped and recorded in `warnings`.

**Direct Links vs Landing Pages**

The system automatically determines link type from the `download_url` file extension:

- **Direct**: URL ends with `.exe` / `.dmg` / `.iso` / `.zip` / `.tar.gz` / `.msi` / `.pkg` etc., download starts immediately. Shown as **filled badges** in the web UI.
- **Landing page**: URL points to a download webpage (no file extension), user must manually click download on that page. Shown as **outlined badges** in the web UI.

If the URL extension cannot be reliably determined, explicitly set `link_kind: direct` or `link_kind: landing_page` in the platform config in `packages/`.

**Version Field Semantics**

Each entry in `data/latest.json` includes `version_kind` and `version_source`:

- `release_version`: Upstream release version, e.g. GitHub Release tag, official manifest.
- `release_label`: Release label, e.g. `25H2` from Windows 11 ISO filename.
- `build_date` / `page_date`: When upstream only exposes a build time or page update date.
- `sync_date`: Upstream has no public version API; this field indicates the sync date.

Current data contract version: `schema_version: 2`.

---

## ⚙️ Workflow

- **Scheduled**: Daily at UTC `01:00` (Beijing time 09:00)
- **Manual**: Run workflow from the Actions page
- **Config changes**: Triggered immediately on `packages/` push

Workflow file: [`.github/workflows/sync.yml`](.github/workflows/sync.yml)

Raw fetched data: [`data/latest.json`](data/latest.json)

For local debugging, you can sync only specific packages:

```bash
python -m scripts.sync --only vscode,chrome
python -m scripts.sync --skip windows11
python -m scripts.render
```

---

## 🤝 Credits

- [pbatard/Fido](https://github.com/pbatard/Fido) — Windows ISO direct link generator, GPL v3
- All upstream official sources

> This repository is maintained automatically by GitHub Actions. README content is auto-generated — do not edit manually (overwritten on each sync).

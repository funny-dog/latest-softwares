# 🚀 Latest Windows / macOS Software Releases

> **Latest version metadata** automatically synced from official upstream sources daily by GitHub Actions.
> This repository **does not host binary installers** — download buttons link directly to upstream official downloads.
>
> 📅 **Last updated**: `{{ updated_at }}` (UTC){{ " · " if updated_at else "" }}{{ total }} software items{% if failed > 0 %} ({{ failed }} using previous data, marked ⚠️){% endif %}

---

## 🌐 Live Site

- Site: <https://latest-softwares-064facea.fastapicloud.dev/>
- Health check: <https://latest-softwares-064facea.fastapicloud.dev/api/health>
- Packages API: <https://latest-softwares-064facea.fastapicloud.dev/api/packages>

The web page sends a visit beacon to `/api/visit`; download buttons first hit `/api/download/{package_id}/{platform}` then 302-redirect to the upstream official URL. This repository does not host any binaries.

---

## 📦 Software List

{% for category, items in grouped %}
### {{ category }}

| Software | Latest Version | Released | Download | Source |
|----------|---------------|----------|----------|--------|
{%- for it in items %}
| {% if it.homepage %}[**{{ it.name }}**]({{ it.homepage }}){% else %}**{{ it.name }}**{% endif %}{% if it._stale or it.warnings %} ⚠️{% endif %} | `{{ it.version }}` | {{ it.released_at | fmt_date }} | {% for a in it.assets %}[{{ a.platform }}]({{ a.url }}){% if not loop.last %} · {% endif %}{% endfor %} | {{ it.source }}{% if it._stale_reason %}<br>⚠ {{ it._stale_reason }}{% endif %}{% if it.warnings %}<br>⚠ {{ it.warnings | join("; ") }}{% endif %} |
{%- endfor %}

{% endfor %}

---

## 🔧 Adding New Software

The project's "control panel" is [`packages.yaml`](packages.yaml) in the repository root. To add a new software item, simply append an entry:

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

If the URL extension cannot be reliably determined, explicitly set `link_kind: direct` or `link_kind: landing_page` in the platform config in `packages.yaml`.

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
- **Config changes**: Triggered immediately on `packages.yaml` push

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

# 自动发现热门软件 → 开 PR 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 定时（双周）从 GitHub + winget + Scoop 多源交叉发现热门国际软件，自动推断 Windows 资产 pattern、翻译描述、生成条目并开 PR 供人工审核。

**Architecture:** 新建 `scripts/discover/` 包，复用现有 `scripts/fetchers/` 的插件风格与 `scripts/net.py` 的 HTTP 层。核心是可独立运行的 CLI（`discover_popular.py`），GitHub Action 仅定时调用。GitHub 提供热度（star）+ release 资产；winget/Scoop 通过 **GitHub Code Search** 佐证（在其仓库里搜候选的 `github.com/owner/repo` 字符串）。

**Tech Stack:** Python 3.10+、`requests`（已 pin 2.33.1）、`PyYAML`（已 pin 6.0.3）、pytest + monkeypatch、GitHub Actions、`peter-evans/create-pull-request`。无需新增运行时依赖。

---

## 设计相对 spec 的两处实现细化

1. **winget.py + scoop.py 合并为 `sources/corroborate.py`**：二者机制相同（GitHub Code Search 搜 repo URL），DRY。
2. **佐证从"预拉全量 manifest 集合"改为"按候选 code search"**：等价于 spec 的"repo 身份交叉验证"，但 API 调用量从"全量"降到"≤候选数"，且 asset 推断 + 去重之后才做，进一步压缩调用。

## 文件结构

```
scripts/discover/
  __init__.py          # 空包标记
  models.py            # Candidate 数据类 + 常量（PLACEHOLDER_DESC_CN 等）
  asset_infer.py       # infer_windows_pattern（最高风险纯逻辑）
  categorize.py        # categorize（纯逻辑）
  dedup.py             # existing_repos / is_new（读 config_loader）
  translate.py         # translate_to_zh（MyMemory，HTTP）
  generate.py          # slugify / build_entry（纯逻辑）
  yaml_writer.py       # append_entries（追加写 shared.yaml，保证干净 diff）
  aggregate.py         # select_candidates（编排：过滤+排序+截断）
  sources/
    __init__.py        # 空包标记
    github.py          # discover（GitHub Search + latest release，HTTP）
    corroborate.py     # corroborated_by_winget / corroborated_by_scoop（Code Search，HTTP）
scripts/discover_popular.py   # CLI 入口
.github/workflows/discover.yml
tests/test_discover_asset_infer.py
tests/test_discover_categorize.py
tests/test_discover_dedup.py
tests/test_discover_translate.py
tests/test_discover_generate.py
tests/test_discover_github.py
tests/test_discover_corroborate.py
tests/test_discover_aggregate.py
tests/test_discover_cli.py
```

**导入深度提示**（易错点）：
- `scripts/discover/*.py`（包 `scripts.discover`）：`from ..net import ...`、`from ..config_loader import ...`、`from ..validate_config import validate_config`
- `scripts/discover/sources/*.py`（包 `scripts.discover.sources`）：`from ...net import ...`（三个点）

---

## Task 1：包骨架 + 数据模型

**Files:**
- Create: `scripts/discover/__init__.py`
- Create: `scripts/discover/sources/__init__.py`
- Create: `scripts/discover/models.py`
- Test: `tests/test_discover_generate.py`（本任务先建占位，Task 6 补全；此处仅验证 models 可导入）

- [ ] **Step 1: 写 models.py**

```python
"""discover 包公共数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field

# 翻译失败时的 desc_cn 占位符（人工 review 时替换）
PLACEHOLDER_DESC_CN = "TODO: 待人工补充中文描述"

# CLI 默认参数
DEFAULT_MIN_STARS = 5000
DEFAULT_MAX_OUTPUT = 10
DEFAULT_MAX_SCAN = 100        # 最多扫描多少个高星 repo
DEFAULT_MAX_CORROBORATE = 30  # 最多对多少候选做 code search 佐证


@dataclass
class Candidate:
    repo: str                       # owner/repo
    name: str                       # 显示名（默认取 repo 名）
    stars: int
    description: str                # repo 描述，可能为空串
    topics: list[str] = field(default_factory=list)
    asset_names: list[str] = field(default_factory=list)  # latest release 资产文件名
    released_at: str | None = None

    @property
    def homepage(self) -> str:
        return f"https://github.com/{self.repo}"
```

- [ ] **Step 2: 建空 `__init__.py`**

`scripts/discover/__init__.py` 与 `scripts/discover/sources/__init__.py` 均为空文件（包标记）。

- [ ] **Step 3: 写最小导入测试**

`tests/test_discover_generate.py`：
```python
from __future__ import annotations

from scripts.discover.models import Candidate, PLACEHOLDER_DESC_CN


def test_candidate_homepage_derived_from_repo():
    c = Candidate(repo="pbatard/rufus", name="rufus", stars=29000, description="USB tool")
    assert c.homepage == "https://github.com/pbatard/rufus"
    assert PLACEHOLDER_DESC_CN.startswith("TODO")
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_discover_generate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/__init__.py scripts/discover/sources/__init__.py scripts/discover/models.py tests/test_discover_generate.py
git commit -m "feat(discover): 新增 discover 包骨架与 Candidate 数据模型"
```

---

## Task 2：asset_infer（最高风险）

从 release 资产文件名推断 Windows x64 安装包的 glob pattern。

**Files:**
- Create: `scripts/discover/asset_infer.py`
- Test: `tests/test_discover_asset_infer.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from scripts.discover.asset_infer import infer_windows_pattern


def test_picks_windows_installer_and_globs_version():
    names = [
        "OBS-Studio-30.1.2-Windows-Installer.exe",
        "OBS-Studio-30.1.2-macOS-Apple.dmg",
        "OBS-Studio-30.1.2-Ubuntu-x86_64.deb",
    ]
    assert infer_windows_pattern(names) == "OBS-Studio-*-Windows-Installer.exe"


def test_prefers_x64_when_multiple_windows_assets():
    names = [
        "app-1.2.3-win-arm64.exe",
        "app-1.2.3-win-x64.exe",
    ]
    assert infer_windows_pattern(names) == "app-*-win-x64.exe"


def test_rejects_when_no_windows_asset():
    names = ["app-1.2.3-linux-x86_64.AppImage", "app-1.2.3-macos.dmg"]
    assert infer_windows_pattern(names) is None


def test_rejects_empty():
    assert infer_windows_pattern([]) is None


def test_msi_setup_recognized():
    names = ["Setup-2024.10.0.msi", "source-2024.10.0.tar.gz"]
    assert infer_windows_pattern(names) == "Setup-*.msi"


def test_zip_only_counts_with_windows_marker():
    # 纯 zip 无 windows 标记 → 拒绝（避免误抓源码包）
    assert infer_windows_pattern(["project-1.0.0.zip"]) is None
    assert infer_windows_pattern(["project-1.0.0-windows-x64.zip"]) == (
        "project-*-windows-x64.zip"
    )
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_asset_infer.py -v`
Expected: FAIL（`ModuleNotFoundError: scripts.discover.asset_infer`）

- [ ] **Step 3: 写实现**

```python
"""从 GitHub release 资产名推断 Windows x64 安装包的 glob pattern。

宁缺毋滥：推不出唯一可信资产时返回 None，让上层跳过该候选，
避免生成会导致 sync 失败的条目。
"""

from __future__ import annotations

import re

# 命中 Windows 的标记词
_WIN_TOKENS = ("windows", "win64", "win32", "win", "x64", "amd64", "x86_64", "setup", "installer")
# 明确排除的非 Windows / 非 x64 标记
_EXCLUDE_TOKENS = (
    "arm64", "aarch64", "armv7", "arm",
    "linux", "ubuntu", "debian", "fedora", ".deb", ".rpm", ".appimage",
    "mac", "macos", "osx", "darwin", ".dmg", ".pkg",
    "android", ".apk", "ios",
    "x86.exe", "ia32", "i686", "32bit", "win32",
)
# Windows 可执行安装扩展名
_WIN_EXTS = (".exe", ".msi")
# 版本号正则：优先匹配 a.b / a.b.c 形式，其次纯长数字串
_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")
_LONGNUM_RE = re.compile(r"\d{4,}")


def _has_token(name: str, tokens: tuple[str, ...]) -> bool:
    return any(t in name for t in tokens)


def _is_windows_asset(lower: str) -> bool:
    """判断单个资产是否是 Windows x64 安装包候选。"""
    if _has_token(lower, _EXCLUDE_TOKENS):
        return False
    if lower.endswith(_WIN_EXTS):
        return True
    if lower.endswith(".zip") and _has_token(lower, ("windows", "win64", "win", "x64", "amd64")):
        return True
    return False


def _score(lower: str) -> int:
    """分数越高越像"主 Windows x64 安装包"。"""
    score = 0
    if lower.endswith(".exe"):
        score += 3
    if lower.endswith(".msi"):
        score += 2
    if "setup" in lower or "installer" in lower:
        score += 2
    if "x64" in lower or "amd64" in lower or "x86_64" in lower or "win64" in lower:
        score += 2
    if "windows" in lower or "win" in lower:
        score += 1
    return score


def _globify_version(name: str) -> str:
    """把文件名里的版本号子串替换为 *。"""
    if _VERSION_RE.search(name):
        return _VERSION_RE.sub("*", name)
    if _LONGNUM_RE.search(name):
        return _LONGNUM_RE.sub("*", name)
    return name


def infer_windows_pattern(asset_names: list[str]) -> str | None:
    """返回 Windows x64 资产的 glob pattern；推不出则 None。"""
    scored: list[tuple[int, str]] = []
    for name in asset_names:
        lower = name.lower()
        if _is_windows_asset(lower):
            scored.append((_score(lower), name))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    # 最高分若与次高分并列且文件名差异大，仍取最高分第一个（确定性）
    best_name = scored[0][1]
    return _globify_version(best_name)
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_asset_infer.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/asset_infer.py tests/test_discover_asset_infer.py
git commit -m "feat(discover): 新增 Windows 资产 pattern 自动推断"
```

---

## Task 3：categorize

**Files:**
- Create: `scripts/discover/categorize.py`
- Test: `tests/test_discover_categorize.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from scripts.discover.categorize import categorize


def test_browser_keyword():
    assert categorize(["browser", "web"], "A privacy browser") == "Browsers"


def test_dev_tools_keyword():
    assert categorize(["cli", "git"], "Developer command-line tool") == "Developer Tools"


def test_ai_keyword():
    assert categorize([], "Local LLM inference engine") == "AI Tools"


def test_fallback_to_utilities():
    assert categorize([], "Some unclassifiable thing") == "Utilities"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_categorize.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""把 GitHub topics + 描述关键词映射到现有 category 取值。

现有 category（来自 packages/*.yaml 实际统计）：
Developer Tools / System Utilities / Utilities / Productivity / Media Players /
Network & Proxy / Gaming / AI Tools / Messaging / Browsers /
Security & Privacy / Cloud & DevOps / Operating Systems / Download Tools
"""

from __future__ import annotations

# 顺序即优先级：靠前的先命中
_KEYWORD_CATEGORY: list[tuple[tuple[str, ...], str]] = [
    (("browser", "chromium", "webkit"), "Browsers"),
    (("llm", "ai ", " ai", "gpt", "inference", "stable-diffusion", "chatbot"), "AI Tools"),
    (("proxy", "vpn", "v2ray", "clash", "sing-box", "wireguard", "tunnel"), "Network & Proxy"),
    (("game", "gaming", "emulator", "launcher", "minecraft"), "Gaming"),
    (("chat", "messaging", "messenger", "im "), "Messaging"),
    (("player", "video", "audio", "music", "media"), "Media Players"),
    (("encrypt", "password", "security", "privacy", "vault"), "Security & Privacy"),
    (("docker", "kubernetes", "k8s", "devops", "cloud", "terraform"), "Cloud & DevOps"),
    (("download", "downloader", "torrent", "aria2"), "Download Tools"),
    (("note", "markdown", "productivity", "todo", "office"), "Productivity"),
    (("cli", "git", "compiler", "sdk", "developer", "ide", "editor", "terminal", "debug"), "Developer Tools"),
    (("disk", "system", "monitor", "cleaner", "uninstall", "registry"), "System Utilities"),
]


def categorize(topics: list[str], description: str) -> str:
    haystack = " ".join(topics).lower() + " " + (description or "").lower()
    for keywords, category in _KEYWORD_CATEGORY:
        if any(k in haystack for k in keywords):
            return category
    return "Utilities"
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_categorize.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/categorize.py tests/test_discover_categorize.py
git commit -m "feat(discover): 新增 category 关键词分类"
```

---

## Task 4：dedup

**Files:**
- Create: `scripts/discover/dedup.py`
- Test: `tests/test_discover_dedup.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from scripts.discover import dedup
from scripts.discover.models import Candidate


def test_is_new_false_for_existing_repo(monkeypatch):
    fake_cfg = {
        "packages": [
            {"id": "rufus", "fetcher": "github_release", "args": {"repo": "pbatard/rufus"}},
        ]
    }
    monkeypatch.setattr(dedup, "load_packages_config", lambda: fake_cfg)
    existing = dedup.existing_repos()
    c = Candidate(repo="pbatard/rufus", name="rufus", stars=1, description="")
    assert dedup.is_new(c, existing) is False


def test_is_new_true_for_unknown_repo(monkeypatch):
    fake_cfg = {"packages": [
        {"id": "rufus", "fetcher": "github_release", "args": {"repo": "pbatard/rufus"}},
    ]}
    monkeypatch.setattr(dedup, "load_packages_config", lambda: fake_cfg)
    existing = dedup.existing_repos()
    c = Candidate(repo="zen-browser/desktop", name="zen", stars=1, description="")
    assert dedup.is_new(c, existing) is True


def test_repo_match_is_case_insensitive(monkeypatch):
    fake_cfg = {"packages": [
        {"id": "x", "fetcher": "github_release", "args": {"repo": "PBatard/Rufus"}},
    ]}
    monkeypatch.setattr(dedup, "load_packages_config", lambda: fake_cfg)
    existing = dedup.existing_repos()
    c = Candidate(repo="pbatard/rufus", name="rufus", stars=1, description="")
    assert dedup.is_new(c, existing) is False
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_dedup.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""对照现有 packages/*.yaml 判断候选是否已收录。"""

from __future__ import annotations

from ..config_loader import load_packages_config
from .models import Candidate


def existing_repos() -> set[str]:
    """返回现有 github_release 条目的 repo 集合（全小写）。"""
    cfg = load_packages_config()
    repos: set[str] = set()
    for pkg in cfg.get("packages", []):
        if not isinstance(pkg, dict):
            continue
        if pkg.get("fetcher") != "github_release":
            continue
        repo = (pkg.get("args") or {}).get("repo")
        if isinstance(repo, str) and repo.strip():
            repos.add(repo.strip().lower())
    return repos


def is_new(candidate: Candidate, existing: set[str]) -> bool:
    return candidate.repo.strip().lower() not in existing
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_dedup.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/dedup.py tests/test_discover_dedup.py
git commit -m "feat(discover): 新增对照既有清单的去重"
```

---

## Task 5：translate（MyMemory）

**Files:**
- Create: `scripts/discover/translate.py`
- Test: `tests/test_discover_translate.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from scripts.discover import translate
from scripts.discover.models import PLACEHOLDER_DESC_CN


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_translate_success(monkeypatch):
    def fake_get(url, **kwargs):
        assert "mymemory" in url
        return _FakeResp({"responseData": {"translatedText": "USB 启动盘制作工具"}})

    monkeypatch.setattr(translate, "get", fake_get)
    assert translate.translate_to_zh("USB bootable drive creator") == "USB 启动盘制作工具"


def test_translate_empty_input_returns_placeholder():
    assert translate.translate_to_zh("") == PLACEHOLDER_DESC_CN


def test_translate_http_failure_returns_placeholder(monkeypatch):
    def fake_get(url, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(translate, "get", fake_get)
    assert translate.translate_to_zh("anything") == PLACEHOLDER_DESC_CN


def test_translate_bad_payload_returns_placeholder(monkeypatch):
    def fake_get(url, **kwargs):
        return _FakeResp({"responseData": {"translatedText": ""}})

    monkeypatch.setattr(translate, "get", fake_get)
    assert translate.translate_to_zh("anything") == PLACEHOLDER_DESC_CN
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_translate.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""desc_cn 翻译后端：MyMemory（免 key）。

容错优先：任何失败都降级为占位符，绝不抛异常中断整个发现流程。
后端做成可替换：未来可换 DeepL，只需替换 translate_to_zh 内部实现。
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..net import get
from .models import PLACEHOLDER_DESC_CN

_MYMEMORY_API = "https://api.mymemory.translated.net/get"
_TIMEOUT = 15


def translate_to_zh(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return PLACEHOLDER_DESC_CN
    params = urlencode({"q": text, "langpair": "en|zh-CN"})
    url = f"{_MYMEMORY_API}?{params}"
    try:
        resp = get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        translated = (data.get("responseData") or {}).get("translatedText") or ""
        translated = translated.strip()
        return translated if translated else PLACEHOLDER_DESC_CN
    except Exception:
        return PLACEHOLDER_DESC_CN
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_translate.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/translate.py tests/test_discover_translate.py
git commit -m "feat(discover): 新增 MyMemory 翻译后端（失败降级占位符）"
```

---

## Task 6：generate（slugify + build_entry，黄金测试）

**Files:**
- Create: `scripts/discover/generate.py`
- Test: 扩展 `tests/test_discover_generate.py`

- [ ] **Step 1: 追加失败测试**（在 Task 1 已有 import 测试之后追加）

```python
from scripts.discover.generate import slugify, build_entry
from scripts.validate_config import validate_config


def test_slugify_basic():
    assert slugify("Zen Browser") == "zen-browser"
    assert slugify("OBS Studio!!") == "obs-studio"
    assert slugify("7-Zip") == "7-zip"


def test_slugify_strips_leading_nonalnum():
    # id 必须以字母或数字开头（ID_RE）
    assert slugify("---Foo")[0].isalnum()


def test_build_entry_passes_validate_config():
    entry = build_entry(
        repo="pbatard/rufus",
        name="Rufus",
        category="System Utilities",
        pattern="rufus-*.exe",
        desc_en="USB bootable drive creator",
        desc_cn="USB 启动盘制作工具",
    )
    # 生成的条目放进最小 config 必须通过校验（黄金测试）
    errors = validate_config({"packages": [entry]})
    assert errors == [], errors
    assert entry["editions"] == ["cn", "intl"]
    assert entry["fetcher"] == "github_release"
    assert entry["args"]["repo"] == "pbatard/rufus"
    assert entry["args"]["assets"] == [{"platform": "win-x64", "pattern": "rufus-*.exe"}]
    # 字段顺序：id 在最前
    assert list(entry.keys())[0] == "id"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_generate.py -v`
Expected: FAIL（`cannot import name 'slugify'`）

- [ ] **Step 3: 写实现**

```python
"""把候选信息组装为 validate_config 认可的 package 条目。"""

from __future__ import annotations

import re

_NON_ID = re.compile(r"[^a-z0-9]+")
_LEADING_NON_ALNUM = re.compile(r"^[^a-z0-9]+")


def slugify(name: str) -> str:
    """转为合法 id：小写、非字母数字→连字符、去首尾连字符。

    需满足 validate_config 的 ID_RE: ^[a-z0-9][a-z0-9-]*$
    """
    s = name.strip().lower()
    s = _NON_ID.sub("-", s)
    s = _LEADING_NON_ALNUM.sub("", s)
    s = s.strip("-")
    return s


def build_entry(
    *,
    repo: str,
    name: str,
    category: str,
    pattern: str,
    desc_en: str,
    desc_cn: str,
) -> dict:
    """按现有 YAML 字段顺序组装条目。"""
    return {
        "id": slugify(name),
        "name": name,
        "category": category,
        "editions": ["cn", "intl"],
        "homepage": f"https://github.com/{repo}",
        "fetcher": "github_release",
        "args": {
            "repo": repo,
            "assets": [{"platform": "win-x64", "pattern": pattern}],
        },
        "desc_cn": desc_cn,
        "desc_en": desc_en,
    }
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_generate.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/generate.py tests/test_discover_generate.py
git commit -m "feat(discover): 新增条目生成（含 validate_config 黄金测试）"
```

---

## Task 7：sources/github（发现源）

**Files:**
- Create: `scripts/discover/sources/github.py`
- Test: `tests/test_discover_github.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from scripts.discover.sources import github


def test_discover_builds_candidates_with_assets(monkeypatch):
    def fake_get_json(url, **kwargs):
        if "search/repositories" in url:
            return {
                "items": [
                    {
                        "full_name": "pbatard/rufus",
                        "name": "rufus",
                        "stargazers_count": 29000,
                        "description": "USB tool",
                        "topics": ["usb", "windows"],
                    }
                ]
            }
        # latest release
        return {
            "published_at": "2026-01-01T00:00:00Z",
            "assets": [
                {"name": "rufus-4.5.exe"},
                {"name": "rufus-4.5p.exe"},
            ],
        }

    monkeypatch.setattr(github, "get_json", fake_get_json)
    cands = github.discover(min_stars=5000, max_scan=10)
    assert len(cands) == 1
    c = cands[0]
    assert c.repo == "pbatard/rufus"
    assert c.stars == 29000
    assert c.asset_names == ["rufus-4.5.exe", "rufus-4.5p.exe"]
    assert c.topics == ["usb", "windows"]


def test_discover_skips_repo_without_release(monkeypatch):
    def fake_get_json(url, **kwargs):
        if "search/repositories" in url:
            return {"items": [
                {"full_name": "a/b", "name": "b", "stargazers_count": 9000,
                 "description": "", "topics": []}
            ]}
        raise RuntimeError("404 no release")

    monkeypatch.setattr(github, "get_json", fake_get_json)
    cands = github.discover(min_stars=5000, max_scan=10)
    assert cands == []
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_github.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""发现源：GitHub Search API 找高星 repo + 取 latest release 资产。"""

from __future__ import annotations

from typing import Any

from ...net import get_json, github_headers
from ..models import Candidate

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 30
_PER_PAGE = 50


def _latest_release(repo: str) -> dict[str, Any] | None:
    url = f"{_GITHUB_API}/repos/{repo}/releases/latest"
    try:
        return get_json(url, headers=github_headers(), timeout=_TIMEOUT)
    except Exception:
        return None  # 无 release / 仅 prerelease → 跳过该 repo


def discover(min_stars: int, max_scan: int) -> list[Candidate]:
    """按 star 降序扫描高星 repo，取得 latest release 资产，构建候选列表。"""
    candidates: list[Candidate] = []
    scanned = 0
    page = 1
    while scanned < max_scan:
        query = f"stars:>={min_stars}"
        url = (
            f"{_GITHUB_API}/search/repositories"
            f"?q={query}&sort=stars&order=desc&per_page={_PER_PAGE}&page={page}"
        )
        data = get_json(url, headers=github_headers(), timeout=_TIMEOUT)
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            break
        for item in items:
            if scanned >= max_scan:
                break
            scanned += 1
            repo = item.get("full_name")
            if not repo:
                continue
            rel = _latest_release(repo)
            if rel is None:
                continue
            asset_names = [a["name"] for a in rel.get("assets", []) if a.get("name")]
            if not asset_names:
                continue
            candidates.append(
                Candidate(
                    repo=repo,
                    name=item.get("name") or repo.split("/")[-1],
                    stars=int(item.get("stargazers_count", 0)),
                    description=item.get("description") or "",
                    topics=list(item.get("topics") or []),
                    asset_names=asset_names,
                    released_at=rel.get("published_at"),
                )
            )
        page += 1
    return candidates
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_github.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/sources/github.py tests/test_discover_github.py
git commit -m "feat(discover): 新增 GitHub 高星 repo 发现源"
```

---

## Task 8：sources/corroborate（winget/Scoop 佐证）

**Files:**
- Create: `scripts/discover/sources/corroborate.py`
- Test: `tests/test_discover_corroborate.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from scripts.discover.sources import corroborate


def test_winget_corroborated_when_code_search_has_hits(monkeypatch):
    def fake_get_json(url, **kwargs):
        assert "search/code" in url
        assert "winget-pkgs" in url
        return {"total_count": 3}

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.corroborated_by_winget("pbatard/rufus") is True


def test_scoop_not_corroborated_when_zero_hits(monkeypatch):
    def fake_get_json(url, **kwargs):
        return {"total_count": 0}

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.corroborated_by_scoop("obscure/repo") is False


def test_corroboration_failure_is_false_not_exception(monkeypatch):
    def fake_get_json(url, **kwargs):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.corroborated_by_winget("a/b") is False


def test_is_corroborated_true_if_either_source(monkeypatch):
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        # winget 命中即短路，不应再查 scoop
        return {"total_count": 1}

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.is_corroborated("pbatard/rufus") is True
    assert len(calls) == 1  # 短路
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_corroborate.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""佐证源：用 GitHub Code Search 在 winget-pkgs / Scoop 仓库里搜候选的 repo URL。

total_count > 0 即表示该软件已被 winget/Scoop 收录 → 多源交叉验证通过。
任何失败都视为"未佐证"（False），绝不抛异常。
"""

from __future__ import annotations

from urllib.parse import quote

from ...net import get_json, github_headers

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 30
_WINGET_REPO = "microsoft/winget-pkgs"
_SCOOP_REPOS = ("ScoopInstaller/Main", "ScoopInstaller/Extras")


def _code_search_hits(repo_url_fragment: str, in_repo: str) -> int:
    q = quote(f'"{repo_url_fragment}" repo:{in_repo}')
    url = f"{_GITHUB_API}/search/code?q={q}"
    try:
        data = get_json(url, headers=github_headers(), timeout=_TIMEOUT)
        return int(data.get("total_count", 0)) if isinstance(data, dict) else 0
    except Exception:
        return 0


def corroborated_by_winget(repo: str) -> bool:
    fragment = f"github.com/{repo}"
    return _code_search_hits(fragment, _WINGET_REPO) > 0


def corroborated_by_scoop(repo: str) -> bool:
    fragment = f"github.com/{repo}"
    return any(_code_search_hits(fragment, r) > 0 for r in _SCOOP_REPOS)


def is_corroborated(repo: str) -> bool:
    """winget 或 Scoop 任一命中即视为多源佐证（winget 优先，命中短路）。"""
    if corroborated_by_winget(repo):
        return True
    return corroborated_by_scoop(repo)
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_corroborate.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/sources/corroborate.py tests/test_discover_corroborate.py
git commit -m "feat(discover): 新增 winget/Scoop Code Search 佐证"
```

---

## Task 9：aggregate（编排：过滤 + 排序 + 截断）

**Files:**
- Create: `scripts/discover/aggregate.py`
- Test: `tests/test_discover_aggregate.py`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from scripts.discover import aggregate
from scripts.discover.models import Candidate


def _cand(repo, stars, assets):
    return Candidate(repo=repo, name=repo.split("/")[-1], stars=stars,
                     description="", asset_names=assets)


def test_select_filters_and_sorts(monkeypatch):
    cands = [
        _cand("a/low", 6000, ["a-1.0-win-x64.exe"]),
        _cand("b/high", 9000, ["b-1.0-windows-installer.exe"]),
        _cand("c/nowin", 8000, ["c-1.0-linux.AppImage"]),   # 无 Windows 资产 → 淘汰
        _cand("d/exists", 9999, ["d-1.0-setup.exe"]),       # 已存在 → 淘汰
    ]
    monkeypatch.setattr(aggregate, "existing_repos", lambda: {"d/exists"})
    monkeypatch.setattr(aggregate, "is_corroborated", lambda repo: True)

    selected = aggregate.select_candidates(cands, max_output=10, max_corroborate=30)
    repos = [c.repo for c, _ in selected]
    assert repos == ["b/high", "a/low"]  # 按 star 降序，且各自带 pattern
    # 每个返回 (candidate, pattern)
    assert all(pattern for _, pattern in selected)


def test_select_requires_corroboration(monkeypatch):
    cands = [_cand("a/b", 9000, ["a-1.0-win-x64.exe"])]
    monkeypatch.setattr(aggregate, "existing_repos", lambda: set())
    monkeypatch.setattr(aggregate, "is_corroborated", lambda repo: False)  # 未佐证
    assert aggregate.select_candidates(cands, max_output=10, max_corroborate=30) == []


def test_select_respects_max_output(monkeypatch):
    cands = [_cand(f"o/r{i}", 9000 - i, [f"r{i}-1.0-setup.exe"]) for i in range(20)]
    monkeypatch.setattr(aggregate, "existing_repos", lambda: set())
    monkeypatch.setattr(aggregate, "is_corroborated", lambda repo: True)
    selected = aggregate.select_candidates(cands, max_output=10, max_corroborate=30)
    assert len(selected) == 10
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_aggregate.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""编排：把 GitHub 候选过滤（资产可推断 + 去重 + 多源佐证）、按 star 排序、截断。

调用顺序刻意为：先做无 API 成本的资产推断与去重，再对幸存者做
有限次（max_corroborate）的 code search 佐证，控制 GitHub 限额消耗。
"""

from __future__ import annotations

from .asset_infer import infer_windows_pattern
from .dedup import existing_repos, is_new
from .models import Candidate
from .sources.corroborate import is_corroborated


def select_candidates(
    candidates: list[Candidate],
    *,
    max_output: int,
    max_corroborate: int,
) -> list[tuple[Candidate, str]]:
    """返回 [(candidate, windows_pattern), ...]，已过滤+排序+截断。"""
    existing = existing_repos()

    # ① 资产可推断 + ② 去重（无 API 成本），同时记下 pattern
    prefiltered: list[tuple[Candidate, str]] = []
    for c in candidates:
        if not is_new(c, existing):
            continue
        pattern = infer_windows_pattern(c.asset_names)
        if pattern is None:
            continue
        prefiltered.append((c, pattern))

    # 按 star 降序，保证先佐证最热门的
    prefiltered.sort(key=lambda cp: cp[0].stars, reverse=True)

    # ③ 多源佐证（有限次 code search）
    selected: list[tuple[Candidate, str]] = []
    checked = 0
    for c, pattern in prefiltered:
        if len(selected) >= max_output:
            break
        if checked >= max_corroborate:
            break
        checked += 1
        if is_corroborated(c.repo):
            selected.append((c, pattern))
    return selected
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_aggregate.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/aggregate.py tests/test_discover_aggregate.py
git commit -m "feat(discover): 新增候选编排（过滤+排序+佐证+截断）"
```

---

## Task 10：yaml_writer（干净追加写）

**Files:**
- Create: `scripts/discover/yaml_writer.py`
- Test: `tests/test_discover_cli.py`（本任务先建，Task 11 补 CLI 测试）

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

from pathlib import Path

import yaml

from scripts.discover.yaml_writer import append_entries


def test_append_entries_preserves_existing_and_adds(tmp_path: Path):
    f = tmp_path / "shared.yaml"
    f.write_text(
        "packages:\n"
        "- id: existing\n"
        "  name: Existing\n"
        "  category: Utilities\n"
        "  editions:\n"
        "  - cn\n"
        "  - intl\n"
        "  fetcher: github_release\n"
        "  args:\n"
        "    repo: foo/existing\n"
        "    assets:\n"
        "    - platform: win-x64\n"
        "      pattern: existing-*.exe\n"
        "  desc_cn: 旧\n"
        "  desc_en: old\n",
        encoding="utf-8",
    )
    new = [{
        "id": "rufus", "name": "Rufus", "category": "System Utilities",
        "editions": ["cn", "intl"], "homepage": "https://github.com/pbatard/rufus",
        "fetcher": "github_release",
        "args": {"repo": "pbatard/rufus", "assets": [{"platform": "win-x64", "pattern": "rufus-*.exe"}]},
        "desc_cn": "USB 启动盘制作工具", "desc_en": "USB tool",
    }]
    append_entries(new, f)

    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    ids = [p["id"] for p in data["packages"]]
    assert ids == ["existing", "rufus"]
    # 中文不被转义
    assert "USB 启动盘制作工具" in f.read_text(encoding="utf-8")
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_cli.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""把新条目追加写入 packages/<edition>.yaml。

追加而非全量重写：只在文件尾部新增 list item，保证 PR diff 干净
（不动既有条目的格式/顺序）。
"""

from __future__ import annotations

from pathlib import Path

import yaml


def append_entries(entries: list[dict], path: Path) -> None:
    if not entries:
        return
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    chunk = yaml.safe_dump(
        entries,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
    )
    path.write_text(text + chunk, encoding="utf-8")
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_cli.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/yaml_writer.py tests/test_discover_cli.py
git commit -m "feat(discover): 新增 YAML 追加写（保证干净 diff）"
```

---

## Task 11：CLI 入口（discover_popular.py）

**Files:**
- Create: `scripts/discover_popular.py`
- Test: 扩展 `tests/test_discover_cli.py`

- [ ] **Step 1: 追加失败测试**

```python
from scripts import discover_popular


def test_cli_writes_entries_and_new_ids(tmp_path, monkeypatch):
    from scripts.discover.models import Candidate

    out = tmp_path / "shared.yaml"
    out.write_text("packages:\n- id: seed\n  name: Seed\n  category: Utilities\n"
                   "  editions:\n  - cn\n  - intl\n  fetcher: github_release\n"
                   "  args:\n    repo: x/seed\n    assets:\n    - platform: win-x64\n"
                   "      pattern: seed-*.exe\n  desc_cn: 种子\n  desc_en: seed\n",
                   encoding="utf-8")
    ids_file = tmp_path / "new_ids.txt"

    fake = [Candidate(repo="pbatard/rufus", name="Rufus", stars=29000,
                      description="USB tool", asset_names=["rufus-4.5.exe"])]
    monkeypatch.setattr(discover_popular, "discover", lambda **kw: fake)
    monkeypatch.setattr(discover_popular, "select_candidates",
                        lambda c, **kw: [(fake[0], "rufus-*.exe")])
    monkeypatch.setattr(discover_popular, "categorize", lambda topics, desc: "System Utilities")
    monkeypatch.setattr(discover_popular, "translate_to_zh", lambda t: "USB 启动盘制作工具")

    rc = discover_popular.main([
        "--output", str(out), "--new-ids-file", str(ids_file),
    ])
    assert rc == 0
    assert ids_file.read_text(encoding="utf-8").strip() == "rufus"
    text = out.read_text(encoding="utf-8")
    assert "pbatard/rufus" in text
    assert "USB 启动盘制作工具" in text


def test_cli_no_candidates_writes_empty_ids(tmp_path, monkeypatch):
    out = tmp_path / "shared.yaml"
    out.write_text("packages:\n- id: seed\n  name: Seed\n  category: Utilities\n"
                   "  editions:\n  - cn\n  - intl\n  fetcher: github_release\n"
                   "  args:\n    repo: x/seed\n    assets:\n    - platform: win-x64\n"
                   "      pattern: seed-*.exe\n  desc_cn: 种子\n  desc_en: seed\n",
                   encoding="utf-8")
    ids_file = tmp_path / "new_ids.txt"
    monkeypatch.setattr(discover_popular, "discover", lambda **kw: [])
    monkeypatch.setattr(discover_popular, "select_candidates", lambda c, **kw: [])
    rc = discover_popular.main(["--output", str(out), "--new-ids-file", str(ids_file)])
    assert rc == 0
    assert ids_file.read_text(encoding="utf-8").strip() == ""
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_discover_cli.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
"""自动发现热门软件 CLI。

流程：GitHub 发现 → 编排过滤（资产+去重+佐证）→ 分类+翻译 → 组装条目
→ 追加写入 packages/<edition>.yaml → 校验 → 输出新增 id 列表（供 workflow 用）。

运行：
  python -m scripts.discover         # 包导入方式
  python scripts/discover_popular.py # 脚本方式
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows runner 默认 cp1252，输出中文/✓ 会 UnicodeEncodeError；与 sync.py 一致先 reconfigure。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.discover.sources.github import discover  # type: ignore
    from scripts.discover.aggregate import select_candidates  # type: ignore
    from scripts.discover.categorize import categorize  # type: ignore
    from scripts.discover.translate import translate_to_zh  # type: ignore
    from scripts.discover.generate import build_entry  # type: ignore
    from scripts.discover.yaml_writer import append_entries  # type: ignore
    from scripts.discover.models import (  # type: ignore
        DEFAULT_MIN_STARS, DEFAULT_MAX_OUTPUT, DEFAULT_MAX_SCAN, DEFAULT_MAX_CORROBORATE,
    )
    from scripts.config_loader import load_packages_config  # type: ignore
    from scripts.validate_config import validate_config  # type: ignore
else:
    from .discover.sources.github import discover
    from .discover.aggregate import select_candidates
    from .discover.categorize import categorize
    from .discover.translate import translate_to_zh
    from .discover.generate import build_entry
    from .discover.yaml_writer import append_entries
    from .discover.models import (
        DEFAULT_MIN_STARS, DEFAULT_MAX_OUTPUT, DEFAULT_MAX_SCAN, DEFAULT_MAX_CORROBORATE,
    )
    from .config_loader import load_packages_config
    from .validate_config import validate_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "packages" / "shared.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-stars", type=int, default=DEFAULT_MIN_STARS)
    parser.add_argument("--max-output", type=int, default=DEFAULT_MAX_OUTPUT)
    parser.add_argument("--max-scan", type=int, default=DEFAULT_MAX_SCAN)
    parser.add_argument("--max-corroborate", type=int, default=DEFAULT_MAX_CORROBORATE)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--new-ids-file", default=str(REPO_ROOT / "discover_new_ids.txt"))
    args = parser.parse_args([] if argv is None else argv)

    candidates = discover(min_stars=args.min_stars, max_scan=args.max_scan)
    print(f"发现 {len(candidates)} 个高星候选")
    selected = select_candidates(
        candidates, max_output=args.max_output, max_corroborate=args.max_corroborate
    )
    print(f"过滤后保留 {len(selected)} 个候选")

    entries: list[dict] = []
    new_ids: list[str] = []
    for cand, pattern in selected:
        entry = build_entry(
            repo=cand.repo,
            name=cand.name,
            category=categorize(cand.topics, cand.description),
            pattern=pattern,
            desc_en=cand.description,
            desc_cn=translate_to_zh(cand.description),
        )
        entries.append(entry)
        new_ids.append(entry["id"])
        print(f"✓ {entry['id']}: {cand.repo} ({cand.stars}★) → {pattern}")

    output_path = Path(args.output)
    if entries:
        append_entries(entries, output_path)
        # 写后校验：跨文件 id 唯一性 + 字段合法
        cfg = load_packages_config()
        errors = validate_config(cfg)
        if errors:
            print("生成的条目校验失败：", file=sys.stderr)
            for e in errors:
                print(f"- {e}", file=sys.stderr)
            return 1

    Path(args.new_ids_file).write_text("\n".join(new_ids), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> 注：CLI 通过模块级 `from .discover... import discover, select_candidates, ...` 把这些名字绑定到 `discover_popular` 命名空间，因此测试可 `monkeypatch.setattr(discover_popular, "discover", ...)`。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_discover_cli.py -v`
Expected: PASS（3 passed：含 Task 10 的 writer 测试）

- [ ] **Step 5: 运行全套 + lint + mypy**

Run:
```bash
pytest tests/test_discover_*.py -q
python -m ruff check scripts/discover scripts/discover_popular.py tests/test_discover_*.py
python -m ruff format --check scripts/discover scripts/discover_popular.py tests/test_discover_*.py
```
Expected: 全部 PASS / no issues。（mypy 默认只覆盖核心模块，discover 暂不强制；如需可在 pyproject 的 mypy files 增列。）

- [ ] **Step 6: Commit**

```bash
git add scripts/discover_popular.py tests/test_discover_cli.py
git commit -m "feat(discover): 新增发现 CLI（编排全链路 + 写后校验）"
```

---

## Task 12：CI —— 把 discover 测试接入 lint-test action

**Files:**
- Modify: `.github/actions/python-lint-test/action.yml`（在 "Test - fetchers" step 之后追加）

- [ ] **Step 1: 追加 step**

在 `action.yml` 的 fetchers step 之后、`Test - workflow.yml self-check` 之前插入：

```yaml
    - name: Test - discover
      if: ${{ !cancelled() }}
      shell: bash
      run: |
        python -m pytest \
          tests/test_discover_asset_infer.py \
          tests/test_discover_categorize.py \
          tests/test_discover_dedup.py \
          tests/test_discover_translate.py \
          tests/test_discover_generate.py \
          tests/test_discover_github.py \
          tests/test_discover_corroborate.py \
          tests/test_discover_aggregate.py \
          tests/test_discover_cli.py \
          -q
```

- [ ] **Step 2: 本地验证整段 action 引用的命令可跑**

Run: `pytest tests/test_discover_*.py -q`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add .github/actions/python-lint-test/action.yml
git commit -m "ci: 把 discover 测试接入 lint-test 复合 action"
```

---

## Task 13：定时 Workflow（discover.yml）

**Files:**
- Create: `.github/workflows/discover.yml`

- [ ] **Step 1: 写 workflow**

```yaml
name: Discover popular software

on:
  schedule:
    # 双周：每月 1 号与 15 号 02:00 UTC（GitHub Actions cron 无原生双周，用双日期近似）
    - cron: "0 2 1,15 * *"
  workflow_dispatch: {}

permissions:
  contents: write
  pull-requests: write

jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install deps
        run: pip install -r requirements.txt

      - name: Run discovery
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python -m scripts.discover --output packages/shared.yaml --new-ids-file discover_new_ids.txt

      - name: Validate config
        run: python scripts/validate_config.py

      - name: Dry-run sync for new ids
        if: ${{ hashFiles('discover_new_ids.txt') != '' }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          IDS=$(tr '\n' ',' < discover_new_ids.txt | sed 's/,$//')
          if [ -n "$IDS" ]; then
            python -m scripts.sync --only "$IDS"
          else
            echo "无新候选，跳过 dry-run"
          fi

      - name: Clean temp file
        run: rm -f discover_new_ids.txt data/latest.json.tmp || true

      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v7
        with:
          branch: auto/discover
          delete-branch: true
          title: "chore(discover): 自动发现的热门软件候选"
          commit-message: "chore(discover): 自动发现热门软件候选（待人工 review）"
          body: |
            本 PR 由 discover workflow 自动生成。

            请 review：
            - [ ] 核对每条 `desc_cn`（自动翻译，可能需润色）
            - [ ] 确认 `category` 合理
            - [ ] 如不适合国内版，把 `editions` 从 `[cn, intl]` 改为 `[intl]`
            - [ ] 确认 `args.assets[].pattern` 能匹配到 Windows 安装包
        # 无变更时该 action 不会开 PR
```

> 说明：`discover_new_ids.txt` 与 `data/latest.json`（dry-run 产生的改动）不应进 PR。`create-pull-request` 只提交工作区改动；为避免 dry-run 的 `data/latest.json` 混入，下一步在 .gitignore 处理临时文件，并依赖 dry-run 只读校验（sync 写 latest.json，故 PR 前需还原——见 Step 2）。

- [ ] **Step 2: 防止 dry-run 产物混入 PR**

修改 "Dry-run sync" step，让它在临时目录产出而不污染仓库：把该 step 命令改为先备份再还原 `data/latest.json`：

```yaml
      - name: Dry-run sync for new ids
        if: ${{ hashFiles('discover_new_ids.txt') != '' }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          IDS=$(tr '\n' ',' < discover_new_ids.txt | sed 's/,$//')
          if [ -n "$IDS" ]; then
            cp data/latest.json /tmp/latest.json.bak 2>/dev/null || true
            python -m scripts.sync --only "$IDS" || true
            cp /tmp/latest.json.bak data/latest.json 2>/dev/null || true
          fi
          rm -f discover_new_ids.txt
```

（dry-run 的目的是"让日志暴露 fetcher 是否解析成功"，故 `|| true` 不让其失败阻断 PR；真正的硬校验是上一步 validate_config。）

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/discover.yml
git commit -m "ci: 新增双周自动发现热门软件 workflow（开 PR）"
```

---

## Task 14：最终验证 + 文档

**Files:**
- Modify: `AGENTS.md`（在合适位置补一段 discover 管道说明）

- [ ] **Step 1: 全套测试 + lint**

Run:
```bash
pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
```
Expected: 全部 PASS / no issues。

- [ ] **Step 2: 本地真实干跑（可选，需联网）**

Run: `python -m scripts.discover --max-scan 20 --max-output 3 --output /tmp/probe.yaml --new-ids-file /tmp/ids.txt`
（先 `cp packages/shared.yaml /tmp/probe.yaml`）
Expected: 打印发现/过滤数量与 ✓ 行；`/tmp/ids.txt` 含新 id；`/tmp/probe.yaml` 末尾追加合法条目。

- [ ] **Step 3: 在 AGENTS.md 补说明**

在 AGENTS.md 描述 fetcher/edition 的章节后追加：

```markdown
## 自动发现热门软件（discover 管道）

`scripts/discover/` + `scripts/discover_popular.py` 实现双周自动发现：
从 GitHub 高星 repo（star ≥ 5000）发现候选，用 winget/Scoop 的 GitHub
Code Search 佐证（多源交叉），自动推断 Windows 资产 pattern、翻译描述，
生成 `editions: [cn, intl]` 条目追加到 `packages/shared.yaml`，由
`.github/workflows/discover.yml` 开 PR 供人工 review（不自动合并）。
质量门槛：①能推断 Windows 资产 ②被 winget/Scoop 收录。
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 补充 discover 自动发现管道说明"
```

---

## 验证清单（端到端）

- `pytest -q` 全绿（新增 9 个 test_discover_*.py）
- `python -m ruff check . && python -m ruff format --check .` 无问题
- `python -m mypy` 无问题
- 手动触发 workflow（`workflow_dispatch`）→ 观察是否开出 PR、PR 内容是否为 shared.yaml 的纯追加 diff
- PR 中 `data/latest.json`、`discover_new_ids.txt` 不应出现
- 抽查 1-2 条候选的 `args.assets[].pattern` 能否在对应 repo 的真实 release 命中

## Spec 覆盖自检

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 多源交叉（GitHub + winget/Scoop） | Task 7（GitHub）+ Task 8（佐证）+ Task 9（编排要求佐证） |
| 质量门槛①能推断 Windows 资产 | Task 2 + Task 9（pattern 为 None 则淘汰） |
| 质量门槛②多源交叉 | Task 8 + Task 9 |
| 去重 | Task 4 + Task 9 |
| 默认 editions [cn,intl] | Task 6（build_entry） |
| desc_en 取自 repo / desc_cn 翻译 | Task 5 + Task 11 |
| star ≥ 5000、≤10/PR | Task 11 默认参数 + Task 9 截断 |
| 容错（单源/单候选失败不中断） | Task 5/7/8 内 try/except 降级 |
| 永不改既有条目、干净 diff | Task 10（追加写） |
| 定时双周 + 开 PR（不自动合并） | Task 13 |
| 写后 validate_config | Task 11 |
| dry-run sync 校验 | Task 13 |
| 测试接入 CI 每模块 step | Task 12 |
| cn 国内源管道 | Non-Goal（spec 已列未来工作，本计划不含） |

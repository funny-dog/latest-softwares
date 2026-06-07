# 统一部署配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把国内版/国际版后端的装配差异从两个硬编码入口文件,收敛到声明式 `config/profiles/<name>.json`,由统一的 `build_app` 装配;新增部署目标只需加一份 JSON + 设 `APP_PROFILE`。

**Architecture:** 新增 `app_core/app_builder.py`,职责为「读 profile → 造 store → 调 `create_app`」。三个入口(`app.py` 新统一入口、`main.py`、`deploy/cn_server.py`)退化成一行 shim,各调 `build_app`,从而保留 FastAPI Cloud / 现网 systemd 的部署锚点,实现「合并代码零运维动作」。差异(edition / 存储后端 / 是否挂静态 / packages 端点 / 日志 / seed)全部声明在 JSON 里;secret(`TURSO_*`)始终走环境变量。

**Tech Stack:** Python 3.10+、FastAPI、stdlib `json`(零运行时新依赖)、pytest + `fastapi.testclient`。

**为何 JSON 而非 TOML/YAML:** 现网 cn venv 仅含 fastapi+uvicorn 且不会自动加依赖,运行时配置解析必须 stdlib-only;`tomllib` 需 3.11+、`PyYAML` cn 未装,`json` 是唯一兼具「全 Python 版本兼容 + 公认配置格式」的。不能写注释的缺点用 `config/profiles/README.md` 弥补。

---

## File Structure

**新增:**
- `app.py` — 统一部署入口,`app = build_app()`(按 `APP_PROFILE` 选 profile,默认 intl)
- `app_core/app_builder.py` — `load_profile` / `build_store` / `build_app`,装配逻辑唯一所在
- `config/profiles/cn.json` — 国内版声明式配置
- `config/profiles/intl.json` — 国际版声明式配置
- `config/profiles/README.md` — 字段说明(替代 JSON 注释)
- `tests/test_app_builder.py` — builder 层测试

**修改:**
- `main.py` — 退化为 shim:`app = build_app("intl")`(保留 FastAPI Cloud 锚点 main:app)
- `deploy/cn_server.py` — 退化为 shim:`app = build_app("cn")`(保留现网 systemd 锚点)
- `tests/test_main.py` — 改为验证三入口 app 的路由契约(原来检查模块级 EDITION/store 变量已不存在)
- `deploy/cn_server.service` — ExecStart 升级为目标态 `app:app` + `Environment=APP_PROFILE=cn`
- `deploy/server-setup.sh` — 内嵌 systemd unit 同步升级为目标态
- `.github/workflows/deploy-only.yml` — 修复缺口:改 `deploy/**` 时也同步后端 + restart
- `CLAUDE.md` / `AGENTS.md` — 记录 config/profiles 配置入口与三入口 shim 关系

**不改:** `requirements.txt` / `pyproject.toml`(零新依赖)、`app_core/app_factory.py`(契约不变)、`app_core/store.py`、`.fastapicloudignore`(config/ 不在排除列表,自动上传)。

---

### Task 1: app_builder 核心(profile 加载 + store 工厂 + 装配)

**Files:**
- Create: `app_core/app_builder.py`
- Test: `tests/test_app_builder.py`

- [ ] **Step 1: 写失败测试 — store 工厂**

`tests/test_app_builder.py`:

```python
"""app_builder 测试:profile 加载、store 工厂、按 profile 装配 app。

端点行为见 test_app_core.py;这里只测「装配」这一层。
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app_core import app_builder
from app_core.store import JsonFileMetricsStore, SqlMetricsStore


@pytest.fixture
def profiles_dir(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "cn.json").write_text(json.dumps({
        "edition": "cn",
        "title": "CN",
        "description": "cn desc",
        "data_file": "data/latest.json",
        "serve_static": False,
        "packages_endpoint": False,
        "log_events": False,
        "store": {"type": "json_file", "metrics_file": str(tmp_path / "m.json")},
    }), encoding="utf-8")
    (d / "intl.json").write_text(json.dumps({
        "edition": "intl",
        "title": "INTL",
        "description": "intl desc",
        "data_file": "data/latest.json",
        "serve_static": True,
        "packages_endpoint": True,
        "log_events": True,
        "store": {"type": "sql", "db_path": str(tmp_path / "m.db"),
                  "seed_file": str(tmp_path / "seed.json")},
    }), encoding="utf-8")
    return d


def test_build_store_json_file(tmp_path):
    store = app_builder.build_store(
        {"type": "json_file", "metrics_file": str(tmp_path / "m.json")},
        root=tmp_path,
    )
    assert isinstance(store, JsonFileMetricsStore)


def test_build_store_sql(tmp_path):
    store = app_builder.build_store(
        {"type": "sql", "db_path": str(tmp_path / "m.db")}, root=tmp_path
    )
    assert isinstance(store, SqlMetricsStore)


def test_build_store_unknown_type_raises(tmp_path):
    with pytest.raises(ValueError):
        app_builder.build_store({"type": "redis"}, root=tmp_path)


def test_build_store_metrics_file_env_override(tmp_path, monkeypatch):
    override = tmp_path / "override.json"
    monkeypatch.setenv("LATEST_SOFTWARES_METRICS_FILE", str(override))
    store = app_builder.build_store(
        {"type": "json_file", "metrics_file": "/should/be/ignored.json"},
        root=tmp_path,
    )
    assert store.path == override
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `pytest tests/test_app_builder.py -v`
Expected: FAIL — `AttributeError: module 'app_core.app_builder' has no attribute ...`(模块不存在)

- [ ] **Step 3: 写最小实现**

`app_core/app_builder.py`:

```python
"""按 profile 装配 FastAPI 应用 —— cn/intl 与未来部署目标的统一装配层。

差异(edition / 存储后端 / 是否挂静态 / 是否暴露 packages / 日志 / seed)全部由
config/profiles/<name>.json 声明,这里只负责:读 profile → 造 store → 调 create_app。

为何 JSON 而非 TOML/YAML:国内版后端 venv 仅含 fastapi+uvicorn 且不会自动加依赖,
运行时配置解析必须 stdlib-only;json 是其中唯一兼具「全 Python 版本(≥3.10)兼容
+ 公认配置格式」的。secret(TURSO_*)始终走环境变量,不进文件。
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app_core.app_factory import create_app
from app_core.store import JsonFileMetricsStore, MetricsStore, SqlMetricsStore

# 仓库根:app_core/ 的上一级。app.py / main.py / deploy.cn_server 都靠它定位资源。
ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "config" / "profiles"
DEFAULT_PROFILE = "intl"


def _resolve(path: str, root: Path) -> Path:
    """相对路径按仓库根解析,绝对路径原样返回。"""
    p = Path(path)
    return p if p.is_absolute() else root / p


def load_profile(name: str, *, profiles_dir: Path = PROFILES_DIR) -> dict[str, Any]:
    """读取并返回 config/profiles/<name>.json 的内容。"""
    profile_path = profiles_dir / f"{name}.json"
    if not profile_path.is_file():
        raise FileNotFoundError(f"未找到部署 profile: {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def build_store(store_cfg: dict[str, Any], *, root: Path = ROOT) -> MetricsStore:
    """按 profile 的 store 段造出存储后端实例。

    路径支持环境变量覆盖(向后兼容现网 systemd 的 Environment= 配置):
      - json_file: LATEST_SOFTWARES_METRICS_FILE > store.metrics_file
      - sql      : LATEST_SOFTWARES_STATS_DB     > store.db_path
    secret(TURSO_*)由 SqlMetricsStore.from_env 读环境变量,不进 profile。
    """
    kind = store_cfg.get("type")
    if kind == "json_file":
        metrics_file = os.environ.get(
            "LATEST_SOFTWARES_METRICS_FILE", store_cfg["metrics_file"]
        )
        return JsonFileMetricsStore(_resolve(metrics_file, root))
    if kind == "sql":
        db_path = os.environ.get("LATEST_SOFTWARES_STATS_DB", store_cfg["db_path"])
        return SqlMetricsStore.from_env(db_path=_resolve(db_path, root))
    raise ValueError(f"未知的 store.type: {kind!r}")


def build_app(
    name: str | None = None,
    *,
    root: Path = ROOT,
    profiles_dir: Path = PROFILES_DIR,
) -> FastAPI:
    """按 profile 名装配 app。name 缺省时取环境变量 APP_PROFILE,再缺省 intl。"""
    name = name or os.environ.get("APP_PROFILE", DEFAULT_PROFILE)
    profile = load_profile(name, profiles_dir=profiles_dir)
    store = build_store(profile["store"], root=root)

    data_file = _resolve(
        os.environ.get("LATEST_SOFTWARES_DATA_FILE", profile["data_file"]), root
    )

    # seed lifespan 仅当 sql 存储且 profile 指定 seed_file(国际版历史 workaround)。
    lifespan = None
    seed = profile["store"].get("seed_file")
    if isinstance(store, SqlMetricsStore) and seed:
        seed_path = _resolve(
            os.environ.get("LATEST_SOFTWARES_STATS_SEED", seed), root
        )

        @asynccontextmanager
        async def lifespan(_app: FastAPI):  # noqa: F811
            store.seed_if_empty(seed_path)
            yield

    serve_static = (root / "dist") if profile.get("serve_static") else None

    return create_app(
        edition=profile["edition"],
        store=store,
        data_file=data_file,
        serve_static_dir=serve_static,
        with_packages_endpoint=profile.get("packages_endpoint", False),
        log_events=profile.get("log_events", False),
        lifespan=lifespan,
        title=profile.get("title"),
        description=profile.get("description", ""),
    )
```

- [ ] **Step 4: 运行 store 工厂测试,确认通过**

Run: `pytest tests/test_app_builder.py -v`
Expected: PASS(上面 4 个 store 测试)

- [ ] **Step 5: 追加 build_app 装配测试**

在 `tests/test_app_builder.py` 末尾追加:

```python
def test_load_profile_missing_raises(profiles_dir):
    with pytest.raises(FileNotFoundError):
        app_builder.load_profile("nope", profiles_dir=profiles_dir)


def test_build_app_cn_contract(profiles_dir, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "latest.json").write_text(
        json.dumps({"schema_version": 2, "packages": [], "stats": {}}),
        encoding="utf-8",
    )
    app = app_builder.build_app("cn", root=tmp_path, profiles_dir=profiles_dir)
    client = TestClient(app)
    assert client.get("/api/health").json()["edition"] == "cn"
    assert client.get("/api/packages").status_code == 404  # cn 不暴露


def test_build_app_intl_contract(profiles_dir, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "latest.json").write_text(
        json.dumps({"schema_version": 2, "packages": [], "stats": {}}),
        encoding="utf-8",
    )
    app = app_builder.build_app("intl", root=tmp_path, profiles_dir=profiles_dir)
    client = TestClient(app)
    assert client.get("/api/health").json()["edition"] == "intl"
    assert client.get("/api/packages").status_code == 200  # intl 独有


def test_build_app_default_profile_from_env(profiles_dir, tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "latest.json").write_text(
        json.dumps({"schema_version": 2, "packages": [], "stats": {}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_PROFILE", "cn")
    app = app_builder.build_app(root=tmp_path, profiles_dir=profiles_dir)
    assert TestClient(app).get("/api/health").json()["edition"] == "cn"
```

- [ ] **Step 6: 运行全部 builder 测试,确认通过**

Run: `pytest tests/test_app_builder.py -v`
Expected: PASS(全部)

- [ ] **Step 7: 提交**

```bash
git add app_core/app_builder.py tests/test_app_builder.py
git commit -m "feat(api): 新增 app_builder,按 profile 统一装配两版后端"
```

---

### Task 2: 真实 profile JSON + 字段文档

**Files:**
- Create: `config/profiles/cn.json`
- Create: `config/profiles/intl.json`
- Create: `config/profiles/README.md`
- Test: `tests/test_app_builder.py`(追加真实 profile 校验)

- [ ] **Step 1: 写失败测试 — 真实 profile 文件存在且字段齐全**

在 `tests/test_app_builder.py` 末尾追加:

```python
def test_real_profiles_loadable_and_complete():
    """仓库内真实 profile 必须可加载且含必备字段(防手滑漏字段)。"""
    required = {"edition", "data_file", "serve_static",
                "packages_endpoint", "log_events", "store"}
    for name, edition in [("cn", "cn"), ("intl", "intl")]:
        profile = app_builder.load_profile(name)  # 用真实 PROFILES_DIR
        assert required <= set(profile), f"{name} 缺字段"
        assert profile["edition"] == edition
        assert profile["store"]["type"] in {"json_file", "sql"}
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_app_builder.py::test_real_profiles_loadable_and_complete -v`
Expected: FAIL — `FileNotFoundError: 未找到部署 profile: .../config/profiles/cn.json`

- [ ] **Step 3: 写两份真实 profile**

`config/profiles/cn.json`:

```json
{
  "edition": "cn",
  "title": "Latest Softwares API (CN)",
  "description": "国内版访问统计与下载追踪 API",
  "data_file": "data/latest.json",
  "serve_static": false,
  "packages_endpoint": false,
  "log_events": false,
  "store": {
    "type": "json_file",
    "metrics_file": "/var/lib/latest-softwares/metrics.json"
  }
}
```

`config/profiles/intl.json`:

```json
{
  "edition": "intl",
  "title": "Latest Softwares API (International)",
  "description": "Daily metadata sync for latest software releases, with a JSON API and static web frontend for the international edition.",
  "data_file": "data/latest.json",
  "serve_static": true,
  "packages_endpoint": true,
  "log_events": true,
  "store": {
    "type": "sql",
    "db_path": "data/site_metrics.db",
    "seed_file": "data/site_metrics.json"
  }
}
```

- [ ] **Step 4: 写字段文档**

`config/profiles/README.md`:

```markdown
# 部署 Profile(config/profiles/)

每个 `<name>.json` 描述一个部署目标的装配差异,由 `app_core/app_builder.py` 的
`build_app("<name>")` 读取。新增部署目标 = 加一份 JSON + 把进程的 `APP_PROFILE`
设为该名字 + 入口指向 `app:app`,无需写新的 Python。

用 JSON 而非 TOML/YAML:国内版后端运行环境只装了 fastapi+uvicorn,配置解析必须
stdlib-only,JSON 是唯一「全 Python 版本兼容 + 公认配置格式」的选择。

## 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `edition` | string | `cn` / `intl`,决定包数据过滤 |
| `title` | string | FastAPI app 标题 |
| `description` | string | FastAPI app 描述 |
| `data_file` | string | 包数据路径(相对仓库根;可被 `LATEST_SOFTWARES_DATA_FILE` 覆盖) |
| `serve_static` | bool | 是否挂载 `dist/`(intl 自挂;cn 由 nginx 服务,填 false) |
| `packages_endpoint` | bool | 是否暴露 `/api/packages`(目前仅 intl) |
| `log_events` | bool | 是否打结构化事件日志(给日志平台采集) |
| `store.type` | string | `json_file` / `sql`,见下 |

### `store.type = "json_file"`(cn)
- `metrics_file`:统计文件路径(可被 `LATEST_SOFTWARES_METRICS_FILE` 覆盖)。
  放在部署目录之外(如 `/var/lib/...`),避免 rsync --delete 清掉。

### `store.type = "sql"`(intl)
- `db_path`:本地 SQLite 路径(可被 `LATEST_SOFTWARES_STATS_DB` 覆盖)。
- `seed_file`:可选;存在则启用 lifespan 启动回填(库为空时)。
- 远程 Turso 的 `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` 是 **secret,只走环境
  变量,绝不写进本文件**。

## 路径约定
相对路径相对仓库根解析;绝对路径原样使用。
```

- [ ] **Step 5: 运行真实 profile 测试 + 全套 builder 测试,确认通过**

Run: `pytest tests/test_app_builder.py -v`
Expected: PASS(含 `test_real_profiles_loadable_and_complete`)

- [ ] **Step 6: 提交**

```bash
git add config/profiles/
git commit -m "feat(deploy): 新增 cn/intl 部署 profile 与字段文档"
```

---

### Task 3: 三入口退化为 shim + 重写入口 smoke 测试

**Files:**
- Create: `app.py`
- Modify: `main.py`(整文件替换)
- Modify: `deploy/cn_server.py`(整文件替换)
- Modify: `tests/test_main.py`(整文件替换)

- [ ] **Step 1: 改写入口 smoke 测试(先失败)**

整文件替换 `tests/test_main.py`:

```python
"""三个部署入口的装配 smoke 测试。

端点/存储完整行为见 test_app_core.py;装配逻辑见 test_app_builder.py。
这里只守住「部署锚点存在且契约正确」:
  - app:app                  —— 统一入口(默认 intl)
  - main:app                 —— FastAPI Cloud 锚点(intl)
  - deploy.cn_server:app     —— 现网 systemd 锚点(cn)
"""

from __future__ import annotations

import app as app_entry
import deploy.cn_server as cn_server
import main

SHARED_PATHS = {
    "/api/health",
    "/api/visit",
    "/api/metrics",
    "/api/download/{package_id}/{platform}",
}


def _api_paths(app) -> set[str]:
    return {r.path for r in app.routes if getattr(r, "methods", None)}


def test_main_is_intl_anchor():
    paths = _api_paths(main.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" in paths  # intl 独有


def test_cn_server_is_cn_anchor():
    paths = _api_paths(cn_server.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" not in paths  # cn 不暴露


def test_app_entry_defaults_to_intl():
    # app.py 未设 APP_PROFILE 时默认 intl
    paths = _api_paths(app_entry.app)
    assert SHARED_PATHS <= paths
    assert "/api/packages" in paths
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`(app.py 尚不存在)

- [ ] **Step 3: 新增统一入口 app.py**

`app.py`:

```python
"""统一部署入口:按环境变量 APP_PROFILE 装配 app(缺省 intl)。

新部署目标只需:加一份 config/profiles/<name>.json + 设 APP_PROFILE=<name>,
进程指向 `app:app` 即可,无需新增 Python 入口。装配逻辑见 app_core.app_builder。
"""

from app_core.app_builder import build_app

app = build_app()
```

- [ ] **Step 4: main.py 退化为 intl shim**

整文件替换 `main.py`:

```python
"""国际版入口 —— FastAPI Cloud 部署锚点 `main:app`。

装配逻辑已统一到 app_core.app_builder;本文件只把锚点绑到 intl profile。
差异声明见 config/profiles/intl.json。
"""

from app_core.app_builder import build_app

app = build_app("intl")
```

- [ ] **Step 5: deploy/cn_server.py 退化为 cn shim**

整文件替换 `deploy/cn_server.py`:

```python
"""国内版入口 —— 阿里云现网 systemd 部署锚点 `deploy.cn_server:app`。

装配逻辑已统一到 app_core.app_builder;本文件只把锚点绑到 cn profile。
差异声明见 config/profiles/cn.json。保留本文件是为了「合并代码零运维动作」:
现网 systemd 仍按 deploy.cn_server:app 启动即可,迁移到统一 app:app 是可选项。
"""

from app_core.app_builder import build_app

app = build_app("cn")
```

- [ ] **Step 6: 运行入口测试,确认通过**

Run: `pytest tests/test_main.py -v`
Expected: PASS(3 个)

- [ ] **Step 7: 跑全套测试确认无回归**

Run: `pytest -q`
Expected: PASS(全绿;尤其 test_app_core / test_app_builder / test_main)

- [ ] **Step 8: 提交**

```bash
git add app.py main.py deploy/cn_server.py tests/test_main.py
git commit -m "refactor(api): 三入口退化为 build_app shim,装配差异收敛到 profile"
```

---

### Task 4: 升级部署配置(systemd unit + 初始化脚本 + 修 deploy-only 缺口)

**Files:**
- Modify: `deploy/cn_server.service:9-13`
- Modify: `deploy/server-setup.sh:126-130`
- Modify: `.github/workflows/deploy-only.yml`

- [ ] **Step 1: 升级 systemd unit 到目标态(统一入口)**

`deploy/cn_server.service` 把 `[Service]` 段的 ExecStart 与 Environment 改为:

```ini
ExecStart=/opt/latest-softwares/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5
Environment="APP_PROFILE=cn"
```

> 注:删掉原 `LATEST_SOFTWARES_METRICS_FILE` / `LATEST_SOFTWARES_DATA_FILE` 两行
> ——路径已由 `config/profiles/cn.json` 提供(metrics_file 绝对、data_file 相对)。
> 现网迁移是**可选的一次性运维**:`scp` 新 unit 到 `/etc/systemd/system/`、
> `sudo systemctl daemon-reload && sudo systemctl restart latest-softwares-api`。
> 不迁移也能继续跑(旧 unit 的 deploy.cn_server:app shim 仍有效)。

- [ ] **Step 2: 同步升级 server-setup.sh 内嵌 unit(新装服务器直接用目标态)**

`deploy/server-setup.sh` 中 `SERVICE_CONF` heredoc(约 117-134 行)里的对应行改为:

```bash
ExecStart=$API_DIR/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5
Environment="APP_PROFILE=cn"
```

同步删掉该 heredoc 里 `LATEST_SOFTWARES_METRICS_FILE` / `LATEST_SOFTWARES_DATA_FILE`
两行 Environment。

- [ ] **Step 3: 修复 deploy-only.yml 后端缺口**

`.github/workflows/deploy-only.yml` 在「Deploy to Aliyun via rsync」step 之后、
「Summary」之前,插入 checkout + 后端同步 + restart(与 sync.yml 的 deploy job 一致):

```yaml
      - name: Checkout (for backend deploy)
        uses: actions/checkout@v6

      - name: Deploy API backend to Aliyun
        env:
          SSH_HOST:    ${{ secrets.ALIYUN_HOST }}
          SSH_USER:    ${{ secrets.ALIYUN_USER }}
          SSH_PORT:    ${{ secrets.ALIYUN_PORT }}
        run: |
          PORT="${SSH_PORT:-22}"
          SSH_CMD="ssh -i ~/.ssh/deploy_key -p $PORT -o StrictHostKeyChecking=accept-new"
          rsync -avz --delete \
            -e "$SSH_CMD" \
            --exclude '__pycache__' --exclude '.venv' --exclude 'venv/' \
            --exclude 'tests/' --exclude 'web/' --exclude 'dist/' \
            --exclude '.github/' --exclude 'scripts/' --exclude '.fastapicloud/' \
            --exclude '.ruff_cache/' --exclude '.mypy_cache/' --exclude '.pytest_cache/' \
            ./ "$SSH_USER@$SSH_HOST:/opt/latest-softwares/"
          $SSH_CMD "$SSH_USER@$SSH_HOST" "sudo systemctl restart latest-softwares-api" || true
```

> 这保证「只改 deploy/ 或 config/ 时」后端代码与 profile 也会同步并重启,
> 修掉原 deploy-only 只刷新静态文件、后端不更新的缺口。

- [ ] **Step 4: 校验 YAML 与 systemd 语法(静态检查)**

Run: `python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('yaml ok')"`
Expected: 输出 `yaml ok`(无异常)

- [ ] **Step 5: 提交**

```bash
git add deploy/cn_server.service deploy/server-setup.sh .github/workflows/deploy-only.yml
git commit -m "chore(deploy): systemd/初始化脚本切到统一入口,修 deploy-only 后端缺口"
```

---

### Task 5: 文档同步 + 全量验证

**Files:**
- Modify: `CLAUDE.md`(架构要点段)
- Modify: `AGENTS.md`(若有对应部署/入口说明段)

- [ ] **Step 1: 更新 CLAUDE.md 架构要点**

在 `CLAUDE.md` 的「共享 API 内核 `app_core/`」要点后,补一条:

```markdown
- **部署 profile 驱动**：两版后端差异声明在 `config/profiles/{cn,intl}.json`，由 `app_core/app_builder.py` 的 `build_app("<name>")` 装配。入口 `app.py`（按 `APP_PROFILE` 选，默认 intl）/ `main.py`（FastAPI Cloud 锚点 main:app）/ `deploy/cn_server.py`（现网 systemd 锚点）均退化为一行 shim。新增部署目标 = 加一份 JSON + 设 `APP_PROFILE` + 入口指向 `app:app`。secret（`TURSO_*`）只走环境变量，不进 profile。
```

- [ ] **Step 2: 检查 AGENTS.md 是否需同步**

Run: `grep -n "cn_server\|main:app\|入口\|部署" AGENTS.md`
若命中描述旧双入口的段落,改为指向 `config/profiles/` + `app_builder` 的新模型
(保持与 CLAUDE.md 一致的措辞)。无命中则跳过。

- [ ] **Step 3: 全量测试**

Run: `pytest -q`
Expected: 全绿。

- [ ] **Step 4: 本地起两版冒烟验证(可选但推荐)**

```bash
# intl(默认)
APP_PROFILE=intl python -c "from app import app; import fastapi; print('intl ok', any(r.path=='/api/packages' for r in app.routes))"
# cn
APP_PROFILE=cn python -c "from app import app; print('cn ok', not any(getattr(r,'path','')=='/api/packages' for r in app.routes))"
```
Expected: 分别输出 `intl ok True` / `cn ok True`

- [ ] **Step 5: 提交**

```bash
git add CLAUDE.md AGENTS.md
git commit -m "docs: 记录 config/profiles 部署模型与三入口 shim 关系"
```

---

## Self-Review

**Spec coverage:**
- 统一管理两边部署 → Task 1-3(build_app + profile + shim)✓
- 改配置文件即可部署 → Task 2(JSON profile)✓
- 阿里云保持 rsync+systemd 不上 Docker → Task 4(systemd 升级,无 Docker)✓
- 与 FastAPI Cloud 契约一致(app 变量 + env) → Task 3(三入口锚点)✓
- 零运维动作可合并 → Task 3(shim 保留旧锚点)✓
- 顺带修 deploy-only 后端缺口 → Task 4 Step 3 ✓

**Placeholder scan:** 无 TODO/TBD;每个 code step 均含完整代码。

**Type consistency:** `build_app(name, *, root, profiles_dir)`、`build_store(store_cfg, *, root)`、`load_profile(name, *, profiles_dir)`、`_resolve(path, root)` 在各 Task 中签名一致;profile 字段名(`edition/data_file/serve_static/packages_endpoint/log_events/store.{type,metrics_file,db_path,seed_file}`)在测试、实现、真实 JSON、文档间一致。

**约束守护:** app_core 仍零 `scripts/` 依赖;libsql 仍延迟导入(未碰 store.py);三入口 `app` 变量保留;无新增运行时依赖(stdlib json)。

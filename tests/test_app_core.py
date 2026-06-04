"""app_core 共享内核测试:存储后端两实现 + create_app 两版行为。

覆盖国内版(JsonFileMetricsStore)与国际版(SqlMetricsStore)共享的端点逻辑,
以及它们的差异(packages 端点、edition 过滤、存储语义)。国内版后端此前零测试,
这里一并补上。
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app_core.app_factory import create_app
from app_core.store import JsonFileMetricsStore, SqlMetricsStore

SAMPLE_DATA = {
    "schema_version": 2,
    "generated_at": "2026-06-04T00:00:00+00:00",
    "packages": [
        {
            "id": "firefox",
            "name": "Firefox",
            "category": "Browsers",
            "editions": ["cn", "intl"],
            "assets": [{"platform": "win-x64", "url": "https://example.com/ff.exe"}],
        },
        {
            "id": "intlonly",
            "name": "IntlOnly",
            "category": "X",
            "editions": ["intl"],
            "assets": [{"platform": "win-x64", "url": "https://example.com/io.exe"}],
        },
    ],
    "stats": {"total": 2},
}


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(SAMPLE_DATA), encoding="utf-8")
    return path


# ── JsonFileMetricsStore(国内版)────────────────────────────────


def test_json_store_visit_accumulates_and_persists(tmp_path):
    path = tmp_path / "m.json"
    store = JsonFileMetricsStore(path)
    for _ in range(3):
        store.increment_visit("/")
    metrics = store.load()
    assert metrics["visits"]["total"] == 3
    assert metrics["visits"]["paths"]["/"] == 3
    assert metrics["scope"] == "instance-local"
    assert metrics["storage"] == "persistent-file"
    # 另起一个 store 读同一文件 → 持久
    assert JsonFileMetricsStore(path).load()["visits"]["total"] == 3


def test_json_store_download_breakdown(tmp_path):
    store = JsonFileMetricsStore(tmp_path / "m.json")
    store.increment_download("firefox", "win-x64")
    store.increment_download("firefox", "win-x64")
    metrics = store.load()
    assert metrics["downloads"]["total"] == 2
    assert metrics["downloads"]["packages"]["firefox"] == 2
    assert metrics["downloads"]["platforms"]["win-x64"] == 2
    assert metrics["downloads"]["assets"]["firefox:win-x64"] == 2


def test_json_store_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "m.json"
    path.write_text("not valid json", encoding="utf-8")
    assert JsonFileMetricsStore(path).load()["visits"]["total"] == 0


# ── SqlMetricsStore(国际版)─────────────────────────────────────


def test_sql_store_local_sqlite_accumulates(tmp_path):
    store = SqlMetricsStore(db_path=tmp_path / "m.db")
    assert store.scope == "instance-local"
    assert store.storage == "local-sqlite"
    for _ in range(3):
        store.increment_visit("/")
    assert store.load()["visits"]["total"] == 3


def test_sql_store_from_env_remote_labels(monkeypatch, tmp_path):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://demo.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "tok")
    store = SqlMetricsStore.from_env(db_path=tmp_path / "m.db")
    assert store._remote is True
    assert store.scope == "global"
    assert store.storage == "turso-libsql"


def test_sql_store_seed_if_empty(tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(
        json.dumps(
            {
                "visits": {"total": 42, "paths": {"/": 42}},
                "downloads": {"total": 3, "assets": {"firefox:win-x64": 3}},
                "updated_at": "2026-05-05T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    store = SqlMetricsStore(db_path=tmp_path / "m.db")
    store.seed_if_empty(seed)
    metrics = store.load()
    assert metrics["visits"]["total"] == 42
    assert metrics["downloads"]["total"] == 3
    assert metrics["downloads"]["assets"]["firefox:win-x64"] == 3
    # 库已有数据 → 再次 seed 应跳过(不翻倍)
    store.seed_if_empty(seed)
    assert store.load()["visits"]["total"] == 42


def test_sql_store_real_libsql_local_file(tmp_path):
    """真实 libsql(本地文件)跑完整流程,回归「Cursor 不可直接迭代」bug。

    libsql 本地文件模式的游标语义与远程 Turso 一致,无需联网即可复现。
    """
    libsql = pytest.importorskip("libsql")
    db_path = tmp_path / "ls.db"
    store = SqlMetricsStore(db_path=db_path)
    # 强制连接走真实 libsql(即使未配 TURSO),以复现远程游标行为
    store._connect = lambda: libsql.connect(str(db_path))
    for _ in range(3):
        store.increment_visit("/")
    metrics = store.load()  # 修复前此处会 TypeError: Cursor not iterable
    assert metrics["visits"]["total"] == 3
    assert metrics["visits"]["paths"]["/"] == 3


# ── create_app:国际版(intl)─────────────────────────────────────


def test_create_app_intl(data_file, tmp_path):
    store = SqlMetricsStore(db_path=tmp_path / "m.db")
    app = create_app(
        edition="intl",
        store=store,
        data_file=data_file,
        with_packages_endpoint=True,
    )
    client = TestClient(app)

    health = client.get("/api/health").json()
    assert health["edition"] == "intl"
    assert health["packages_count"] == 2  # firefox + intlonly 都属 intl

    packages = client.get("/api/packages")
    assert packages.status_code == 200
    assert packages.json()["edition"] == "intl"

    assert client.post("/api/visit").json()["metrics"]["visits"]["total"] == 1
    assert client.post("/api/visit").json()["metrics"]["visits"]["total"] == 2

    resp = client.get("/api/download/firefox/win-x64", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/ff.exe"
    assert client.get("/api/metrics").json()["downloads"]["total"] == 1


# ── create_app:国内版(cn)───────────────────────────────────────


def test_create_app_cn(data_file, tmp_path):
    store = JsonFileMetricsStore(tmp_path / "m.json")
    app = create_app(edition="cn", store=store, data_file=data_file)
    client = TestClient(app)

    health = client.get("/api/health").json()
    assert health["edition"] == "cn"
    assert health["packages_count"] == 1  # 仅 firefox 属 cn

    # cn 不暴露 /api/packages
    assert client.get("/api/packages").status_code == 404

    # intl-only 包在 cn 下载不到(edition 过滤)→ 404
    resp = client.get("/api/download/intlonly/win-x64", follow_redirects=False)
    assert resp.status_code == 404

    # cn 可下载 firefox
    resp = client.get("/api/download/firefox/win-x64", follow_redirects=False)
    assert resp.status_code == 307
    assert client.get("/api/metrics").json()["downloads"]["total"] == 1


def test_download_unknown_asset_returns_404(data_file, tmp_path):
    store = JsonFileMetricsStore(tmp_path / "m.json")
    app = create_app(edition="cn", store=store, data_file=data_file)
    client = TestClient(app)
    resp = client.get("/api/download/nope/win-x64", follow_redirects=False)
    assert resp.status_code == 404

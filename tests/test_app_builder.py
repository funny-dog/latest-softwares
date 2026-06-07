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


# ── store 工厂 ────────────────────────────────────────────────


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


# ── build_app 装配 ───────────────────────────────────────────


def test_load_profile_missing_raises(profiles_dir):
    with pytest.raises(FileNotFoundError):
        app_builder.load_profile("nope", profiles_dir=profiles_dir)


def _write_empty_data(root):
    data = root / "data"
    data.mkdir()
    (data / "latest.json").write_text(
        json.dumps({"schema_version": 2, "packages": [], "stats": {}}),
        encoding="utf-8",
    )


def test_build_app_cn_contract(profiles_dir, tmp_path):
    _write_empty_data(tmp_path)
    app = app_builder.build_app("cn", root=tmp_path, profiles_dir=profiles_dir)
    client = TestClient(app)
    assert client.get("/api/health").json()["edition"] == "cn"
    assert client.get("/api/packages").status_code == 404  # cn 不暴露


def test_build_app_intl_contract(profiles_dir, tmp_path):
    _write_empty_data(tmp_path)
    app = app_builder.build_app("intl", root=tmp_path, profiles_dir=profiles_dir)
    client = TestClient(app)
    assert client.get("/api/health").json()["edition"] == "intl"
    assert client.get("/api/packages").status_code == 200  # intl 独有


def test_build_app_default_profile_from_env(profiles_dir, tmp_path, monkeypatch):
    _write_empty_data(tmp_path)
    monkeypatch.setenv("APP_PROFILE", "cn")
    app = app_builder.build_app(root=tmp_path, profiles_dir=profiles_dir)
    assert TestClient(app).get("/api/health").json()["edition"] == "cn"


# ── 仓库内真实 profile(Task 2 落地后转绿)──────────────────


def test_real_profiles_loadable_and_complete():
    """仓库内真实 profile 必须可加载且含必备字段(防手滑漏字段)。"""
    required = {"edition", "data_file", "serve_static",
                "packages_endpoint", "log_events", "store"}
    for name, edition in [("cn", "cn"), ("intl", "intl")]:
        profile = app_builder.load_profile(name)  # 用真实 PROFILES_DIR
        assert required <= set(profile), f"{name} 缺字段"
        assert profile["edition"] == edition
        assert profile["store"]["type"] in {"json_file", "sql"}

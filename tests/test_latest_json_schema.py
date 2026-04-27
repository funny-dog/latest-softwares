"""data/latest.json 契约校验。

防御目标：fetcher 静默退化时（assets 空、version 缺失、URL 非法等）阻止
坏数据进入 README / web 页面。任一断言失败 → CI 红。

PR 中跑：校验仓库内已 commit 的 latest.json（可能是上次 sync 的结果）。
sync job 中跑：紧随 sync.py 之后，校验最新生成的 latest.json。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LATEST_JSON = REPO_ROOT / "data" / "latest.json"

REQUIRED_PKG_FIELDS = {
    "id",
    "name",
    "category",
    "version",
    "version_kind",
    "version_source",
    "source",
    "fetched_at",
    "assets",
}
REQUIRED_ASSET_FIELDS = {"platform", "url"}
ISO_DATETIME_FIELDS = ("fetched_at", "released_at", "last_success_at")
ALLOWED_VERSION_KINDS = {
    "release_version",
    "release_label",
    "build_date",
    "page_date",
    "sync_date",
}


@pytest.fixture(scope="module")
def latest_data() -> dict:
    if not LATEST_JSON.exists():
        pytest.skip(f"{LATEST_JSON} 不存在 —— 跳过 schema 校验")
    return json.loads(LATEST_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def packages(latest_data: dict) -> list[dict]:
    pkgs = latest_data.get("packages")
    assert isinstance(pkgs, list) and pkgs, "packages 必须是非空列表"
    return pkgs


def _is_valid_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_iso_datetime(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def test_top_level_schema_version_present(latest_data: dict):
    assert latest_data.get("schema_version") == 1, "schema_version 缺失或不为 1"


def test_package_ids_are_unique(packages: list[dict]):
    ids = [p.get("id") for p in packages]
    assert len(ids) == len(set(ids)), f"id 重复: {[i for i in ids if ids.count(i) > 1]}"


@pytest.mark.parametrize("field", sorted(REQUIRED_PKG_FIELDS))
def test_each_package_has_required_field(packages: list[dict], field: str):
    """每个包都必须有指定字段且非空。"""
    bad = [p.get("id", "<unnamed>") for p in packages if not p.get(field)]
    assert not bad, f"包缺失或字段 '{field}' 为空: {bad}"


def test_version_is_not_unknown_placeholder(packages: list[dict]):
    """version 必须是真实数据，不是 fetcher 的兜底字符串。"""
    bad = [
        p["id"]
        for p in packages
        if p["version"].strip().lower() in {"unknown", "n/a", ""}
    ]
    assert not bad, f"以下包 version 是兜底占位符: {bad}"


def test_version_kind_uses_known_semantics(packages: list[dict]):
    bad = [
        (p["id"], p.get("version_kind"))
        for p in packages
        if p.get("version_kind") not in ALLOWED_VERSION_KINDS
    ]
    assert not bad, f"version_kind 不在允许集合内: {bad}"


@pytest.mark.parametrize("field", ISO_DATETIME_FIELDS)
def test_datetime_fields_are_iso8601(packages: list[dict], field: str):
    """所有日期字段（存在时）必须可解析为 ISO 8601。"""
    bad = []
    for p in packages:
        value = p.get(field)
        if value is None:
            continue  # released_at / last_success_at 是可选
        if not _is_iso_datetime(value):
            bad.append((p["id"], field, value))
    assert not bad, f"非法 ISO 时间字段: {bad}"


def test_each_package_has_non_empty_assets(packages: list[dict]):
    bad = [
        p["id"]
        for p in packages
        if not isinstance(p.get("assets"), list) or not p["assets"]
    ]
    assert not bad, f"以下包 assets 为空或非列表: {bad}"


def test_each_asset_has_required_fields(packages: list[dict]):
    bad = []
    for p in packages:
        for i, asset in enumerate(p["assets"]):
            missing = REQUIRED_ASSET_FIELDS - {k for k, v in asset.items() if v}
            if missing:
                bad.append((p["id"], i, sorted(missing)))
    assert not bad, f"asset 缺字段: {bad}"


def test_each_asset_url_is_valid_http(packages: list[dict]):
    bad = []
    for p in packages:
        for asset in p["assets"]:
            if not _is_valid_url(asset.get("url")):
                bad.append((p["id"], asset.get("platform"), asset.get("url")))
    assert not bad, f"asset URL 不是合法 http(s): {bad}"


def test_asset_platforms_are_unique_within_package(packages: list[dict]):
    """同一个包内不能有重复 platform —— render 会按 platform 分组展示。"""
    bad = []
    for p in packages:
        platforms = [a.get("platform") for a in p["assets"]]
        if len(platforms) != len(set(platforms)):
            dups = [pl for pl in platforms if platforms.count(pl) > 1]
            bad.append((p["id"], list(set(dups))))
    assert not bad, f"包内 platform 重复: {bad}"


def test_stale_entries_have_reason(packages: list[dict]):
    """失败回退到上次数据的条目必须带 _stale_reason 便于排查。"""
    bad = [
        p["id"]
        for p in packages
        if p.get("_stale") is True and not p.get("_stale_reason")
    ]
    assert not bad, f"以下 _stale=True 但缺 _stale_reason: {bad}"


def test_no_unresolved_template_placeholders(packages: list[dict]):
    """防止 {version} 这类模板占位符没被替换就写入 latest.json。"""
    bad = []
    for p in packages:
        for asset in p["assets"]:
            url = asset.get("url", "")
            if "{" in url and "}" in url:
                bad.append((p["id"], asset.get("platform"), url))
    assert not bad, f"发现未替换的占位符: {bad}"

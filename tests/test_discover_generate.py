from __future__ import annotations

from scripts.discover.models import Candidate, PLACEHOLDER_DESC_CN
from scripts.discover.generate import slugify, build_entry
from scripts.validate_config import validate_config


def test_candidate_homepage_derived_from_repo():
    c = Candidate(
        repo="pbatard/rufus", name="rufus", stars=29000, description="USB tool"
    )
    assert c.homepage == "https://github.com/pbatard/rufus"
    assert PLACEHOLDER_DESC_CN.startswith("TODO")


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
    assert entry["args"]["assets"] == [
        {"platform": "win-x64", "pattern": "rufus-*.exe"}
    ]
    # 字段顺序：id 在最前
    assert list(entry.keys())[0] == "id"

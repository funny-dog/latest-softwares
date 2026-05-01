from __future__ import annotations

import copy

from scripts import validate_config
from scripts.config_loader import load_packages_config


def load_current_config() -> dict:
    return load_packages_config()


def test_current_packages_yaml_is_valid():
    errors = validate_config.validate_config(load_current_config())

    assert errors == []


def test_rejects_duplicate_ids():
    cfg = {
        "packages": [
            {
                "id": "dup",
                "name": "A",
                "category": "工具",
                "fetcher": "github_release",
                "args": {
                    "repo": "owner/repo",
                    "assets": [{"platform": "win-x64", "pattern": "*.exe"}],
                },
            },
            {
                "id": "dup",
                "name": "B",
                "category": "工具",
                "fetcher": "github_release",
                "args": {
                    "repo": "owner/repo",
                    "assets": [{"platform": "mac-arm64", "pattern": "*.dmg"}],
                },
            },
        ]
    }

    errors = validate_config.validate_config(cfg)

    assert any("重复 id: dup" in error for error in errors)


def test_rejects_unknown_fetcher():
    cfg = load_current_config()
    cfg = {"packages": [copy.deepcopy(cfg["packages"][0])]}
    cfg["packages"][0]["fetcher"] = "missing_fetcher"

    errors = validate_config.validate_config(cfg)

    assert any("未知 fetcher: missing_fetcher" in error for error in errors)


def test_rejects_invalid_tag_pattern():
    cfg = load_current_config()
    cfg = {
        "packages": [
            copy.deepcopy(next(p for p in cfg["packages"] if p["id"] == "codex"))
        ]
    }
    cfg["packages"][0]["args"]["tag_pattern"] = "["

    errors = validate_config.validate_config(cfg)

    assert any("tag_pattern 不是有效正则" in error for error in errors)


def test_rejects_duplicate_platforms():
    cfg = load_current_config()
    cfg = {
        "packages": [
            copy.deepcopy(next(p for p in cfg["packages"] if p["id"] == "chrome"))
        ]
    }
    cfg["packages"][0]["args"]["platforms"][1]["platform"] = "win-x64"

    errors = validate_config.validate_config(cfg)

    assert any("重复 platform: win-x64" in error for error in errors)


def test_rejects_invalid_download_url():
    cfg = load_current_config()
    cfg = {
        "packages": [
            copy.deepcopy(next(p for p in cfg["packages"] if p["id"] == "steam"))
        ]
    }
    cfg["packages"][0]["args"]["platforms"][0]["download_url"] = "not-a-url"

    errors = validate_config.validate_config(cfg)

    assert any("download_url 不是有效 URL" in error for error in errors)


def test_redirect_fetcher_allows_missing_download_url():
    cfg = {
        "packages": [
            {
                "id": "wegame",
                "name": "WeGame",
                "category": "游戏平台",
                "fetcher": "wegame_official",
                "args": {"platforms": [{"platform": "win-x64"}]},
            }
        ]
    }

    errors = validate_config.validate_config(cfg)

    assert errors == []


def test_redirect_fetcher_allows_missing_platforms():
    cfg = {
        "packages": [
            {
                "id": "yy",
                "name": "YY",
                "category": "即时通讯",
                "fetcher": "yy_official",
                "args": {},
            }
        ]
    }

    errors = validate_config.validate_config(cfg)

    assert errors == []


def test_allows_explicit_link_kind_on_platform_specs():
    cfg = load_current_config()
    cfg = {
        "packages": [
            copy.deepcopy(next(p for p in cfg["packages"] if p["id"] == "nvidia-app"))
        ]
    }
    cfg["packages"][0]["args"]["platforms"][0]["link_kind"] = "landing_page"

    errors = validate_config.validate_config(cfg)

    assert errors == []


def test_validates_firefox_platform_shape():
    cfg = load_current_config()
    cfg = {
        "packages": [
            copy.deepcopy(next(p for p in cfg["packages"] if p["id"] == "firefox"))
        ]
    }
    del cfg["packages"][0]["args"]["platforms"][0]["os"]

    errors = validate_config.validate_config(cfg)

    assert any("缺少或为空字段 os" in error for error in errors)


def test_validates_nodejs_platform_shape():
    cfg = load_current_config()
    cfg = {
        "packages": [
            copy.deepcopy(next(p for p in cfg["packages"] if p["id"] == "nodejs"))
        ]
    }
    del cfg["packages"][0]["args"]["platforms"][0]["file_key"]

    errors = validate_config.validate_config(cfg)

    assert any("缺少或为空字段 file_key" in error for error in errors)


def test_rejects_invalid_link_kind():
    cfg = load_current_config()
    cfg = {
        "packages": [
            copy.deepcopy(next(p for p in cfg["packages"] if p["id"] == "chrome"))
        ]
    }
    cfg["packages"][0]["args"]["platforms"][0]["link_kind"] = "maybe"

    errors = validate_config.validate_config(cfg)

    assert any("link_kind 必须是 direct 或 landing_page" in error for error in errors)


def test_validate_cross_file_uniqueness(tmp_path):
    """测试跨文件 id 唯一性检查"""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    # 创建两个有重复 id 的文件
    (packages_dir / "cn.yaml").write_text(
        "packages:\n  - id: firefox\n    name: Firefox\n"
    )
    (packages_dir / "intl.yaml").write_text(
        "packages:\n"
        "  - id: firefox\n    name: Firefox International\n"
        "  - id: chrome\n    name: Chrome\n"
    )

    errors = validate_config.validate_cross_file_uniqueness(packages_dir)
    assert len(errors) == 1
    assert "firefox" in errors[0]


def test_validate_cross_file_uniqueness_no_duplicates(tmp_path):
    """测试跨文件无重复 id 时返回空列表"""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    (packages_dir / "cn.yaml").write_text(
        "packages:\n  - id: firefox\n    name: Firefox\n"
    )
    (packages_dir / "intl.yaml").write_text(
        "packages:\n  - id: chrome\n    name: Chrome\n"
    )

    errors = validate_config.validate_cross_file_uniqueness(packages_dir)
    assert errors == []


def test_validate_cross_file_skips_underscore_files(tmp_path):
    """测试以 _ 开头的文件被跳过"""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    (packages_dir / "_template.yaml").write_text(
        "packages:\n  - id: firefox\n    name: Firefox\n"
    )
    (packages_dir / "cn.yaml").write_text(
        "packages:\n  - id: firefox\n    name: Firefox CN\n"
    )

    errors = validate_config.validate_cross_file_uniqueness(packages_dir)
    assert errors == []

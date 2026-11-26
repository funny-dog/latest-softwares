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


def test_validate_multi_source_package_manifest():
    cfg = {
        "packages": [
            {
                "id": "demo",
                "name": "Demo",
                "category": "Utilities",
                "fetcher": "package_manifest",
                "args": {
                    "sources": [
                        {
                            "provider": "winget",
                            "package": "Publisher.Demo",
                            "installer_locale": "zh-CN",
                            "platforms": [{"platform": "win-x64"}],
                        },
                        {
                            "provider": "brew",
                            "package": "demo",
                            "platforms": [{"platform": "mac-arm64"}],
                        },
                    ]
                },
            }
        ]
    }
    assert validate_config.validate_config(cfg) == []

    cfg["packages"][0]["args"]["sources"][1]["platforms"][0]["platform"] = "win-x64"
    errors = validate_config.validate_config(cfg)
    assert any("manifest platform 与 provider 不匹配" in e for e in errors)


def test_validate_linux_store_and_mixed_manifest_providers():
    cfg = {
        "packages": [
            {
                "id": "discord",
                "name": "Discord",
                "category": "Messaging",
                "fetcher": "package_manifest",
                "source_ids": {
                    "winget": "Discord.Discord",
                    "brew": "discord",
                    "flathub": "com.discordapp.Discord",
                },
                "args": {
                    "sources": [
                        {
                            "provider": "winget",
                            "package": "Discord.Discord",
                            "platforms": [{"platform": "win-x64"}],
                        },
                        {
                            "provider": "flathub",
                            "package": "com.discordapp.Discord",
                            "platforms": [{"platform": "linux-x64"}],
                        },
                    ]
                },
            },
            {
                "id": "slack-snap",
                "name": "Slack",
                "category": "Messaging",
                "fetcher": "linux_store",
                "args": {
                    "provider": "snapcraft",
                    "package": "slack",
                    "platforms": [{"platform": "linux-x64"}],
                },
            },
        ]
    }
    assert validate_config.validate_config(cfg) == []

    bad = copy.deepcopy(cfg)
    bad["packages"][0]["args"]["sources"][1]["platforms"][0]["platform"] = "win-x64"
    assert any(
        "manifest platform 与 provider 不匹配" in e
        for e in validate_config.validate_config(bad)
    )

    bad_linux = copy.deepcopy(cfg)
    bad_linux["packages"][1]["args"]["provider"] = "winget"
    assert any(
        "manifest provider" in e for e in validate_config.validate_config(bad_linux)
    )


def test_validate_updater_feed_and_redirect_probe():
    cfg = {
        "packages": [
            {
                "id": "docker-desktop",
                "name": "Docker Desktop",
                "category": "Developer Tools",
                "fetcher": "updater_feed",
                "args": {
                    "format": "sparkle",
                    "platforms": [
                        {
                            "platform": "linux-x64",
                            "feed_url": "https://desktop.docker.com/linux/main/amd64/appcast.xml",
                            "pattern": "*.deb",
                        }
                    ],
                },
            },
            {
                "id": "huorong",
                "name": "Huorong",
                "category": "Security",
                "fetcher": "redirect_probe",
                "args": {
                    "version_regex": r"sysdiag-(\d+\.\d+\.\d+\.\d+)",
                    "max_hops": 6,
                    "platforms": [
                        {
                            "platform": "win-x64",
                            "url": "https://www.huorong.cn/product/downloadHr60.php?pro=hr60&plat=x64UrlAll",
                        }
                    ],
                },
            },
        ]
    }
    assert validate_config.validate_config(cfg) == []

    bad_feed = copy.deepcopy(cfg)
    bad_feed["packages"][0]["args"]["format"] = "unknown"
    assert any("format" in e for e in validate_config.validate_config(bad_feed))

    bad_probe = copy.deepcopy(cfg)
    bad_probe["packages"][1]["args"]["version_regex"] = "["
    bad_probe["packages"][1]["args"]["max_hops"] = 99
    errors = validate_config.validate_config(bad_probe)
    assert any("version_regex 不是有效正则" in e for e in errors)
    assert any("max_hops 必须是 1-10 的整数" in e for e in errors)

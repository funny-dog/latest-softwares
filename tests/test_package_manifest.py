from __future__ import annotations

import pytest

from scripts.fetchers import package_manifest
from scripts.fetchers.base import FetchError


def test_brew_refreshes_current_version_and_checksum(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "get_json",
        lambda *a, **kw: {
            "token": "sample",
            "version": "2.0",
            "url": "https://example.test/app-arm64.dmg",
            "sha256": "a" * 64,
            "homepage": "https://example.test",
        },
    )
    result = package_manifest.fetch(
        {
            "provider": "brew",
            "package": "sample",
            "platforms": [{"platform": "mac-arm64"}],
        }
    )
    assert result.version == "2.0"
    assert result.assets[0].sha256 == "a" * 64
    assert result.assets[0].url.endswith("app-arm64.dmg")


def test_brew_unknown_architecture_is_not_labeled_universal_or_arm64(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "get_json",
        lambda *a, **kw: {
            "token": "sample",
            "version": "2.0",
            "url": "https://example.test/app.dmg",
        },
    )
    with pytest.raises(FetchError, match="architecture"):
        package_manifest.fetch(
            {
                "provider": "brew",
                "package": "sample",
                "platforms": [{"platform": "mac-arm64"}],
            }
        )
    assert (
        package_manifest.fetch(
            {
                "provider": "brew",
                "package": "sample",
                "platforms": [{"platform": "mac"}],
            }
        )
        .assets[0]
        .platform
        == "mac"
    )


def test_scoop_manifest_does_not_execute_scripts_and_selects_exact_arch(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "get_json",
        lambda *a, **kw: {
            "version": "3.0",
            "pre_install": "do not run",
            "architecture": {
                "64bit": {"url": "https://example.test/x64.zip", "hash": "b" * 64},
                "arm64": {"url": "https://example.test/arm64.zip"},
            },
        },
    )
    result = package_manifest.fetch(
        {
            "provider": "scoop",
            "package": "extras/sample",
            "platforms": [{"platform": "win-arm64"}],
        }
    )
    assert result.version == "3.0"
    assert result.assets[0].url.endswith("arm64.zip")


def test_winget_platform_ambiguity_is_rejected(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "_winget",
        lambda p: {
            "PackageVersion": "4",
            "Installers": [
                {"Architecture": "x64", "InstallerUrl": "https://example.test/a.exe"},
                {"Architecture": "x64", "InstallerUrl": "https://example.test/b.msi"},
            ],
        },
    )
    with pytest.raises(FetchError, match="ambiguous"):
        package_manifest.fetch(
            {
                "provider": "winget",
                "package": "Publisher.Sample",
                "platforms": [{"platform": "win-x64"}],
            }
        )


def test_winget_single_installer_returns_matching_version_and_sha(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "_winget",
        lambda p: {
            "PackageVersion": "4",
            "Installers": [
                {
                    "Architecture": "x64",
                    "InstallerUrl": "https://example.test/a.exe",
                    "InstallerSha256": "c" * 64,
                }
            ],
        },
    )
    result = package_manifest.fetch(
        {
            "provider": "winget",
            "package": "Publisher.Sample",
            "platforms": [{"platform": "win-x64"}],
        }
    )
    assert result.version == "4"
    assert result.assets[0].sha256 == "c" * 64


def test_winget_refresh_uses_latest_natural_version_and_checks_identity(monkeypatch):
    calls = []

    def get_json(url, **kwargs):
        calls.append(url)
        if url.endswith("10.0"):
            return [
                {
                    "name": "Publisher.Sample.installer.yaml",
                    "download_url": "https://raw.githubusercontent.com/example.yaml",
                }
            ]
        return [{"name": v, "type": "dir", "path": v} for v in ["9.0", "10.0"]]

    class Response:
        text = (
            "PackageIdentifier: Publisher.Sample\nPackageVersion: 10.0\nInstallers: []"
        )

        def close(self):
            pass

    monkeypatch.setattr(package_manifest, "get_json", get_json)
    monkeypatch.setattr(package_manifest, "get", lambda *a, **kw: Response())
    assert package_manifest._winget("Publisher.Sample")["PackageVersion"] == 10.0
    assert calls[-1].endswith("/10.0")


@pytest.mark.parametrize(
    "provider,package",
    [("brew", "../bad"), ("scoop", "untrusted/sample"), ("winget", "bad/id")],
)
def test_invalid_package_identifiers_never_make_network_requests(
    monkeypatch, provider, package
):
    monkeypatch.setattr(
        package_manifest, "get_json", lambda *a, **kw: pytest.fail("unexpected request")
    )
    with pytest.raises(FetchError):
        package_manifest.fetch(
            {
                "provider": provider,
                "package": package,
                "platforms": [{"platform": "win-x64"}],
            }
        )


def test_winget_prefers_installer_manifest_over_version_pointer(monkeypatch):
    def contents(repo, path):
        if path.endswith("Publisher/Sample"):
            return [{"type": "dir", "name": "1.0", "path": "version-dir"}]
        return [
            {
                "name": "Publisher.Sample.yaml",
                "download_url": "https://example.test/version.yaml",
            },
            {
                "name": "Publisher.Sample.installer.yaml",
                "download_url": "https://example.test/installer.yaml",
            },
        ]

    class Response:
        text = (
            "PackageIdentifier: Publisher.Sample\nPackageVersion: 1.0\nInstallers: []"
        )

        def close(self):
            pass

    def get(url, **kwargs):
        assert url.endswith("/installer.yaml")
        return Response()

    monkeypatch.setattr(package_manifest, "_contents", contents)
    monkeypatch.setattr(package_manifest, "get", get)
    assert package_manifest._winget("Publisher.Sample")["PackageVersion"] == 1.0


def test_winget_explicit_policy_prefers_installer_over_portable_archive():
    manifest = {
        "Installers": [
            {
                "Architecture": "x64",
                "InstallerType": "zip",
                "InstallerUrl": "https://example.test/portable.zip",
            },
            {
                "Architecture": "x64",
                "InstallerType": "wix",
                "Scope": "machine",
                "InstallerUrl": "https://example.test/setup.msi",
            },
        ]
    }
    assert package_manifest.select_winget_installer(manifest, "x64")[
        "InstallerUrl"
    ].endswith("setup.msi")
    manifest["Installers"].reverse()
    assert package_manifest.select_winget_installer(manifest, "x64")[
        "InstallerUrl"
    ].endswith("setup.msi")


def test_brew_current_default_is_not_replaced_by_old_os_variation(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "get_json",
        lambda *a, **kw: {
            "token": "sample",
            "version": "2.0",
            "url": "https://example.test/2.0-arm64.dmg",
            "variations": {
                "arm64_ventura": {
                    "version": "1.0",
                    "url": "https://example.test/1.0-arm64.dmg",
                }
            },
        },
    )
    result = package_manifest.fetch(
        {
            "provider": "brew",
            "package": "sample",
            "platforms": [{"platform": "mac-arm64"}],
        }
    )
    assert result.version == "2.0"
    assert result.assets[0].url.endswith("2.0-arm64.dmg")


def test_brew_cannot_label_old_other_arch_release_as_current_version(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "get_json",
        lambda *a, **kw: {
            "token": "sample",
            "version": "2.0",
            "url": "https://example.test/2.0-arm64.dmg",
            "variations": {
                "sequoia": {"version": "1.0", "url": "https://example.test/1.0-x64.dmg"}
            },
        },
    )
    with pytest.raises(FetchError, match="current version"):
        package_manifest.fetch(
            {
                "provider": "brew",
                "package": "sample",
                "platforms": [{"platform": "mac-x64"}],
            }
        )


def test_parse_winget_index_msix_reads_sqlite_packages_table(tmp_path):
    import io
    import sqlite3
    import zipfile

    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE packages (id TEXT, latest_version TEXT)")
    conn.execute("INSERT INTO packages VALUES ('Publisher.Sample', '1.2.3')")
    conn.execute("INSERT INTO packages VALUES ('Publisher.Empty', NULL)")
    conn.commit()
    conn.close()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Public/index.db", db_path.read_bytes())

    mapping = package_manifest.parse_winget_index_msix(buf.getvalue())
    assert mapping == {"Publisher.Sample": "1.2.3"}


def test_winget_uses_index_fast_path_without_contents_api(monkeypatch):
    requested_urls = []

    class Response:
        status_code = 200
        text = (
            "PackageIdentifier: Publisher.Sample\n"
            "PackageVersion: 9.1.0\n"
            "Installers:\n"
            "  - Architecture: x64\n"
            "    InstallerUrl: https://example.test/sample.exe\n"
        )

        def raise_for_status(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(
        package_manifest,
        "_winget_index_version",
        lambda pkg: "9.1.0" if pkg == "Publisher.Sample" else None,
    )
    monkeypatch.setattr(
        package_manifest,
        "_contents",
        lambda *a, **kw: pytest.fail("_contents should not be called when index hits"),
    )

    def fake_get(url, **kwargs):
        requested_urls.append(url)
        return Response()

    monkeypatch.setattr(package_manifest, "get", fake_get)
    data = package_manifest._winget("Publisher.Sample")
    assert data["PackageVersion"] == "9.1.0"
    assert requested_urls == [
        "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/p/Publisher/Sample/9.1.0/Publisher.Sample.installer.yaml"
    ]


def test_winget_locale_and_type_disambiguate_installers():
    manifest = {
        "Installers": [
            {
                "Architecture": "x64",
                "InstallerType": "inno",
                "InstallerLocale": "en-US",
                "InstallerUrl": "https://example.test/app-en.exe",
            },
            {
                "Architecture": "x64",
                "InstallerType": "inno",
                "InstallerLocale": "zh-CN",
                "InstallerUrl": "https://example.test/app-cn.exe",
            },
            {
                "Architecture": "x64",
                "InstallerType": "msi",
                "InstallerLocale": "zh-CN",
                "InstallerUrl": "https://example.test/app-cn.msi",
            },
        ]
    }
    chosen_cn = package_manifest.select_winget_installer(
        manifest, "x64", installer_locale="zh-CN"
    )
    assert chosen_cn["InstallerUrl"].endswith("app-cn.msi")

    chosen_inno = package_manifest.select_winget_installer(
        manifest, "x64", installer_locale="zh-CN", installer_type="inno"
    )
    assert chosen_inno["InstallerUrl"].endswith("app-cn.exe")


def test_package_manifest_multi_source_combines_platforms_and_versions(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "_winget",
        lambda pkg: {
            "PackageVersion": "4.2.1.9",
            "Installers": [
                {
                    "Architecture": "x64",
                    "InstallerType": "nullsoft",
                    "InstallerUrl": "https://example.test/win.exe",
                    "InstallerSha256": "a" * 64,
                }
            ],
        },
    )
    monkeypatch.setattr(
        package_manifest,
        "get_json",
        lambda *a, **kw: {
            "token": "sample-mac",
            "version": "4.2.1.12",
            "url": "https://example.test/mac-universal.dmg",
            "sha256": "b" * 64,
            "homepage": "https://example.test",
        },
    )
    result = package_manifest.fetch(
        {
            "sources": [
                {
                    "provider": "winget",
                    "package": "Publisher.Sample",
                    "platforms": [{"platform": "win-x64"}],
                },
                {
                    "provider": "brew",
                    "package": "sample-mac",
                    "platforms": [{"platform": "mac-universal"}],
                },
            ]
        }
    )
    assert result.version == "4.2.1.9"
    assert result.homepage == "https://example.test"
    assert [a.platform for a in result.assets] == ["win-x64", "mac-universal"]
    assert [a.version for a in result.assets] == ["4.2.1.9", "4.2.1.12"]


def test_package_manifest_multi_source_rejects_duplicate_platforms(monkeypatch):
    monkeypatch.setattr(
        package_manifest,
        "get_json",
        lambda *a, **kw: {
            "token": "sample-mac",
            "version": "1.0",
            "url": "https://example.test/mac-arm64.dmg",
        },
    )
    with pytest.raises(FetchError, match="duplicate platform"):
        package_manifest.fetch(
            {
                "sources": [
                    {
                        "provider": "brew",
                        "package": "sample-mac",
                        "platforms": [{"platform": "mac-arm64"}],
                    },
                    {
                        "provider": "brew",
                        "package": "sample-mac",
                        "platforms": [{"platform": "mac-arm64"}],
                    },
                ]
            }
        )

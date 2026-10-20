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

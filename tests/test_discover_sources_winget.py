from __future__ import annotations

from scripts.discover.sources import winget
from scripts.discover.state import DiscoveryState


def test_winget_extract_installer_url_accepts_valid_and_rejects_script():
    # 包含合法 x64 和包含脚本/非 http 地址的 installer
    manifest = {
        "Installers": [
            {
                "Architecture": "x64",
                "InstallerUrl": "powershell.exe -Command Write-Host bad",
            },
            {
                "Architecture": "x64",
                "InstallerUrl": "https://example.com/app-setup-x64.exe",
            },
            {
                "Architecture": "x86",
                "InstallerUrl": "http://example.com/app-setup-x86.msi",
            },
        ]
    }
    url, platform = winget.extract_installer_url(manifest)
    assert url == "https://example.com/app-setup-x64.exe"
    assert platform == "win-x64"


def test_winget_discover_builds_candidates_offline(monkeypatch):
    sample_yaml = (
        "PackageIdentifier: TestPublisher.SampleApp\n"
        "PackageName: Sample App\n"
        "Publisher: TestPublisher\n"
        "PackageUrl: https://github.com/testpub/sample\n"
        "Description: A sample tool\n"
        "Installers:\n"
        "  - Architecture: x64\n"
        "    InstallerUrl: https://example.com/sample-installer.exe\n"
    )

    def fake_get_json(url, **kwargs):
        if url.endswith("contents/manifests/a"):
            return [
                {
                    "type": "dir",
                    "path": "manifests/a/TestPublisher",
                    "sha": "publisher-sha",
                }
            ]
        if "git/trees/publisher-sha" in url:
            return {
                "tree": [
                    {
                        "type": "blob",
                        "path": "SampleApp/1.0/TestPublisher.SampleApp.installer.yaml",
                    }
                ]
            }
        raise AssertionError(url)

    class FakeResponse:
        text = sample_yaml

        def close(self):
            pass

    monkeypatch.setattr(winget, "get_json", fake_get_json)
    monkeypatch.setattr(winget, "get", lambda *a, **kw: FakeResponse())

    state = DiscoveryState()
    cands = winget.discover(max_scan=5, state=state)

    assert len(cands) == 1
    c = cands[0]
    assert c.name == "Sample App"
    assert c.external_id == "TestPublisher.SampleApp"
    assert c.source == "winget"
    assert c.repo == "testpub/sample"
    assert c.download_url == "https://example.com/sample-installer.exe"
    assert len(c.evidences) == 1


def test_winget_discover_network_failure_isolated(monkeypatch):
    def fake_get_json(url, **kwargs):
        raise RuntimeError("winget api connection timeout")

    monkeypatch.setattr(winget, "get_json", fake_get_json)
    state = DiscoveryState()
    cands = winget.discover(max_scan=5, state=state)
    assert cands == []
    assert winget.LAST_ERROR is not None
    assert "winget api connection timeout" in winget.LAST_ERROR


def test_arm64_is_never_mislabeled_x64_and_ambiguity_is_rejected():
    assert winget.extract_installer_url(
        {
            "Installers": [
                {
                    "Architecture": "arm64",
                    "InstallerUrl": "https://example.test/arm64.exe",
                }
            ]
        }
    ) == ("https://example.test/arm64.exe", "win-arm64")
    assert (
        winget.extract_installer_url(
            {
                "Installers": [
                    {
                        "Architecture": "x64",
                        "InstallerUrl": "https://example.test/a.exe",
                    },
                    {
                        "Architecture": "x64",
                        "InstallerUrl": "https://example.test/b.exe",
                    },
                ]
            }
        )[0]
        is None
    )

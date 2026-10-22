"""Regression tests for source repairs and pattern disambiguation (2026-10-23).

Verifies that tightened patterns and official download configurations in packages/*.yaml
uniquely match their intended assets without ambiguous multi-matches or missing assets.
"""

from __future__ import annotations

import fnmatch
import pytest
from scripts.config_loader import load_packages_config


@pytest.fixture(scope="module")
def packages_map() -> dict[str, dict]:
    return {p["id"]: p for p in load_packages_config()["packages"]}


def _get_pattern(pkg: dict, platform: str, version: str = "") -> str:
    for spec in pkg.get("args", {}).get("assets", []):
        if spec.get("platform") == platform:
            return spec["pattern"].replace("{version}", version)
    raise KeyError(f"Platform {platform} pattern not found in package {pkg.get('id')}")


def test_docker_desktop_official_docs_configured(packages_map: dict[str, dict]) -> None:
    pkg = packages_map["docker-desktop"]
    assert pkg["fetcher"] == "download_page"
    platforms = {
        spec["platform"]: spec["download_url"] for spec in pkg["args"]["platforms"]
    }
    assert (
        platforms["win-x64"]
        == "https://docs.docker.com/desktop/setup/install/windows-install/"
    )
    assert (
        platforms["mac-universal"]
        == "https://docs.docker.com/desktop/setup/install/mac-install/"
    )
    assert (
        platforms["linux-x64"] == "https://docs.docker.com/desktop/setup/install/linux/"
    )


@pytest.mark.parametrize("version", ["4.15", "10.123"])
def test_rufus_pattern_excludes_portable_and_arch_variants(
    packages_map: dict[str, dict], version: str
) -> None:
    pat = _get_pattern(packages_map["rufus"], "win-x64", version)
    assets = [
        f"rufus-{version}.exe",
        f"rufus-{version}.exe.sig",
        f"rufus-{version}p.exe",
        f"rufus-{version}_arm64.exe",
        f"rufus-{version}_x86.exe",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == [f"rufus-{version}.exe"]


@pytest.mark.parametrize("version", ["4.1.3", "10.20.300"])
def test_transmission_pattern_excludes_qt5_variant(
    packages_map: dict[str, dict], version: str
) -> None:
    pat = _get_pattern(packages_map["transmission"], "win-x64", version)
    assets = [
        f"transmission-{version}-qt5-x64.msi",
        f"transmission-{version}-x64.msi",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == [f"transmission-{version}-x64.msi"]


@pytest.mark.parametrize("version", ["1.14.4", "2.10.123"])
def test_obsidian_linux_pattern_excludes_arm64(
    packages_map: dict[str, dict], version: str
) -> None:
    pat = _get_pattern(packages_map["obsidian"], "linux-x64", version)
    assets = [
        f"Obsidian-{version}-arm64.AppImage",
        f"Obsidian-{version}.AppImage",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == [f"Obsidian-{version}.AppImage"]


def test_clickhouse_pattern_excludes_dbg(packages_map: dict[str, dict]) -> None:
    pat = _get_pattern(packages_map["clickhouse"], "linux-x64")
    assets = [
        "clickhouse-common-static-26.9.25.15-amd64.tgz",
        "clickhouse-common-static-dbg-26.9.25.15-amd64.tgz",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == ["clickhouse-common-static-26.9.25.15-amd64.tgz"]


def test_powershell_mac_patterns_exclude_lts(packages_map: dict[str, dict]) -> None:
    pat_arm = _get_pattern(packages_map["powershell"], "mac-arm64")
    pat_x64 = _get_pattern(packages_map["powershell"], "mac-x64")
    assets = [
        "powershell-7.6.8-osx-arm64.pkg",
        "powershell-lts-7.6.8-osx-arm64.pkg",
        "powershell-7.6.8-osx-x64.pkg",
        "powershell-lts-7.6.8-osx-x64.pkg",
    ]
    assert [a for a in assets if fnmatch.fnmatchcase(a, pat_arm)] == [
        "powershell-7.6.8-osx-arm64.pkg"
    ]
    assert [a for a in assets if fnmatch.fnmatchcase(a, pat_x64)] == [
        "powershell-7.6.8-osx-x64.pkg"
    ]


def test_localsend_pattern_excludes_cli(packages_map: dict[str, dict]) -> None:
    pat = _get_pattern(packages_map["localsend"], "win-x64")
    assets = [
        "LocalSend-1.18.2-windows-x86-64.exe",
        "LocalSend-CLI-1.18.2-windows-x86-64.exe",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == ["LocalSend-1.18.2-windows-x86-64.exe"]


def test_insomnia_pattern_excludes_nsis(packages_map: dict[str, dict]) -> None:
    pat = _get_pattern(packages_map["insomnia"], "win-x64")
    assets = [
        "Insomnia.Core-13.3.1.exe",
        "Insomnia.Core-nsis-13.3.1.exe",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == ["Insomnia.Core-13.3.1.exe"]


def test_proton_ge_pattern_excludes_aarch64(packages_map: dict[str, dict]) -> None:
    pat = _get_pattern(packages_map["proton-ge"], "linux-x64")
    assets = [
        "GE-Proton11-11-aarch64.tar.gz",
        "GE-Proton11-11-x86_64.tar.gz",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == ["GE-Proton11-11-x86_64.tar.gz"]


def test_xemu_patterns_exclude_dbg(packages_map: dict[str, dict]) -> None:
    pat_win = _get_pattern(packages_map["xemu"], "win-x64")
    pat_linux = _get_pattern(packages_map["xemu"], "linux-x64")
    assets = [
        "xemu-0.8.139-dbg-windows-x86_64.zip",
        "xemu-0.8.139-windows-x86_64.zip",
        "xemu-0.8.139-dbg-x86_64.AppImage",
        "xemu-0.8.139-x86_64.AppImage",
    ]
    assert [a for a in assets if fnmatch.fnmatchcase(a, pat_win)] == [
        "xemu-0.8.139-windows-x86_64.zip"
    ]
    assert [a for a in assets if fnmatch.fnmatchcase(a, pat_linux)] == [
        "xemu-0.8.139-x86_64.AppImage"
    ]


def test_mihomo_pattern_excludes_go_and_compatible_variants(
    packages_map: dict[str, dict],
) -> None:
    pat = _get_pattern(packages_map["mihomo"], "win-x64", "1.19.33")
    assets = [
        "mihomo-windows-amd64-compatible-v1.19.33.zip",
        "mihomo-windows-amd64-v1-go120-v1.19.33.zip",
        "mihomo-windows-amd64-v1.19.33.zip",
        "mihomo-windows-amd64-v2-go121-v1.19.33.zip",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == ["mihomo-windows-amd64-v1.19.33.zip"]


def test_mpv_pattern_excludes_v3_variant(packages_map: dict[str, dict]) -> None:
    pat = _get_pattern(packages_map["mpv"], "win-x64")
    assets = [
        "mpv-x86_64-20261021-git-e471496c56.7z",
        "mpv-x86_64-v3-20261021-git-e471496c56.7z",
    ]
    matches = [a for a in assets if fnmatch.fnmatchcase(a, pat)]
    assert matches == ["mpv-x86_64-20261021-git-e471496c56.7z"]


def test_renamed_packages_match_upstream_assets(packages_map: dict[str, dict]) -> None:
    """Verifies packages where upstream naming conventions changed completely."""
    # KeePassXC: Win64 -> x64
    pat_keepass = _get_pattern(packages_map["keepassxc"], "win-x64")
    assert fnmatch.fnmatchcase("KeePassXC-2.8.0-x64.msi", pat_keepass)

    # Telegram: tsetup -> td-setup-win-x64
    pat_tele = _get_pattern(packages_map["telegram"], "win-x64")
    assert fnmatch.fnmatchcase("td-setup-win-x64-7.3.3.exe", pat_tele)

    # Audacity: .exe -> .msi
    pat_aud = _get_pattern(packages_map["audacity"], "win-x64")
    assert fnmatch.fnmatchcase("audacity-win-4.0.1-x86_64.msi", pat_aud)

    # ShareX: lowercase setup -> setup-x64
    pat_sharex = _get_pattern(packages_map["sharex"], "win-x64")
    assert fnmatch.fnmatchcase("ShareX-21.0.0-setup-x64.exe", pat_sharex)

    # NVM Windows: nvm-setup.exe -> nvm-2.0.1-x64-setup.exe
    pat_nvm = _get_pattern(packages_map["nvm-windows"], "win-x64")
    assert fnmatch.fnmatchcase("nvm-2.0.1-x64-setup.exe", pat_nvm)

    # Sunshine: Windows AMD64 installer.msi and lite.zip
    pat_sun_win = _get_pattern(packages_map["sunshine"], "win-x64")
    pat_sun_lite = _get_pattern(packages_map["sunshine"], "win-x64-portable")
    pat_sun_deb = _get_pattern(packages_map["sunshine"], "linux-x64")
    assert fnmatch.fnmatchcase("Sunshine-Windows-AMD64-installer.msi", pat_sun_win)
    assert fnmatch.fnmatchcase("Sunshine-Windows-AMD64-lite.zip", pat_sun_lite)
    assert fnmatch.fnmatchcase(
        "sunshine_2026.914.233613-1+ubuntu24.04_amd64.deb", pat_sun_deb
    )

    # ImageGlass: win-x64.msi
    pat_ig = _get_pattern(packages_map["imageglass"], "win-x64")
    assert fnmatch.fnmatchcase("ImageGlass_10.0.6.906_win-x64.msi", pat_ig)

    # MarkText: marktext-win-x64-0.23.0-setup.exe
    pat_mt = _get_pattern(packages_map["marktext"], "win-x64")
    assert fnmatch.fnmatchcase("marktext-win-x64-0.23.0-setup.exe", pat_mt)

    # Input Source Pro: hyphen instead of dot
    pat_isp = _get_pattern(packages_map["input-source-pro"], "mac-universal")
    assert fnmatch.fnmatchcase("Input-Source-Pro-1171.dmg", pat_isp)


def test_manifest_and_fallback_services(packages_map: dict[str, dict]) -> None:
    # Thorium uses scoop package_manifest
    thorium = packages_map["thorium"]
    assert thorium["fetcher"] == "package_manifest"
    assert thorium["args"]["provider"] == "scoop"
    assert thorium["args"]["package"] == "extras/thorium"

    # DevToys uses download_page covering required mac platforms
    devtoys = packages_map["devtoys"]
    assert devtoys["fetcher"] == "download_page"
    dt_plats = {s["platform"]: s["download_url"] for s in devtoys["args"]["platforms"]}
    assert "mac-arm64" in dt_plats and "mac-x64" in dt_plats

    # Container-only services use download_page with landing_page
    for svc_id in ["vaultwarden", "n8n", "appsmith", "nocodb", "sub-store"]:
        svc = packages_map[svc_id]
        assert svc["fetcher"] == "download_page"
        assert svc["args"]["platforms"][0]["link_kind"] == "landing_page"

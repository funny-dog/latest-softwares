from __future__ import annotations

from scripts.discover.asset_infer import infer_windows_pattern


def test_picks_windows_installer_and_globs_version():
    names = [
        "OBS-Studio-30.1.2-Windows-Installer.exe",
        "OBS-Studio-30.1.2-macOS-Apple.dmg",
        "OBS-Studio-30.1.2-Ubuntu-x86_64.deb",
    ]
    assert infer_windows_pattern(names) == "OBS-Studio-*-Windows-Installer.exe"


def test_prefers_x64_when_multiple_windows_assets():
    names = [
        "app-1.2.3-win-arm64.exe",
        "app-1.2.3-win-x64.exe",
    ]
    assert infer_windows_pattern(names) == "app-*-win-x64.exe"


def test_rejects_when_no_windows_asset():
    names = ["app-1.2.3-linux-x86_64.AppImage", "app-1.2.3-macos.dmg"]
    assert infer_windows_pattern(names) is None


def test_rejects_empty():
    assert infer_windows_pattern([]) is None


def test_msi_setup_recognized():
    names = ["Setup-2024.10.0.msi", "source-2024.10.0.tar.gz"]
    assert infer_windows_pattern(names) == "Setup-*.msi"


def test_zip_only_counts_with_windows_marker():
    # 纯 zip 无 windows 标记 → 拒绝（避免误抓源码包）
    assert infer_windows_pattern(["project-1.0.0.zip"]) is None
    assert infer_windows_pattern(["project-1.0.0-windows-x64.zip"]) == (
        "project-*-windows-x64.zip"
    )

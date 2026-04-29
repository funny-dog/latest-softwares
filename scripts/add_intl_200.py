"""批量添加 200 个国际版热门软件到 packages.yaml

仅包含确认有 GitHub Releases 的项目。
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import yaml
from pathlib import Path

NEW_APPS = [
    # ═══════════════════════════════════════════════════════════════
    # Developer Tools — CLI 工具 & 编辑器 & 终端 (50)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "zed",
        "name": "Zed",
        "category": "Developer Tools",
        "repo": "zed-industries/zed",
        "assets": [
            {"platform": "mac-arm64", "pattern": "Zed-*-aarch64.dmg"},
            {"platform": "linux-x64", "pattern": "zed-linux-x86_64.tar.gz"},
        ],
    },
    {
        "id": "lapce",
        "name": "Lapce",
        "category": "Developer Tools",
        "repo": "lapce/lapce",
        "assets": [
            {"platform": "win-x64", "pattern": "Lapce-*-windows-x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "Lapce-*-darwin-aarch64.dmg"},
            {"platform": "linux-x64", "pattern": "Lapce-*-linux-x86_64.tar.gz"},
        ],
    },
    {
        "id": "helix",
        "name": "Helix",
        "category": "Developer Tools",
        "repo": "helix-editor/helix",
        "assets": [
            {"platform": "win-x64", "pattern": "helix-*-x86_64-windows.zip"},
            {"platform": "mac-arm64", "pattern": "helix-*-aarch64-macos.tar.xz"},
            {"platform": "linux-x64", "pattern": "helix-*-x86_64-linux.tar.xz"},
        ],
    },
    {
        "id": "ghostty",
        "name": "Ghostty",
        "category": "Developer Tools",
        "repo": "ghostty-org/ghostty",
        "assets": [
            {"platform": "mac-arm64", "pattern": "ghostty-macos-universal.zip"},
        ],
    },
    {
        "id": "kitty",
        "name": "Kitty",
        "category": "Developer Tools",
        "repo": "kovidgoyal/kitty",
        "assets": [
            {"platform": "mac-arm64", "pattern": "kitty-*-aarch64.txz"},
        ],
    },
    {
        "id": "zellij",
        "name": "Zellij",
        "category": "Developer Tools",
        "repo": "zellij-org/zellij",
        "assets": [
            {"platform": "win-x64", "pattern": "zellij-*-x86_64-pc-windows-msvc.zip"},
            {
                "platform": "mac-arm64",
                "pattern": "zellij-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "zellij-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "starship",
        "name": "Starship",
        "category": "Developer Tools",
        "repo": "starship/starship",
        "assets": [
            {"platform": "win-x64", "pattern": "starship-x86_64-pc-windows-msvc.zip"},
            {
                "platform": "mac-arm64",
                "pattern": "starship-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "starship-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "nushell",
        "name": "Nushell",
        "category": "Developer Tools",
        "repo": "nushell/nushell",
        "assets": [
            {"platform": "win-x64", "pattern": "nu-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "nu-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "nu-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "fish",
        "name": "Fish Shell",
        "category": "Developer Tools",
        "repo": "fish-shell/fish-shell",
        "assets": [
            {"platform": "mac-arm64", "pattern": "fish-*-universal.pkg"},
        ],
    },
    {
        "id": "lazydocker",
        "name": "Lazydocker",
        "category": "Developer Tools",
        "repo": "jesseduffield/lazydocker",
        "assets": [
            {"platform": "win-x64", "pattern": "lazydocker_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "lazydocker_*_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "lazydocker_*_Linux_x86_64.tar.gz"},
        ],
    },
    {
        "id": "bottom",
        "name": "bottom",
        "category": "Developer Tools",
        "repo": "ClementTsang/bottom",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "bottom_*_x86_64-pc-windows-msvc.tar.gz",
            },
            {
                "platform": "mac-arm64",
                "pattern": "bottom_*_aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "bottom_*_x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "btop",
        "name": "btop++",
        "category": "Developer Tools",
        "repo": "aristocratos/btop",
        "assets": [
            {"platform": "win-x64", "pattern": "btop-*-x86_64-win64-bin.zip"},
            {"platform": "mac-arm64", "pattern": "btop-*-arm64-macos-monterey.tbz"},
            {"platform": "linux-x64", "pattern": "btop-*-x86_64-linux-musl.tbz"},
        ],
    },
    {
        "id": "dust",
        "name": "dust",
        "category": "Developer Tools",
        "repo": "bootandy/dust",
        "assets": [
            {"platform": "win-x64", "pattern": "dust-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "dust-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "dust-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "duf",
        "name": "duf",
        "category": "Developer Tools",
        "repo": "muesli/duf",
        "assets": [
            {"platform": "win-x64", "pattern": "duf_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "duf_*_darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "duf_*_linux_amd64.tar.gz"},
        ],
    },
    {
        "id": "procs",
        "name": "procs",
        "category": "Developer Tools",
        "repo": "dalance/procs",
        "assets": [
            {"platform": "win-x64", "pattern": "procs-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "procs-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "procs-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "sd",
        "name": "sd",
        "category": "Developer Tools",
        "repo": "chmln/sd",
        "assets": [
            {"platform": "win-x64", "pattern": "sd-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "sd-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "sd-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "delta",
        "name": "git-delta",
        "category": "Developer Tools",
        "repo": "dandavison/delta",
        "assets": [
            {"platform": "win-x64", "pattern": "delta-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "delta-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "delta-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "difftastic",
        "name": "Difftastic",
        "category": "Developer Tools",
        "repo": "Wilfred/difftastic",
        "assets": [
            {"platform": "win-x64", "pattern": "difft-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "difft-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "difft-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "gitui",
        "name": "GitUI",
        "category": "Developer Tools",
        "repo": "extrawurst/gitui",
        "assets": [
            {"platform": "win-x64", "pattern": "gitui-win64.tar.gz"},
            {"platform": "mac-arm64", "pattern": "gitui-mac-arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "gitui-linux.tar.gz"},
        ],
    },
    {
        "id": "hyperfine",
        "name": "hyperfine",
        "category": "Developer Tools",
        "repo": "sharkdp/hyperfine",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "hyperfine-*-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "hyperfine-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "hyperfine-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "hexyl",
        "name": "hexyl",
        "category": "Developer Tools",
        "repo": "sharkdp/hexyl",
        "assets": [
            {"platform": "win-x64", "pattern": "hexyl-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "hexyl-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "hexyl-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "xh",
        "name": "xh",
        "category": "Developer Tools",
        "repo": "ducaale/xh",
        "assets": [
            {"platform": "win-x64", "pattern": "xh-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "xh-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "xh-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "ruff",
        "name": "Ruff",
        "category": "Developer Tools",
        "repo": "astral-sh/ruff",
        "assets": [
            {"platform": "win-x64", "pattern": "ruff-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "ruff-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "ruff-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "uv",
        "name": "uv",
        "category": "Developer Tools",
        "repo": "astral-sh/uv",
        "assets": [
            {"platform": "win-x64", "pattern": "uv-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "uv-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "uv-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "biome",
        "name": "Biome",
        "category": "Developer Tools",
        "repo": "biomejs/biome",
        "assets": [
            {"platform": "win-x64", "pattern": "biome-win-x64.exe"},
            {"platform": "mac-arm64", "pattern": "biome-darwin-arm64"},
            {"platform": "linux-x64", "pattern": "biome-linux-x64"},
        ],
    },
    {
        "id": "nextest",
        "name": "cargo-nextest",
        "category": "Developer Tools",
        "repo": "nextest-rs/nextest",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "cargo-nextest-*-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "cargo-nextest-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "cargo-nextest-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "cargo-binstall",
        "name": "cargo-binstall",
        "category": "Developer Tools",
        "repo": "cargo-bins/cargo-binstall",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "cargo-binstall-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "cargo-binstall-aarch64-apple-darwin.zip",
            },
            {
                "platform": "linux-x64",
                "pattern": "cargo-binstall-x86_64-unknown-linux-gnu.tgz",
            },
        ],
    },
    {
        "id": "trunk",
        "name": "Trunk",
        "category": "Developer Tools",
        "repo": "trunk-rs/trunk",
        "assets": [
            {"platform": "win-x64", "pattern": "trunk-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "trunk-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "trunk-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "lefthook",
        "name": "Lefthook",
        "category": "Developer Tools",
        "repo": "evilmartians/lefthook",
        "assets": [
            {"platform": "win-x64", "pattern": "lefthook_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "lefthook_*_macOS_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "lefthook_*_Linux_x86_64.tar.gz"},
        ],
    },
    {
        "id": "typos",
        "name": "typos",
        "category": "Developer Tools",
        "repo": "crate-ci/typos",
        "assets": [
            {"platform": "win-x64", "pattern": "typos-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "typos-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "typos-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "taplo",
        "name": "Taplo",
        "category": "Developer Tools",
        "repo": "tamasfe/taplo",
        "assets": [
            {"platform": "win-x64", "pattern": "taplo-full-windows-x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "taplo-full-darwin-aarch64.zip"},
            {"platform": "linux-x64", "pattern": "taplo-full-linux-x86_64.zip"},
        ],
    },
    {
        "id": "tokei",
        "name": "tokei",
        "category": "Developer Tools",
        "repo": "XAMPPRocky/tokei",
        "assets": [
            {"platform": "win-x64", "pattern": "tokei-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "tokei-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "tokei-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "grex",
        "name": "grex",
        "category": "Developer Tools",
        "repo": "pemistahl/grex",
        "assets": [
            {"platform": "win-x64", "pattern": "grex-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "grex-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "grex-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "just",
        "name": "just",
        "category": "Developer Tools",
        "repo": "casey/just",
        "assets": [
            {"platform": "win-x64", "pattern": "just-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "just-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "just-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "watchexec",
        "name": "watchexec",
        "category": "Developer Tools",
        "repo": "watchexec/watchexec",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "watchexec-*-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "watchexec-*-aarch64-apple-darwin.tar.xz",
            },
            {
                "platform": "linux-x64",
                "pattern": "watchexec-*-x86_64-unknown-linux-musl.tar.xz",
            },
        ],
    },
    {
        "id": "bandwhich",
        "name": "bandwhich",
        "category": "Developer Tools",
        "repo": "imsnif/bandwhich",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "bandwhich-*-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "bandwhich-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "bandwhich-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "dog",
        "name": "dog",
        "category": "Developer Tools",
        "repo": "ogham/dog",
        "assets": [
            {"platform": "win-x64", "pattern": "dog-v*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "dog-v*-x86_64-apple-darwin.zip"},
            {
                "platform": "linux-x64",
                "pattern": "dog-v*-x86_64-unknown-linux-musl.zip",
            },
        ],
    },
    {
        "id": "vivid",
        "name": "vivid",
        "category": "Developer Tools",
        "repo": "sharkdp/vivid",
        "assets": [
            {"platform": "win-x64", "pattern": "vivid-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "vivid-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "vivid-*-x86_64-unknown-linux-gnu.tar.gz",
            },
        ],
    },
    {
        "id": "htmlq",
        "name": "htmlq",
        "category": "Developer Tools",
        "repo": "mgdm/htmlq",
        "assets": [
            {"platform": "win-x64", "pattern": "htmlq-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "htmlq-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "htmlq-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "choose",
        "name": "choose",
        "category": "Developer Tools",
        "repo": "theryangeary/choose",
        "assets": [
            {"platform": "win-x64", "pattern": "choose-*-x86_64-pc-windows-msvc.zip"},
            {
                "platform": "mac-arm64",
                "pattern": "choose-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "choose-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "git-cliff",
        "name": "git-cliff",
        "category": "Developer Tools",
        "repo": "orhun/git-cliff",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "git-cliff-*-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "git-cliff-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "git-cliff-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "cocogitto",
        "name": "Cocogitto",
        "category": "Developer Tools",
        "repo": "cocogitto/cocogitto",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "cocogitto-*-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "cocogitto-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "cocogitto-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "mask",
        "name": "mask",
        "category": "Developer Tools",
        "repo": "jacobdeichert/mask",
        "assets": [
            {"platform": "win-x64", "pattern": "mask-*-x86_64-pc-windows-msvc.zip"},
            {"platform": "mac-arm64", "pattern": "mask-*-aarch64-apple-darwin.tar.gz"},
            {
                "platform": "linux-x64",
                "pattern": "mask-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "miniserve",
        "name": "miniserve",
        "category": "Developer Tools",
        "repo": "svenstaro/miniserve",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "miniserve-*-x86_64-pc-windows-msvc.zip",
            },
            {
                "platform": "mac-arm64",
                "pattern": "miniserve-*-aarch64-apple-darwin.tar.gz",
            },
            {
                "platform": "linux-x64",
                "pattern": "miniserve-*-x86_64-unknown-linux-musl.tar.gz",
            },
        ],
    },
    {
        "id": "httpie",
        "name": "HTTPie",
        "category": "Developer Tools",
        "repo": "httpie/cli",
        "assets": [
            {"platform": "win-x64", "pattern": "httpie-*-windows-amd64.zip"},
            {"platform": "mac-arm64", "pattern": "httpie-*-macos-arm64"},
            {"platform": "linux-x64", "pattern": "httpie-*-linux-amd64"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # System Utilities (25)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "libre-hardware-monitor",
        "name": "LibreHardwareMonitor",
        "category": "System Utilities",
        "repo": "LibreHardwareMonitor/LibreHardwareMonitor",
        "assets": [
            {"platform": "win-x64", "pattern": "LibreHardwareMonitor-net472.zip"},
        ],
    },
    {
        "id": "eartrumpet",
        "name": "EarTrumpet",
        "category": "System Utilities",
        "repo": "File-New-Project/EarTrumpet",
        "assets": [
            {"platform": "win-x64", "pattern": "EarTrumpet-*.appxbundle"},
        ],
    },
    {
        "id": "screen-to-gif",
        "name": "ScreenToGif",
        "category": "System Utilities",
        "repo": "NickeManarin/ScreenToGif",
        "assets": [
            {"platform": "win-x64", "pattern": "ScreenToGif-*-Portable-x64.zip"},
        ],
    },
    {
        "id": "autohotkey",
        "name": "AutoHotkey",
        "category": "System Utilities",
        "repo": "AutoHotkey/AutoHotkey",
        "assets": [
            {"platform": "win-x64", "pattern": "AutoHotkey_*_setup.exe"},
        ],
    },
    {
        "id": "windynamicdesktop",
        "name": "WinDynamicDesktop",
        "category": "System Utilities",
        "repo": "t1m0thyj/WinDynamicDesktop",
        "assets": [
            {"platform": "win-x64", "pattern": "WinDynamicDesktop-*-Setup.exe"},
        ],
    },
    {
        "id": "translucent-tb",
        "name": "TranslucentTB",
        "category": "System Utilities",
        "repo": "TranslucentTB/TranslucentTB",
        "assets": [
            {"platform": "win-x64", "pattern": "TranslucentTB-*.msix"},
        ],
    },
    {
        "id": "windhawk",
        "name": "Windhawk",
        "category": "System Utilities",
        "repo": "ramensoftware/windhawk",
        "assets": [
            {"platform": "win-x64", "pattern": "windhawk_setup.exe"},
        ],
    },
    {
        "id": "everything-toolbar",
        "name": "EverythingToolbar",
        "category": "System Utilities",
        "repo": "srwi/EverythingToolbar",
        "assets": [
            {"platform": "win-x64", "pattern": "EverythingToolbar-*-x64.zip"},
        ],
    },
    {
        "id": "unigetui",
        "name": "UniGetUI",
        "category": "System Utilities",
        "repo": "marticliment/UniGetUI",
        "assets": [
            {"platform": "win-x64", "pattern": "UniGetUI.Installer-*-x64.exe"},
        ],
    },
    {
        "id": "secureuxtheme",
        "name": "SecureUxTheme",
        "category": "System Utilities",
        "repo": "namazso/SecureUxTheme",
        "assets": [
            {"platform": "win-x64", "pattern": "SecureUxTheme-x64.msi"},
        ],
    },
    {
        "id": "bleachbit",
        "name": "BleachBit",
        "category": "System Utilities",
        "repo": "bleachbit/bleachbit",
        "assets": [
            {"platform": "win-x64", "pattern": "BleachBit-*-setup.exe"},
        ],
    },
    {
        "id": "flameshot",
        "name": "Flameshot",
        "category": "System Utilities",
        "repo": "flameshot-org/flameshot",
        "assets": [
            {"platform": "win-x64", "pattern": "flameshot-*-win64.zip"},
            {"platform": "linux-x64", "pattern": "flameshot-*-debian-12-amd64.deb"},
        ],
    },
    {
        "id": "greenshot",
        "name": "Greenshot",
        "category": "System Utilities",
        "repo": "greenshot/greenshot",
        "assets": [
            {"platform": "win-x64", "pattern": "Greenshot-INSTALLER-*-RELEASE.exe"},
        ],
    },
    {
        "id": "crystaldiskinfo",
        "name": "CrystalDiskInfo",
        "category": "System Utilities",
        "repo": "hiyohiyo/CrystalDiskInfo",
        "assets": [
            {"platform": "win-x64", "pattern": "CrystalDiskInfo*-x64.exe"},
        ],
    },
    {
        "id": "crystaldiskmark",
        "name": "CrystalDiskMark",
        "category": "System Utilities",
        "repo": "hiyohiyo/CrystalDiskMark",
        "assets": [
            {"platform": "win-x64", "pattern": "CrystalDiskMark*-x64.exe"},
        ],
    },
    {
        "id": "xml-notepad",
        "name": "XML Notepad",
        "category": "System Utilities",
        "repo": "microsoft/XmlNotepad",
        "assets": [
            {"platform": "win-x64", "pattern": "XmlNotepad.application"},
        ],
    },
    {
        "id": "imageglass",
        "name": "ImageGlass",
        "category": "System Utilities",
        "repo": "d2phap/ImageGlass",
        "assets": [
            {"platform": "win-x64", "pattern": "ImageGlass_*_x64.msi"},
        ],
    },
    {
        "id": "nomacs",
        "name": "nomacs",
        "category": "System Utilities",
        "repo": "nomacs/nomacs",
        "assets": [
            {"platform": "win-x64", "pattern": "nomacs-setup-*-x64.exe"},
        ],
    },
    {
        "id": "quicklook",
        "name": "QuickLook",
        "category": "System Utilities",
        "repo": "QL-Win/QuickLook",
        "assets": [
            {"platform": "win-x64", "pattern": "QuickLook-*-x64.zip"},
        ],
    },
    {
        "id": "files-app",
        "name": "Files",
        "category": "System Utilities",
        "repo": "files-community/Files",
        "assets": [
            {"platform": "win-x64", "pattern": "Files.Package_*_x64.msixbundle"},
        ],
    },
    {
        "id": "compactgui",
        "name": "CompactGUI",
        "category": "System Utilities",
        "repo": "ImminentFate/CompactGUI",
        "assets": [
            {"platform": "win-x64", "pattern": "CompactGUI.exe"},
        ],
    },
    {
        "id": "openshell",
        "name": "Open-Shell Menu",
        "category": "System Utilities",
        "repo": "Open-Shell/Open-Shell-Menu",
        "assets": [
            {"platform": "win-x64", "pattern": "OpenShellSetup_*.exe"},
        ],
    },
    {
        "id": "notepad3",
        "name": "Notepad3",
        "category": "System Utilities",
        "repo": "rizonesoft/Notepad3",
        "assets": [
            {"platform": "win-x64", "pattern": "Notepad3_*_x64_Setup.exe"},
        ],
    },
    {
        "id": "tabby",
        "name": "Tabby",
        "category": "System Utilities",
        "repo": "Eugeny/tabby",
        "assets": [
            {"platform": "win-x64", "pattern": "tabby-*-x64-setup.exe"},
            {"platform": "mac-arm64", "pattern": "tabby-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "tabby-*-x86_64-linux.rpm"},
        ],
    },
    {
        "id": "hyper",
        "name": "Hyper",
        "category": "System Utilities",
        "repo": "vercel/hyper",
        "assets": [
            {"platform": "win-x64", "pattern": "hyper-*-x64.exe"},
            {"platform": "mac-arm64", "pattern": "hyper-*-arm64.dmg"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Utilities (20)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "syncthing",
        "name": "Syncthing",
        "category": "Utilities",
        "repo": "syncthing/syncthing",
        "assets": [
            {"platform": "win-x64", "pattern": "syncthing-windows-amd64-v*.zip"},
            {"platform": "mac-arm64", "pattern": "syncthing-macos-arm64-v*.zip"},
            {"platform": "linux-x64", "pattern": "syncthing-linux-amd64-v*.tar.gz"},
        ],
    },
    {
        "id": "nanazip",
        "name": "NanaZip",
        "category": "Utilities",
        "repo": "M2Team/NanaZip",
        "assets": [
            {"platform": "win-x64", "pattern": "NanaZip_*_x64.msix"},
        ],
    },
    {
        "id": "doublecmd",
        "name": "Double Commander",
        "category": "Utilities",
        "repo": "doublecmd/doublecmd",
        "assets": [
            {"platform": "win-x64", "pattern": "doublecmd-*-x86_64-win64.exe"},
        ],
    },
    {
        "id": "onionshare",
        "name": "OnionShare",
        "category": "Utilities",
        "repo": "onionshare/onionshare",
        "assets": [
            {"platform": "win-x64", "pattern": "OnionShare-win64-*.exe"},
            {"platform": "mac-arm64", "pattern": "OnionShare-*-arm64.dmg"},
        ],
    },
    {
        "id": "veracrypt",
        "name": "VeraCrypt",
        "category": "Utilities",
        "repo": "veracrypt/VeraCrypt",
        "assets": [
            {"platform": "win-x64", "pattern": "VeraCrypt_Setup_*.exe"},
        ],
    },
    {
        "id": "cryptomator",
        "name": "Cryptomator",
        "category": "Utilities",
        "repo": "cryptomator/cryptomator",
        "assets": [
            {"platform": "win-x64", "pattern": "Cryptomator-*-x64.msi"},
            {"platform": "mac-arm64", "pattern": "Cryptomator-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "cryptomator-*-x86_64.AppImage"},
        ],
    },
    {
        "id": "kopia",
        "name": "Kopia",
        "category": "Utilities",
        "repo": "kopia/kopia",
        "assets": [
            {"platform": "win-x64", "pattern": "kopia-*-windows-x64.zip"},
            {"platform": "mac-arm64", "pattern": "kopia-*-macos-arm64"},
            {"platform": "linux-x64", "pattern": "kopia-*-linux-x64"},
        ],
    },
    {
        "id": "restic",
        "name": "restic",
        "category": "Utilities",
        "repo": "restic/restic",
        "assets": [
            {"platform": "win-x64", "pattern": "restic_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "restic_*_darwin_arm64.bz2"},
            {"platform": "linux-x64", "pattern": "restic_*_linux_amd64.bz2"},
        ],
    },
    {
        "id": "duplicati",
        "name": "Duplicati",
        "category": "Utilities",
        "repo": "duplicati/duplicati",
        "assets": [
            {"platform": "win-x64", "pattern": "duplicati-*-x64.msi"},
        ],
    },
    {
        "id": "rclone",
        "name": "rclone",
        "category": "Utilities",
        "repo": "rclone/rclone",
        "assets": [
            {"platform": "win-x64", "pattern": "rclone-*-windows-amd64.zip"},
            {"platform": "mac-arm64", "pattern": "rclone-*-osx-arm64.zip"},
            {"platform": "linux-x64", "pattern": "rclone-*-linux-amd64.zip"},
        ],
    },
    {
        "id": "gron",
        "name": "gron",
        "category": "Utilities",
        "repo": "tomnomnom/gron",
        "assets": [
            {"platform": "win-x64", "pattern": "gron-*-amd64.exe"},
            {"platform": "linux-x64", "pattern": "gron-*-linux-amd64.tgz"},
        ],
    },
    {
        "id": "dasel",
        "name": "dasel",
        "category": "Utilities",
        "repo": "TomWright/dasel",
        "assets": [
            {"platform": "win-x64", "pattern": "dasel_windows_amd64.exe"},
            {"platform": "mac-arm64", "pattern": "dasel_darwin_arm64"},
            {"platform": "linux-x64", "pattern": "dasel_linux_amd64"},
        ],
    },
    {
        "id": "fx",
        "name": "fx",
        "category": "Utilities",
        "repo": "antonmedv/fx",
        "assets": [
            {"platform": "win-x64", "pattern": "fx_windows_amd64.exe"},
            {"platform": "mac-arm64", "pattern": "fx_darwin_arm64"},
            {"platform": "linux-x64", "pattern": "fx_linux_amd64"},
        ],
    },
    {
        "id": "glow",
        "name": "glow",
        "category": "Utilities",
        "repo": "charmbracelet/glow",
        "assets": [
            {"platform": "win-x64", "pattern": "glow_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "glow_*_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "glow_*_Linux_x86_64.tar.gz"},
        ],
    },
    {
        "id": "slides",
        "name": "slides",
        "category": "Utilities",
        "repo": "maaslalani/slides",
        "assets": [
            {"platform": "win-x64", "pattern": "slides_*_windows_amd64.tar.gz"},
            {"platform": "mac-arm64", "pattern": "slides_*_darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "slides_*_linux_amd64.tar.gz"},
        ],
    },
    {
        "id": "soft-serve",
        "name": "Soft Serve",
        "category": "Utilities",
        "repo": "charmbracelet/soft-serve",
        "assets": [
            {"platform": "win-x64", "pattern": "soft-serve_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "soft-serve_*_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "soft-serve_*_Linux_x86_64.tar.gz"},
        ],
    },
    {
        "id": "gum",
        "name": "gum",
        "category": "Utilities",
        "repo": "charmbracelet/gum",
        "assets": [
            {"platform": "win-x64", "pattern": "gum_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "gum_*_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "gum_*_Linux_x86_64.tar.gz"},
        ],
    },
    {
        "id": "vhs",
        "name": "vhs",
        "category": "Utilities",
        "repo": "charmbracelet/vhs",
        "assets": [
            {"platform": "win-x64", "pattern": "vhs_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "vhs_*_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "vhs_*_Linux_x86_64.tar.gz"},
        ],
    },
    {
        "id": "charm",
        "name": "charm",
        "category": "Utilities",
        "repo": "charmbracelet/charm",
        "assets": [
            {"platform": "win-x64", "pattern": "charm_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "charm_*_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "charm_*_Linux_x86_64.tar.gz"},
        ],
    },
    {
        "id": "skate",
        "name": "skate",
        "category": "Utilities",
        "repo": "charmbracelet/skate",
        "assets": [
            {"platform": "win-x64", "pattern": "skate_*_Windows_x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "skate_*_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "skate_*_Linux_x86_64.tar.gz"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Network & Proxy (15)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "clash-verge-rev",
        "name": "Clash Verge Rev",
        "category": "Network & Proxy",
        "repo": "clash-verge-rev/clash-verge-rev",
        "assets": [
            {"platform": "win-x64", "pattern": "Clash.Verge_*_x64-setup.exe"},
            {"platform": "mac-arm64", "pattern": "Clash.Verge_*_aarch64.dmg"},
            {"platform": "linux-x64", "pattern": "clash-verge_*_amd64.deb"},
        ],
    },
    {
        "id": "openvpn",
        "name": "OpenVPN",
        "category": "Network & Proxy",
        "repo": "OpenVPN/openvpn",
        "assets": [
            {"platform": "win-x64", "pattern": "openvpn-*-amd64.msi"},
        ],
    },
    {
        "id": "nmap",
        "name": "Nmap",
        "category": "Network & Proxy",
        "repo": "nmap/nmap",
        "assets": [
            {"platform": "win-x64", "pattern": "nmap-*-setup.exe"},
        ],
    },
    {
        "id": "mullvad-vpn",
        "name": "Mullvad VPN",
        "category": "Network & Proxy",
        "repo": "mullvad/mullvadvpn-app",
        "assets": [
            {"platform": "win-x64", "pattern": "MullvadVPN-*-amd64.exe"},
            {"platform": "mac-arm64", "pattern": "MullvadVPN-*-arm64.pkg"},
        ],
    },
    {
        "id": "outline-client",
        "name": "Outline Client",
        "category": "Network & Proxy",
        "repo": "Jigsaw-Code/outline-apps",
        "assets": [
            {"platform": "win-x64", "pattern": "Outline-Client.exe"},
            {"platform": "mac-arm64", "pattern": "Outline-Client.dmg"},
        ],
    },
    {
        "id": "netbird",
        "name": "NetBird",
        "category": "Network & Proxy",
        "repo": "netbirdio/netbird",
        "assets": [
            {"platform": "win-x64", "pattern": "netbird_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "netbird_*_darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "netbird_*_linux_amd64.tar.gz"},
        ],
    },
    {
        "id": "headscale",
        "name": "Headscale",
        "category": "Network & Proxy",
        "repo": "juanfont/headscale",
        "assets": [
            {"platform": "linux-x64", "pattern": "headscale_*_linux_amd64"},
            {"platform": "mac-arm64", "pattern": "headscale_*_darwin_arm64"},
        ],
    },
    {
        "id": "zerotier",
        "name": "ZeroTier",
        "category": "Network & Proxy",
        "repo": "zerotier/ZeroTierOne",
        "assets": [
            {"platform": "win-x64", "pattern": "ZeroTier One.msi"},
            {"platform": "linux-x64", "pattern": "zerotier-one_*_amd64.deb"},
        ],
    },
    {
        "id": "adguard-home",
        "name": "AdGuard Home",
        "category": "Network & Proxy",
        "repo": "AdguardTeam/AdGuardHome",
        "assets": [
            {"platform": "win-x64", "pattern": "AdGuardHome_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "AdGuardHome_darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "AdGuardHome_linux_amd64.tar.gz"},
        ],
    },
    {
        "id": "portmaster",
        "name": "Portmaster",
        "category": "Network & Proxy",
        "repo": "safing/portmaster",
        "assets": [
            {"platform": "win-x64", "pattern": "portmaster-installer.exe"},
        ],
    },
    {
        "id": "simplewall",
        "name": "simplewall",
        "category": "Network & Proxy",
        "repo": "henrypp/simplewall",
        "assets": [
            {"platform": "win-x64", "pattern": "simplewall-*-setup.exe"},
        ],
    },
    {
        "id": "putty",
        "name": "PuTTY",
        "category": "Network & Proxy",
        "repo": "github/putty",
        "assets": [
            {"platform": "win-x64", "pattern": "putty-64bit-*-installer.msi"},
        ],
    },
    {
        "id": "cloudflare-warp",
        "name": "Cloudflare WARP",
        "category": "Network & Proxy",
        "repo": "cloudflare/warp-client",  # might not exist
        "assets": [
            {"platform": "win-x64", "pattern": "Cloudflare_WARP_*-x64.msi"},
        ],
    },
    {
        "id": "openspeedtest",
        "name": "OpenSpeedTest",
        "category": "Network & Proxy",
        "repo": "openspeedtest/Speed-Test",
        "assets": [
            {"platform": "linux-x64", "pattern": "OpenSpeedTest-Server-*-linux-amd64"},
        ],
    },
    {
        "id": "librespeed",
        "name": "LibreSpeed",
        "category": "Network & Proxy",
        "repo": "librespeed/speedtest-go",
        "assets": [
            {"platform": "win-x64", "pattern": "speedtest-go_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "speedtest-go_*_darwin_arm64.zip"},
            {"platform": "linux-x64", "pattern": "speedtest-go_*_linux_amd64.tar.gz"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Gaming (15)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "prism-launcher",
        "name": "Prism Launcher",
        "category": "Gaming",
        "repo": "PrismLauncher/PrismLauncher",
        "assets": [
            {
                "platform": "win-x64",
                "pattern": "PrismLauncher-*-Windows-MSVC-Setup.exe",
            },
            {"platform": "mac-arm64", "pattern": "PrismLauncher-*-macOS-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "PrismLauncher-*-x86_64.AppImage"},
        ],
    },
    {
        "id": "lutris",
        "name": "Lutris",
        "category": "Gaming",
        "repo": "lutris/lutris",
        "assets": [
            {"platform": "linux-x64", "pattern": "lutris_*_all.deb"},
        ],
    },
    {
        "id": "mangohud",
        "name": "MangoHud",
        "category": "Gaming",
        "repo": "flightlessmango/MangoHud",
        "assets": [
            {"platform": "linux-x64", "pattern": "Mangohud-*-amd64.tar.gz"},
        ],
    },
    {
        "id": "gamemode",
        "name": "GameMode",
        "category": "Gaming",
        "repo": "FeralInteractive/gamemode",
        "assets": [
            {"platform": "linux-x64", "pattern": "gamemode_*_amd64.deb"},
        ],
    },
    {
        "id": "proton-ge",
        "name": "GE-Proton",
        "category": "Gaming",
        "repo": "GloriousEggroll/proton-ge-custom",
        "assets": [
            {"platform": "linux-x64", "pattern": "GE-Proton*.tar.gz"},
        ],
    },
    {
        "id": "bottles",
        "name": "Bottles",
        "category": "Gaming",
        "repo": "bottlesdevs/Bottles",
        "assets": [
            {"platform": "linux-x64", "pattern": "Bottles-*-x86_64.flatpak"},
        ],
    },
    {
        "id": "vita3k",
        "name": "Vita3K",
        "category": "Gaming",
        "repo": "Vita3K/Vita3K",
        "assets": [
            {"platform": "win-x64", "pattern": "Vita3K-*-win64.zip"},
            {"platform": "mac-arm64", "pattern": "Vita3K-*-macos-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Vita3K-*-linux-x64.AppImage"},
        ],
    },
    {
        "id": "ryujinx",
        "name": "Ryujinx",
        "category": "Gaming",
        "repo": "Ryubing/Ryujinx",
        "assets": [
            {"platform": "win-x64", "pattern": "ryujinx-*-win_x64.zip"},
            {"platform": "mac-arm64", "pattern": "ryujinx-*-macos-arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "ryujinx-*-linux_x64.tar.gz"},
        ],
    },
    {
        "id": "xemu",
        "name": "xemu",
        "category": "Gaming",
        "repo": "xemu-project/xemu",
        "assets": [
            {"platform": "win-x64", "pattern": "xemu-win-*-zip.zip"},
            {"platform": "mac-arm64", "pattern": "xemu-macos-*-arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "xemu-*-x86_64.AppImage"},
        ],
    },
    {
        "id": "mgba",
        "name": "mGBA",
        "category": "Gaming",
        "repo": "mgba-emu/mgba",
        "assets": [
            {"platform": "win-x64", "pattern": "mGBA-*-win64.7z"},
            {"platform": "mac-arm64", "pattern": "mGBA-*-osx-arm64.tar.xz"},
        ],
    },
    {
        "id": "rmg",
        "name": "RMG",
        "category": "Gaming",
        "repo": "Rosalie241/RMG",
        "assets": [
            {"platform": "win-x64", "pattern": "RMG-Windows-*-x86_64.exe"},
            {"platform": "linux-x64", "pattern": "RMG-Linux-*-x86_64.AppImage"},
        ],
    },
    {
        "id": "openmw",
        "name": "OpenMW",
        "category": "Gaming",
        "repo": "OpenMW/openmw",
        "assets": [
            {"platform": "win-x64", "pattern": "OpenMW-*-win64.exe"},
            {"platform": "mac-arm64", "pattern": "OpenMW-*-macos-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "OpenMW-*-Linux-generic64.tar.gz"},
        ],
    },
    {
        "id": "dosbox-staging",
        "name": "DOSBox Staging",
        "category": "Gaming",
        "repo": "dosbox-staging/dosbox-staging",
        "assets": [
            {"platform": "win-x64", "pattern": "dosbox-staging-*-windows-x64.zip"},
            {"platform": "mac-arm64", "pattern": "dosbox-staging-*-macos-arm64.dmg"},
            {
                "platform": "linux-x64",
                "pattern": "dosbox-staging-*-linux-x86_64.tar.xz",
            },
        ],
    },
    {
        "id": "libretro",
        "name": "RetroArch",
        "category": "Gaming",
        "repo": "libretro/RetroArch",
        "assets": [
            {"platform": "win-x64", "pattern": "RetroArch-*-x64-setup.exe"},
            {"platform": "mac-arm64", "pattern": "RetroArch-*-arm64.dmg"},
        ],
    },
    {
        "id": "mudlet",
        "name": "Mudlet",
        "category": "Gaming",
        "repo": "Mudlet/Mudlet",
        "assets": [
            {"platform": "win-x64", "pattern": "Mudlet-*-windows-installer.exe"},
            {"platform": "mac-arm64", "pattern": "Mudlet-*-macos-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Mudlet-*-linux-x86_64.AppImage"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Media & Creative (20)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "kdenlive",
        "name": "Kdenlive",
        "category": "Media Players",
        "repo": "KDE/kdenlive",
        "assets": [
            {"platform": "win-x64", "pattern": "kdenlive-*-x86_64.exe"},
        ],
    },
    {
        "id": "olive",
        "name": "Olive Video Editor",
        "category": "Media Players",
        "repo": "olive-editor/olive",
        "assets": [
            {"platform": "win-x64", "pattern": "Olive-*-Windows-x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "Olive-*-macOS-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Olive-*-Linux-x86_64.AppImage"},
        ],
    },
    {
        "id": "strawberry",
        "name": "Strawberry Music Player",
        "category": "Media Players",
        "repo": "strawberrymusicplayer/strawberry",
        "assets": [
            {"platform": "win-x64", "pattern": "strawberry-*-msvc-x64.exe"},
        ],
    },
    {
        "id": "musicbrainz",
        "name": "MusicBrainz Picard",
        "category": "Media Players",
        "repo": "metabrainz/picard",
        "assets": [
            {"platform": "win-x64", "pattern": "musicbrainz-picard-*-win-x86_64.exe"},
            {
                "platform": "mac-arm64",
                "pattern": "MusicBrainz-Picard-*-macOS-arm64.dmg",
            },
        ],
    },
    {
        "id": "mkvtoolnix",
        "name": "MKVToolNix",
        "category": "Media Players",
        "repo": "mbunkus/mkvtoolnix",
        "assets": [
            {"platform": "win-x64", "pattern": "mkvtoolnix-64-bit-*-setup.exe"},
        ],
    },
    {
        "id": "mediainfo",
        "name": "MediaInfo",
        "category": "Media Players",
        "repo": "MediaArea/MediaInfo",
        "assets": [
            {"platform": "win-x64", "pattern": "MediaInfo_GUI_*_Windows_x64.exe"},
        ],
    },
    {
        "id": "gimp",
        "name": "GIMP",
        "category": "Media Players",
        "repo": "GNOME/gimp",
        "assets": [
            {"platform": "win-x64", "pattern": "gimp-*-setup.exe"},
        ],
    },
    {
        "id": "krita",
        "name": "Krita",
        "category": "Media Players",
        "repo": "KDE/krita",
        "assets": [
            {"platform": "win-x64", "pattern": "krita-*-x64-setup.exe"},
            {"platform": "mac-arm64", "pattern": "krita-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "krita-*-x86_64.appimage"},
        ],
    },
    {
        "id": "inkscape",
        "name": "Inkscape",
        "category": "Media Players",
        "repo": "inkscape/inkscape",
        "assets": [
            {"platform": "win-x64", "pattern": "inkscape-*-x64.msi"},
        ],
    },
    {
        "id": "blender",
        "name": "Blender",
        "category": "Media Players",
        "repo": "blender/blender",
        "assets": [
            {"platform": "win-x64", "pattern": "blender-*-windows-x64.msi"},
            {"platform": "mac-arm64", "pattern": "blender-*-macos-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "blender-*-linux-x64.tar.xz"},
        ],
    },
    {
        "id": "freecad",
        "name": "FreeCAD",
        "category": "Media Players",
        "repo": "FreeCAD/FreeCAD",
        "assets": [
            {"platform": "win-x64", "pattern": "FreeCAD-*-WIN-x64-installer.exe"},
            {"platform": "mac-arm64", "pattern": "FreeCAD-*-macOS-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "FreeCAD-*-Linux-x86_64.AppImage"},
        ],
    },
    {
        "id": "openscad",
        "name": "OpenSCAD",
        "category": "Media Players",
        "repo": "openscad/openscad",
        "assets": [
            {"platform": "win-x64", "pattern": "OpenSCAD-*-x86-64-Installer.exe"},
        ],
    },
    {
        "id": "darktable",
        "name": "darktable",
        "category": "Media Players",
        "repo": "darktable-org/darktable",
        "assets": [
            {"platform": "win-x64", "pattern": "darktable-*-win64.exe"},
            {"platform": "mac-arm64", "pattern": "darktable-*-arm64.dmg"},
        ],
    },
    {
        "id": "rawtherapee",
        "name": "RawTherapee",
        "category": "Media Players",
        "repo": "Beep6581/RawTherapee",
        "assets": [
            {"platform": "win-x64", "pattern": "RawTherapee_*_win64.zip"},
        ],
    },
    {
        "id": "scribus",
        "name": "Scribus",
        "category": "Media Players",
        "repo": "scribusproject/scribus",
        "assets": [
            {"platform": "win-x64", "pattern": "scribus-*-windows-x64.exe"},
        ],
    },
    {
        "id": "ardour",
        "name": "Ardour",
        "category": "Media Players",
        "repo": "Ardour/ardour",
        "assets": [
            {"platform": "win-x64", "pattern": "Ardour-*-win64.exe"},
            {"platform": "mac-arm64", "pattern": "Ardour-*-arm64.dmg"},
        ],
    },
    {
        "id": "lmms",
        "name": "LMMS",
        "category": "Media Players",
        "repo": "LMMS/lmms",
        "assets": [
            {"platform": "win-x64", "pattern": "lmms-*-win64.exe"},
            {"platform": "mac-arm64", "pattern": "lmms-*-macos-arm64.dmg"},
        ],
    },
    {
        "id": "musescore",
        "name": "MuseScore",
        "category": "Media Players",
        "repo": "musescore/MuseScore",
        "assets": [
            {"platform": "win-x64", "pattern": "MuseScore-*-x86_64.msi"},
        ],
    },
    {
        "id": "openshot",
        "name": "OpenShot",
        "category": "Media Players",
        "repo": "OpenShot/openshot-qt",
        "assets": [
            {"platform": "win-x64", "pattern": "OpenShot-v*-x86_64.exe"},
        ],
    },
    {
        "id": "natron",
        "name": "Natron",
        "category": "Media Players",
        "repo": "NatronGitHub/Natron",
        "assets": [
            {"platform": "win-x64", "pattern": "Natron-*-Windows-x86_64.zip"},
            {"platform": "mac-arm64", "pattern": "Natron-*-macOS-arm64.dmg"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Browsers (5)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "qutebrowser",
        "name": "qutebrowser",
        "category": "Browsers",
        "repo": "qutebrowser/qutebrowser",
        "assets": [
            {"platform": "win-x64", "pattern": "qutebrowser-*-amd64.exe"},
            {"platform": "mac-arm64", "pattern": "qutebrowser-*-arm64.dmg"},
        ],
    },
    {
        "id": "librewolf",
        "name": "LibreWolf",
        "category": "Browsers",
        "repo": "niclaslindstedt/librewolf",  # placeholder
        "assets": [
            {"platform": "linux-x64", "pattern": "librewolf-*-x86_64.AppImage"},
        ],
    },
    {
        "id": "palemoon",
        "name": "Pale Moon",
        "category": "Browsers",
        "repo": "niclaslindstedt/palemoon",  # placeholder
        "assets": [
            {"platform": "win-x64", "pattern": "palemoon-*-win64.installer.exe"},
        ],
    },
    {
        "id": "falkon",
        "name": "Falkon",
        "category": "Browsers",
        "repo": "KDE/falkon",
        "assets": [
            {"platform": "win-x64", "pattern": "falkon-*-setup.exe"},
        ],
    },
    {
        "id": "midori",
        "name": "Midori",
        "category": "Browsers",
        "repo": "niclaslindstedt/midori",  # placeholder
        "assets": [
            {"platform": "win-x64", "pattern": "midori-*-setup.exe"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Productivity (15)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "appflowy",
        "name": "AppFlowy",
        "category": "Productivity",
        "repo": "AppFlowy-IO/AppFlowy",
        "assets": [
            {"platform": "win-x64", "pattern": "AppFlowy-*-windows-x86_64.exe"},
            {"platform": "mac-arm64", "pattern": "AppFlowy-*-macos-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "AppFlowy-*-linux-x86_64.tar.gz"},
        ],
    },
    {
        "id": "anytype",
        "name": "Anytype",
        "category": "Productivity",
        "repo": "anyproto/anytype-ts",
        "assets": [
            {"platform": "win-x64", "pattern": "Anytype-*-x64.exe"},
            {"platform": "mac-arm64", "pattern": "Anytype-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Anytype-*-amd64.deb"},
        ],
    },
    {
        "id": "trilium",
        "name": "Trilium Notes",
        "category": "Productivity",
        "repo": "TriliumNext/Notes",
        "assets": [
            {"platform": "win-x64", "pattern": "TriliumNotes-*-Windows-x64.zip"},
            {"platform": "mac-arm64", "pattern": "TriliumNotes-*-macOS-arm64.zip"},
            {"platform": "linux-x64", "pattern": "TriliumNotes-*-Linux-x64.zip"},
        ],
    },
    {
        "id": "zettlr",
        "name": "Zettlr",
        "category": "Productivity",
        "repo": "Zettlr/Zettlr",
        "assets": [
            {"platform": "win-x64", "pattern": "Zettlr-*-x64.exe"},
            {"platform": "mac-arm64", "pattern": "Zettlr-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Zettlr-*-amd64.deb"},
        ],
    },
    {
        "id": "drawio",
        "name": "draw.io",
        "category": "Productivity",
        "repo": "jgraph/drawio-desktop",
        "assets": [
            {"platform": "win-x64", "pattern": "draw.io-*-windows-installer.exe"},
            {"platform": "mac-arm64", "pattern": "draw.io-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "draw.io-*-x86_64.rpm"},
        ],
    },
    {
        "id": "excalidraw",
        "name": "Excalidraw",
        "category": "Productivity",
        "repo": "excalidraw/excalidraw",
        "assets": [
            {"platform": "win-x64", "pattern": "Excalidraw-*-x64.exe"},
        ],
    },
    {
        "id": "beekeeper",
        "name": "Beekeeper Studio",
        "category": "Productivity",
        "repo": "beekeeper-studio/beekeeper-studio",
        "assets": [
            {"platform": "win-x64", "pattern": "beekeeper-studio-*-win.exe"},
            {"platform": "mac-arm64", "pattern": "beekeeper-studio-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "beekeeper-studio-*-amd64.deb"},
        ],
    },
    {
        "id": "sumatrapdf",
        "name": "Sumatra PDF",
        "category": "Productivity",
        "repo": "sumatrapdfreader/sumatrapdf",
        "assets": [
            {"platform": "win-x64", "pattern": "SumatraPDF-*-64-install.exe"},
            {"platform": "win-x64-portable", "pattern": "SumatraPDF-*-64.zip"},
        ],
    },
    {
        "id": "sioyek",
        "name": "Sioyek",
        "category": "Productivity",
        "repo": "ahrm/sioyek",
        "assets": [
            {"platform": "win-x64", "pattern": "sioyek-release-windows.zip"},
            {"platform": "mac-arm64", "pattern": "sioyek-apple-silicon.dmg"},
            {
                "platform": "linux-x64",
                "pattern": "sioyek-release-linux-portable.tar.gz",
            },
        ],
    },
    {
        "id": "pomatez",
        "name": "Pomatez",
        "category": "Productivity",
        "repo": "roldanjr/pomatez",
        "assets": [
            {"platform": "win-x64", "pattern": "Pomatez-*-x64.exe"},
            {"platform": "mac-arm64", "pattern": "Pomatez-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Pomatez-*-x86_64.AppImage"},
        ],
    },
    {
        "id": "mindforger",
        "name": "MindForger",
        "category": "Productivity",
        "repo": "dvorka/mindforger",
        "assets": [
            {"platform": "win-x64", "pattern": "mindforger-*-win64.exe"},
        ],
    },
    {
        "id": "notable",
        "name": "Notable",
        "category": "Productivity",
        "repo": "niclaslindstedt/notable",  # placeholder
        "assets": [
            {"platform": "win-x64", "pattern": "Notable-*-Setup.exe"},
        ],
    },
    {
        "id": "ghostwriter",
        "name": "ghostwriter",
        "category": "Productivity",
        "repo": "KDE/ghostwriter",
        "assets": [
            {"platform": "win-x64", "pattern": "ghostwriter-*-setup.exe"},
        ],
    },
    {
        "id": "marktext-new",
        "name": "Mark Text (New)",
        "category": "Productivity",
        "repo": "niclaslindstedt/marktext",  # placeholder
        "assets": [
            {"platform": "win-x64", "pattern": "marktext-*-x64.exe"},
        ],
    },
    {
        "id": "notion-enhanced",
        "name": "Notion Enhanced",
        "category": "Productivity",
        "repo": "niclaslindstedt/notion-enhanced",  # placeholder
        "assets": [
            {"platform": "win-x64", "pattern": "Notion-Enhanced-*-x64.exe"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Messaging (5)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "element",
        "name": "Element",
        "category": "Messaging",
        "repo": "element-hq/element-desktop",
        "assets": [
            {"platform": "win-x64", "pattern": "element-*-x64.exe"},
            {"platform": "mac-arm64", "pattern": "element-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "element-*-amd64.deb"},
        ],
    },
    {
        "id": "cinny",
        "name": "Cinny",
        "category": "Messaging",
        "repo": "cinnyapp/cinny-desktop",
        "assets": [
            {"platform": "win-x64", "pattern": "Cinny-*-x64.exe"},
            {"platform": "mac-arm64", "pattern": "Cinny-*-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Cinny-*-amd64.deb"},
        ],
    },
    {
        "id": "hexchat",
        "name": "HexChat",
        "category": "Messaging",
        "repo": "hexchat/hexchat",
        "assets": [
            {"platform": "win-x64", "pattern": "HexChat-*-x64.exe"},
        ],
    },
    {
        "id": "protonmail-bridge",
        "name": "Proton Mail Bridge",
        "category": "Messaging",
        "repo": "ProtonMail/proton-bridge",
        "assets": [
            {"platform": "win-x64", "pattern": "proton-bridge-*-x64.exe"},
            {"platform": "mac-arm64", "pattern": "proton-bridge-*-arm64.dmg"},
        ],
    },
    {
        "id": "fluffy-chat",
        "name": "FluffyChat",
        "category": "Messaging",
        "repo": "niclaslindstedt/fluffychat",  # placeholder
        "assets": [
            {"platform": "linux-x64", "pattern": "fluffychat-*-linux-x86_64.AppImage"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # AI Tools (10)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "localai",
        "name": "LocalAI",
        "category": "AI Tools",
        "repo": "mudler/LocalAI",
        "assets": [
            {"platform": "win-x64", "pattern": "local-ai-*-windows-amd64.exe"},
            {"platform": "mac-arm64", "pattern": "local-ai-*-darwin-arm64"},
            {"platform": "linux-x64", "pattern": "local-ai-*-linux-amd64"},
        ],
    },
    {
        "id": "comfyui",
        "name": "ComfyUI",
        "category": "AI Tools",
        "repo": "comfyanonymous/ComfyUI",
        "assets": [
            {"platform": "win-x64", "pattern": "ComfyUI_windows_portable_nvidia.7z"},
        ],
    },
    {
        "id": "invokeai",
        "name": "InvokeAI",
        "category": "AI Tools",
        "repo": "invoke-ai/InvokeAI",
        "assets": [
            {"platform": "win-x64", "pattern": "InvokeAI-*-windows.zip"},
            {"platform": "mac-arm64", "pattern": "InvokeAI-*-macos.zip"},
            {"platform": "linux-x64", "pattern": "InvokeAI-*-linux.tar.gz"},
        ],
    },
    {
        "id": "stable-diffusion-webui",
        "name": "Stable Diffusion WebUI",
        "category": "AI Tools",
        "repo": "AUTOMATIC1111/stable-diffusion-webui",
        "assets": [
            {"platform": "win-x64", "pattern": "stable-diffusion-webui-*-win64.zip"},
        ],
    },
    {
        "id": "text-generation-webui",
        "name": "text-generation-webui",
        "category": "AI Tools",
        "repo": "oobabooga/text-generation-webui",
        "assets": [
            {"platform": "win-x64", "pattern": "text-generation-webui-*-win64.zip"},
        ],
    },
    {
        "id": "buzz",
        "name": "Buzz",
        "category": "AI Tools",
        "repo": "chidiwilliams/buzz",
        "assets": [
            {"platform": "win-x64", "pattern": "Buzz-*-windows.exe"},
            {"platform": "mac-arm64", "pattern": "Buzz-*-mac-arm64.dmg"},
            {"platform": "linux-x64", "pattern": "Buzz-*-linux-x86_64.AppImage"},
        ],
    },
    {
        "id": "whisper",
        "name": "Whisper",
        "category": "AI Tools",
        "repo": "openai/whisper",
        "assets": [
            {"platform": "linux-x64", "pattern": "whisper-*-linux-amd64"},
        ],
    },
    {
        "id": "llama-cpp",
        "name": "llama.cpp",
        "category": "AI Tools",
        "repo": "ggml-org/llama.cpp",
        "assets": [
            {"platform": "win-x64", "pattern": "llama-*-bin-win-x64.zip"},
            {"platform": "mac-arm64", "pattern": "llama-*-bin-macos-arm64.zip"},
            {"platform": "linux-x64", "pattern": "llama-*-bin-linux-x64.zip"},
        ],
    },
    {
        "id": "open-webui",
        "name": "Open WebUI",
        "category": "AI Tools",
        "repo": "open-webui/open-webui",
        "assets": [
            {"platform": "win-x64", "pattern": "open-webui-*-windows-amd64.exe"},
            {"platform": "mac-arm64", "pattern": "open-webui-*-darwin-arm64"},
            {"platform": "linux-x64", "pattern": "open-webui-*-linux-amd64"},
        ],
    },
    {
        "id": "koboldcpp",
        "name": "KoboldCpp",
        "category": "AI Tools",
        "repo": "LostRuins/koboldcpp",
        "assets": [
            {"platform": "win-x64", "pattern": "koboldcpp_*_win_x64.exe"},
            {"platform": "mac-arm64", "pattern": "koboldcpp_*_macos_arm64"},
            {"platform": "linux-x64", "pattern": "koboldcpp_*_linux_x64"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Security & Privacy (5)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "age",
        "name": "age",
        "category": "Security & Privacy",
        "repo": "FiloSottile/age",
        "assets": [
            {"platform": "win-x64", "pattern": "age-*-windows-amd64.zip"},
            {"platform": "mac-arm64", "pattern": "age-*-darwin-arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "age-*-linux-amd64.tar.gz"},
        ],
    },
    {
        "id": "sops",
        "name": "sops",
        "category": "Security & Privacy",
        "repo": "getsops/sops",
        "assets": [
            {"platform": "win-x64", "pattern": "sops-*-windows.amd64.exe"},
            {"platform": "mac-arm64", "pattern": "sops-*-darwin.arm64"},
            {"platform": "linux-x64", "pattern": "sops-*-linux.amd64"},
        ],
    },
    {
        "id": "yubikey-manager",
        "name": "YubiKey Manager",
        "category": "Security & Privacy",
        "repo": "Yubico/yubikey-manager",
        "assets": [
            {"platform": "win-x64", "pattern": "yubikey-manager-*.exe"},
            {"platform": "mac-arm64", "pattern": "yubikey-manager-*.dmg"},
        ],
    },
    {
        "id": "clamav",
        "name": "ClamAV",
        "category": "Security & Privacy",
        "repo": "Cisco-Talos/clamav",
        "assets": [
            {"platform": "win-x64", "pattern": "clamav-*-x64.msi"},
        ],
    },
    {
        "id": "gitleaks",
        "name": "gitleaks",
        "category": "Security & Privacy",
        "repo": "gitleaks/gitleaks",
        "assets": [
            {"platform": "win-x64", "pattern": "gitleaks_*_windows_x64.zip"},
            {"platform": "mac-arm64", "pattern": "gitleaks_*_darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "gitleaks_*_linux_x64.tar.gz"},
        ],
    },
    # ═══════════════════════════════════════════════════════════════
    # Cloud & DevOps (10)
    # ═══════════════════════════════════════════════════════════════
    {
        "id": "docker-compose",
        "name": "Docker Compose",
        "category": "Cloud & DevOps",
        "repo": "docker/compose",
        "assets": [
            {"platform": "win-x64", "pattern": "docker-compose-windows-x86_64.exe"},
            {"platform": "mac-arm64", "pattern": "docker-compose-darwin-aarch64"},
            {"platform": "linux-x64", "pattern": "docker-compose-linux-x86_64"},
        ],
    },
    {
        "id": "k9s",
        "name": "k9s",
        "category": "Cloud & DevOps",
        "repo": "derailed/k9s",
        "assets": [
            {"platform": "win-x64", "pattern": "k9s_Windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "k9s_Darwin_arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "k9s_Linux_amd64.tar.gz"},
        ],
    },
    {
        "id": "helm",
        "name": "Helm",
        "category": "Cloud & DevOps",
        "repo": "helm/helm",
        "assets": [
            {"platform": "win-x64", "pattern": "helm-*-windows-amd64.zip"},
            {"platform": "mac-arm64", "pattern": "helm-*-darwin-arm64.tar.gz"},
            {"platform": "linux-x64", "pattern": "helm-*-linux-amd64.tar.gz"},
        ],
    },
    {
        "id": "terraform",
        "name": "Terraform",
        "category": "Cloud & DevOps",
        "repo": "hashicorp/terraform",
        "assets": [
            {"platform": "win-x64", "pattern": "terraform_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "terraform_*_darwin_arm64.zip"},
            {"platform": "linux-x64", "pattern": "terraform_*_linux_amd64.zip"},
        ],
    },
    {
        "id": "vault",
        "name": "Vault",
        "category": "Cloud & DevOps",
        "repo": "hashicorp/vault",
        "assets": [
            {"platform": "win-x64", "pattern": "vault_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "vault_*_darwin_arm64.zip"},
            {"platform": "linux-x64", "pattern": "vault_*_linux_amd64.zip"},
        ],
    },
    {
        "id": "consul",
        "name": "Consul",
        "category": "Cloud & DevOps",
        "repo": "hashicorp/consul",
        "assets": [
            {"platform": "win-x64", "pattern": "consul_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "consul_*_darwin_arm64.zip"},
            {"platform": "linux-x64", "pattern": "consul_*_linux_amd64.zip"},
        ],
    },
    {
        "id": "nomad",
        "name": "Nomad",
        "category": "Cloud & DevOps",
        "repo": "hashicorp/nomad",
        "assets": [
            {"platform": "win-x64", "pattern": "nomad_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "nomad_*_darwin_arm64.zip"},
            {"platform": "linux-x64", "pattern": "nomad_*_linux_amd64.zip"},
        ],
    },
    {
        "id": "boundary",
        "name": "Boundary",
        "category": "Cloud & DevOps",
        "repo": "hashicorp/boundary",
        "assets": [
            {"platform": "win-x64", "pattern": "boundary_*_windows_amd64.zip"},
            {"platform": "mac-arm64", "pattern": "boundary_*_darwin_arm64.zip"},
            {"platform": "linux-x64", "pattern": "boundary_*_linux_amd64.zip"},
        ],
    },
    {
        "id": "k3s",
        "name": "k3s",
        "category": "Cloud & DevOps",
        "repo": "k3s-io/k3s",
        "assets": [
            {"platform": "linux-x64", "pattern": "k3s"},
        ],
    },
    {
        "id": "k6",
        "name": "k6",
        "category": "Cloud & DevOps",
        "repo": "grafana/k6",
        "assets": [
            {"platform": "win-x64", "pattern": "k6-*-windows-amd64.zip"},
            {"platform": "mac-arm64", "pattern": "k6-*-macos-arm64.zip"},
            {"platform": "linux-x64", "pattern": "k6-*-linux-amd64.tar.gz"},
        ],
    },
]


def main():
    packages_path = Path(__file__).parent.parent / "packages.yaml"

    with open(packages_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    existing_ids = {p["id"] for p in config["packages"]}
    added = 0
    skipped = 0

    for app in NEW_APPS:
        app_id = app["id"]
        if app_id in existing_ids:
            print(f"  跳过已存在: {app_id}")
            skipped += 1
            continue

        # 跳过 placeholder 仓库的条目
        if "niclaslindstedt" in app.get("repo", ""):
            print(f"  跳过 placeholder: {app_id} ({app['repo']})")
            skipped += 1
            continue

        entry = {
            "id": app_id,
            "name": app["name"],
            "category": app["category"],
            "editions": ["intl"],
            "homepage": f"https://github.com/{app['repo']}",
            "fetcher": "github_release",
            "args": {
                "repo": app["repo"],
                "assets": app["assets"],
            },
        }

        if "tag_pattern" in app:
            entry["args"]["tag_pattern"] = app["tag_pattern"]

        config["packages"].append(entry)
        existing_ids.add(app_id)
        added += 1

    with open(packages_path, "w", encoding="utf-8") as f:
        yaml.dump(
            config, f, allow_unicode=True, sort_keys=False, default_flow_style=False
        )

    print(f"\n完成! 新增 {added} 个软件, 跳过 {skipped} 个")
    print(f"总计: {len(config['packages'])} 个软件")


if __name__ == "__main__":
    main()

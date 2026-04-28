import yaml

new_apps = [
    # 开发工具
    {"id": "git", "name": "Git for Windows", "repo": "git-for-windows/git", "pattern": "Git-*-64-bit.exe", "category": "开发工具"},
    {"id": "nodejs", "name": "Node.js", "repo": "nodejs/node", "pattern": "node-v*-win-x64.zip", "category": "开发工具"},
    {"id": "python", "name": "Python", "repo": "python/cpython", "pattern": "python-*.exe", "category": "开发工具", "tag_pattern": "^v3"},
    {"id": "go", "name": "Go", "repo": "golang/go", "pattern": "go*.windows-amd64.msi", "category": "开发工具"},
    {"id": "rust", "name": "Rust (rustup)", "repo": "rust-lang/rustup", "pattern": "rustup-init.exe", "category": "开发工具"},
    {"id": "postman", "name": "Postman", "repo": "postmanlabs/postman-app-support", "pattern": "Postman-win64-*.exe", "category": "开发工具"},
    {"id": "insomnia", "name": "Insomnia", "repo": "Kong/insomnia", "pattern": "Insomnia.Core-*.exe", "category": "开发工具"},
    {"id": "dbeaver", "name": "DBeaver", "repo": "dbeaver/dbeaver", "pattern": "dbeaver-ce-*-x86_64-setup.exe", "category": "开发工具"},
    {"id": "heidisql", "name": "HeidiSQL", "repo": "HeidiSQL/HeidiSQL", "pattern": "HeidiSQL_*_Setup.exe", "category": "开发工具"},
    {"id": "notepadplusplus", "name": "Notepad++", "repo": "notepad-plus-plus/notepad-plus-plus", "pattern": "npp.*.Installer.x64.exe", "category": "开发工具"},
    {"id": "alacritty", "name": "Alacritty", "repo": "alacritty/alacritty", "pattern": "Alacritty-v*-installer.exe", "category": "开发工具"},
    {"id": "wezterm", "name": "WezTerm", "repo": "wez/wezterm", "pattern": "WezTerm-*-setup.exe", "category": "开发工具"},
    {"id": "windows-terminal", "name": "Windows Terminal", "repo": "microsoft/terminal", "pattern": "Microsoft.WindowsTerminal_*.msixbundle", "category": "开发工具"},
    {"id": "lazygit", "name": "Lazygit", "repo": "jesseduffield/lazygit", "pattern": "lazygit_*_Windows_x86_64.zip", "category": "开发工具"},

    # 网络工具
    {"id": "wireshark", "name": "Wireshark", "repo": "wireshark/wireshark", "pattern": "Wireshark-win64-*.exe", "category": "网络工具"},
    {"id": "curl", "name": "curl", "repo": "curl/curl", "pattern": "curl-*-win64-mingw.zip", "category": "网络工具"},
    {"id": "nmap", "name": "Nmap", "repo": "nmap/nmap", "pattern": "nmap-*-setup.exe", "category": "网络工具"},
    {"id": "putty", "name": "PuTTY", "repo": "github/putty", "pattern": "putty-64bit-*-installer.msi", "category": "网络工具"},
    {"id": "winscp", "name": "WinSCP", "repo": "winscp/winscp", "pattern": "WinSCP-*-Setup.exe", "category": "网络工具"},
    {"id": "filezilla", "name": "FileZilla Client", "repo": "filezilla/filezilla", "pattern": "FileZilla_*_win64-setup.exe", "category": "网络工具"},
    {"id": "tailscale", "name": "Tailscale", "repo": "tailscale/tailscale", "pattern": "tailscale-setup-*.exe", "category": "网络代理"},
    {"id": "clash-verge-rev", "name": "Clash Verge Rev", "repo": "clash-verge-rev/clash-verge-rev", "pattern": "Clash.Verge_*_x64_en-US.msi", "category": "网络代理"},
    {"id": "hiddify", "name": "Hiddify Next", "repo": "hiddify/hiddify-next", "pattern": "Hiddify-Windows-Setup-x64.exe", "category": "网络代理"},
    {"id": "sing-box", "name": "sing-box", "repo": "SagerNet/sing-box", "pattern": "sing-box-*-windows-amd64.zip", "category": "网络代理"},
    {"id": "xray-core", "name": "Xray-core", "repo": "XTLS/Xray-core", "pattern": "Xray-windows-64.zip", "category": "网络代理"},
    {"id": "v2ray-core", "name": "v2ray-core", "repo": "v2fly/v2ray-core", "pattern": "v2ray-windows-64.zip", "category": "网络代理"},

    # 系统工具
    {"id": "rufus", "name": "Rufus", "repo": "pbatard/rufus", "pattern": "rufus-*.exe", "category": "系统工具"},
    {"id": "ventoy", "name": "Ventoy", "repo": "ventoy/Ventoy", "pattern": "ventoy-*-windows.zip", "category": "系统工具"},
    {"id": "bleachbit", "name": "BleachBit", "repo": "bleachbit/bleachbit", "pattern": "BleachBit-*-setup.exe", "category": "系统工具"},
    {"id": "hwinfo", "name": "HWiNFO", "repo": "hwinfo/hwinfo", "pattern": "hwi_*.exe", "category": "系统工具"},
    {"id": "cpu-z", "name": "CPU-Z", "repo": "cpuid/cpu-z", "pattern": "cpu-z_*_setup.exe", "category": "系统工具"},
    {"id": "gpu-z", "name": "GPU-Z", "repo": "TechPowerUp/GPU-Z", "pattern": "GPU-Z_*.exe", "category": "系统工具"},
    {"id": "crystaldiskinfo", "name": "CrystalDiskInfo", "repo": "hiyohiyo/CrystalDiskInfo", "pattern": "CrystalDiskInfo*.exe", "category": "系统工具"},
    {"id": "crystaldiskmark", "name": "CrystalDiskMark", "repo": "hiyohiyo/CrystalDiskMark", "pattern": "CrystalDiskMark*.exe", "category": "系统工具"},
    {"id": "7zip", "name": "7-Zip", "repo": "ipavlov/7-zip", "pattern": "7z*x64.exe", "category": "系统工具"},
    {"id": "peazip", "name": "PeaZip", "repo": "peazip/PeaZip", "pattern": "peazip-*_WIN64.exe", "category": "系统工具"},
    {"id": "trafficmonitor", "name": "TrafficMonitor", "repo": "zhongyang219/TrafficMonitor", "pattern": "TrafficMonitor_V*_x64.zip", "category": "系统工具"},
    {"id": "snipaste", "name": "Snipaste", "repo": "Snipaste/feedback", "pattern": "Snipaste-*-x64.zip", "category": "系统工具"},
    {"id": "flameshot", "name": "Flameshot", "repo": "flameshot-org/flameshot", "pattern": "Flameshot-*-win64.exe", "category": "系统工具"},
    {"id": "sharex", "name": "ShareX", "repo": "ShareX/ShareX", "pattern": "ShareX-*-setup.exe", "category": "系统工具"},

    # 媒体与生产力
    {"id": "obs-studio", "name": "OBS Studio", "repo": "obsproject/obs-studio", "pattern": "OBS-Studio-*-Full-Installer-x64.exe", "category": "多媒体软件"},
    {"id": "vlc", "name": "VLC media player", "repo": "videolan/vlc", "pattern": "vlc-*-win64.exe", "category": "多媒体软件"},
    {"id": "k-lite", "name": "K-Lite Codec Pack", "repo": "codecguide/klite", "pattern": "K-Lite_Codec_Pack_*_Mega.exe", "category": "多媒体软件"},
    {"id": "audacity", "name": "Audacity", "repo": "audacity/audacity", "pattern": "audacity-win-*-64bit.exe", "category": "多媒体软件"},
    {"id": "handbrake", "name": "HandBrake", "repo": "HandBrake/HandBrake", "pattern": "HandBrake-*-x86_64-Win_GUI.exe", "category": "多媒体软件"},
    {"id": "ffmpeg", "name": "FFmpeg", "repo": "BtbN/FFmpeg-Builds", "pattern": "ffmpeg-master-latest-win64-gpl.zip", "category": "多媒体软件"},
    {"id": "gimp", "name": "GIMP", "repo": "GNOME/gimp", "pattern": "gimp-*-setup.exe", "category": "生产力工具"},
    {"id": "krita", "name": "Krita", "repo": "KDE/krita", "pattern": "krita-*-x64-setup.exe", "category": "生产力工具"},
    {"id": "inkscape", "name": "Inkscape", "repo": "inkscape/inkscape", "pattern": "inkscape-*-x64.exe", "category": "生产力工具"},
    {"id": "blender", "name": "Blender", "repo": "blender/blender", "pattern": "blender-*-windows-x64.msi", "category": "生产力工具"},
    {"id": "libreoffice", "name": "LibreOffice", "repo": "LibreOffice/core", "pattern": "LibreOffice_*_Win_x86-64.msi", "category": "生产力工具"},
    {"id": "sumatrapdf", "name": "Sumatra PDF", "repo": "sumatrapdfreader/sumatrapdf", "pattern": "SumatraPDF-*-64-install.exe", "category": "生产力工具"},
    {"id": "calibre", "name": "calibre", "repo": "kovidgoyal/calibre", "pattern": "calibre-64bit-*.msi", "category": "生产力工具"},
    {"id": "kodi", "name": "Kodi", "repo": "xbmc/xbmc", "pattern": "kodi-*-x64.exe", "category": "多媒体软件"},

    # 通用工具 & 社交
    {"id": "keepassxc", "name": "KeePassXC", "repo": "keepassxreboot/keepassxc", "pattern": "KeePassXC-*-Win64.msi", "category": "通用工具"},
    {"id": "rustdesk", "name": "RustDesk", "repo": "rustdesk/rustdesk", "pattern": "rustdesk-*-x86_64.exe", "category": "通用工具"},
    {"id": "telegram", "name": "Telegram Desktop", "repo": "telegramdesktop/tdesktop", "pattern": "tsetup.*.exe", "category": "即时通讯"},
    {"id": "obsidian", "name": "Obsidian", "repo": "obsidianmd/obsidian-releases", "pattern": "Obsidian.*.exe", "category": "生产力工具"},
    {"id": "logseq", "name": "Logseq", "repo": "logseq/logseq", "pattern": "Logseq-win-x64-*.exe", "category": "生产力工具"},
    {"id": "joplin", "name": "Joplin", "repo": "laurent22/joplin", "pattern": "Joplin-Setup-*.exe", "category": "生产力工具"},

    # 浏览器
    {"id": "brave", "name": "Brave Browser", "repo": "brave/brave-browser", "pattern": "BraveBrowserSetup.exe", "category": "浏览器"},
    {"id": "thorium", "name": "Thorium Browser", "repo": "Alex313031/Thorium-Win", "pattern": "thorium_*.exe", "category": "浏览器"},
    {"id": "librewolf", "name": "LibreWolf", "repo": "LibreWolf-Community/librewolf-win", "pattern": "librewolf-*-windows-x86_64-setup.exe", "category": "浏览器"},

    # 游戏与娱乐
    {"id": "moonlight", "name": "Moonlight Game Streaming", "repo": "moonlight-stream/moonlight-qt", "pattern": "MoonlightPC-*-x64.exe", "category": "游戏平台"},
    {"id": "sunshine", "name": "Sunshine", "repo": "LizardByte/Sunshine", "pattern": "sunshine-windows-amd64.exe", "category": "游戏平台"},
    {"id": "heroic", "name": "Heroic Games Launcher", "repo": "Heroic-Games-Launcher/HeroicGamesLauncher", "pattern": "Heroic-*-Setup.exe", "category": "游戏平台"},
    {"id": "retroarch", "name": "RetroArch", "repo": "libretro/RetroArch", "pattern": "RetroArch-*-x64-setup.exe", "category": "游戏平台"},

    # AI
    {"id": "ollama", "name": "Ollama", "repo": "ollama/ollama", "pattern": "OllamaSetup.exe", "category": "AI 工具"},
    {"id": "jan", "name": "Jan", "repo": "janhq/jan", "pattern": "jan-win-x64-*.exe", "category": "AI 工具"},
]

valid_apps = []
for app in new_apps:
    cfg = {
        "id": app["id"],
        "name": app["name"],
        "category": app.get("category", "通用工具"),
        "editions": ["intl"],
        "homepage": f"https://github.com/{app['repo']}",
        "fetcher": "github_release",
        "args": {
            "repo": app["repo"],
            "assets": [
                {"platform": "win-x64", "pattern": app["pattern"]}
            ]
        }
    }
    if "tag_pattern" in app:
        cfg["args"]["tag_pattern"] = app["tag_pattern"]
    valid_apps.append(cfg)

with open("packages.yaml", "r") as f:
    config = yaml.safe_load(f)

existing_ids = {p["id"] for p in config["packages"]}
added = 0
for app in valid_apps:
    if app["id"] not in existing_ids:
        config["packages"].append(app)
        added += 1

with open("packages.yaml", "w") as f:
    yaml.dump(config, f, allow_unicode=True, sort_keys=False)

print(f"Added {added} new apps to packages.yaml")

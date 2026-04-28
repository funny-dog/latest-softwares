import yaml

more_apps = [
    # Network & Security
    ("bitwarden", "Bitwarden", "bitwarden/clients", "Bitwarden-Installer-*.exe", "Utilities"),
    ("tailscale", "Tailscale", "tailscale/tailscale", "tailscale-setup-*.exe", "Network & Proxy"),
    ("wireguard", "WireGuard", "WireGuard/wireguard-windows", "wireguard-amd64-*.msi", "Network & Proxy"),
    ("v2ray-core", "v2ray-core", "v2fly/v2ray-core", "v2ray-windows-64.zip", "Network & Proxy"),
    ("xray-core", "Xray-core", "XTLS/Xray-core", "Xray-windows-64.zip", "Network & Proxy"),
    ("clash-for-windows", "Clash for Windows", "Fndroid/clash_for_windows_pkg", "Clash.for.Windows.Setup.*.exe", "Network & Proxy"),
    
    # Utilities
    ("rufus", "Rufus", "pbatard/rufus", "rufus-*.exe", "System Utilities"),
    ("ventoy", "Ventoy", "ventoy/Ventoy", "ventoy-*-windows.zip", "System Utilities"),
    ("bleachbit", "BleachBit", "bleachbit/bleachbit", "BleachBit-*-setup.exe", "System Utilities"),
    ("autoruns", "Autoruns", "microsoft/SysinternalsSuite", "Autoruns.zip", "System Utilities"),
    ("process-explorer", "Process Explorer", "microsoft/SysinternalsSuite", "ProcessExplorer.zip", "System Utilities"),
    ("process-monitor", "Process Monitor", "microsoft/SysinternalsSuite", "ProcessMonitor.zip", "System Utilities"),
    ("7zip", "7-Zip", "ipavlov/7-zip", "7z*x64.exe", "System Utilities"),
    ("peazip", "PeaZip", "peazip/PeaZip", "peazip-*_WIN64.exe", "System Utilities"),
    ("powertoys", "PowerToys", "microsoft/PowerToys", "PowerToysUserSetup-*-x64.exe", "System Utilities"),
    ("sharex", "ShareX", "ShareX/ShareX", "ShareX-*-setup.exe", "System Utilities"),
    ("nilesoft-shell", "Nilesoft Shell", "moudey/Shell", "shell_setup.exe", "System Utilities"),
    ("windirstat", "WinDirStat", "windirstat/windirstat", "windirstat*_setup.exe", "System Utilities"),

    # Media Players & Editors
    ("vlc", "VLC", "videolan/vlc", "vlc-*-win64.exe", "Media Players"),
    ("mpv", "mpv", "mpv-player/mpv", "mpv-x86_64-*-git-*.7z", "Media Players"),
    ("k-lite", "K-Lite Codec Pack", "codecguide/klite", "K-Lite_Codec_Pack_*_Mega.exe", "Media Players"),
    ("audacity", "Audacity", "audacity/audacity", "audacity-win-*-64bit.exe", "Media Players"),
    ("handbrake", "HandBrake", "HandBrake/HandBrake", "HandBrake-*-x86_64-Win_GUI.exe", "Media Players"),
    ("ffmpeg", "FFmpeg", "BtbN/FFmpeg-Builds", "ffmpeg-master-latest-win64-gpl.zip", "Media Players"),
    ("gimp", "GIMP", "GNOME/gimp", "gimp-*-setup.exe", "Productivity"),
    ("inkscape", "Inkscape", "inkscape/inkscape", "inkscape-*-x64.exe", "Productivity"),
    ("blender", "Blender", "blender/blender", "blender-*-windows-x64.msi", "Productivity"),
    ("libreoffice", "LibreOffice", "LibreOffice/core", "LibreOffice_*_Win_x86-64.msi", "Productivity"),
    ("sumatrapdf", "Sumatra PDF", "sumatrapdfreader/sumatrapdf", "SumatraPDF-*-64-install.exe", "Productivity"),
    ("calibre", "calibre", "kovidgoyal/calibre", "calibre-64bit-*.msi", "Productivity"),
    ("kodi", "Kodi", "xbmc/xbmc", "kodi-*-x64.exe", "Media Players"),
    
    # Browsers
    ("firefox", "Firefox", "mozilla/gecko-dev", "Firefox Setup *.exe", "Browsers"),
    ("vivaldi", "Vivaldi", "vivaldi/vivaldi", "Vivaldi.*.exe", "Browsers"),
    ("arc", "Arc", "thebrowsercompany/arc", "ArcInstaller.exe", "Browsers"), # might not have release
    
    # Gaming
    ("moonlight", "Moonlight", "moonlight-stream/moonlight-qt", "MoonlightPC-*-x64.exe", "Gaming"),
    ("sunshine", "Sunshine", "LizardByte/Sunshine", "sunshine-windows-amd64.exe", "Gaming"),
    ("heroic", "Heroic", "Heroic-Games-Launcher/HeroicGamesLauncher", "Heroic-*-Setup.exe", "Gaming"),
    ("retroarch", "RetroArch", "libretro/RetroArch", "RetroArch-*-x64-setup.exe", "Gaming"),
    ("rpcs3", "RPCS3", "RPCS3/rpcs3", "rpcs3-*-win32.zip", "Gaming"),
    ("cemu", "Cemu", "cemu-project/Cemu", "cemu_*.zip", "Gaming"),

    # Development
    ("git", "Git", "git-for-windows/git", "Git-*-64-bit.exe", "Developer Tools"),
    ("docker", "Docker Desktop", "docker/docker-ce", "Docker Desktop Installer.exe", "Developer Tools"),
    ("postman", "Postman", "postmanlabs/postman-app-support", "Postman-win64-*.exe", "Developer Tools"),
    ("dbeaver", "DBeaver", "dbeaver/dbeaver", "dbeaver-ce-*-x86_64-setup.exe", "Developer Tools"),
    ("alacritty", "Alacritty", "alacritty/alacritty", "Alacritty-v*-installer.exe", "Developer Tools"),
    ("windows-terminal", "Windows Terminal", "microsoft/terminal", "Microsoft.WindowsTerminal_*.msixbundle", "Developer Tools"),
    ("curl", "curl", "curl/curl", "curl-*-win64-mingw.zip", "Developer Tools"),
    ("nmap", "Nmap", "nmap/nmap", "nmap-*-setup.exe", "Developer Tools"),
    ("winscp", "WinSCP", "winscp/winscp", "WinSCP-*-Setup.exe", "Developer Tools"),
    ("filezilla", "FileZilla", "filezilla/filezilla", "FileZilla_*_win64-setup.exe", "Developer Tools"),
]

with open('packages.yaml', 'r') as f:
    config = yaml.safe_load(f)

existing_ids = {p['id'] for p in config.get('packages', [])}

for app in more_apps:
    id_name, name, repo, pattern, cat = app
    if id_name not in existing_ids:
        config['packages'].append({
            'id': id_name,
            'name': name,
            'category': cat,
            'editions': ['intl'],
            'homepage': f"https://github.com/{repo}",
            'fetcher': 'github_release',
            'args': {
                'repo': repo,
                'assets': [
                    {'platform': 'win-x64', 'pattern': pattern}
                ]
            }
        })

with open('packages.yaml', 'w') as f:
    yaml.dump(config, f, allow_unicode=True, sort_keys=False)

print(f"Total apps in packages.yaml: {len(config['packages'])}")

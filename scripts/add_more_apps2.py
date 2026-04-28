import yaml

more_apps = [
    # Utilities & Tools
    ("powertoys", "PowerToys", "microsoft/PowerToys", "PowerToysUserSetup-*-x64.exe", "System Utilities"),
    ("terminal", "Windows Terminal", "microsoft/terminal", "Microsoft.WindowsTerminal_*.msixbundle", "Developer Tools"),
    ("rufus", "Rufus", "pbatard/rufus", "rufus-*.exe", "System Utilities"),
    ("ventoy", "Ventoy", "ventoy/Ventoy", "ventoy-*-windows.zip", "System Utilities"),
    ("translucenttb", "TranslucentTB", "TranslucentTB/TranslucentTB", "TranslucentTB-appinstaller.zip", "System Utilities"),
    ("lively", "Lively Wallpaper", "rocksdanister/lively", "lively_setup_x86_*.exe", "System Utilities"),
    ("everythingtoolbar", "EverythingToolbar", "srwi/EverythingToolbar", "EverythingToolbar-*.msi", "System Utilities"),
    ("ear-trumpet", "EarTrumpet", "File-New-Project/EarTrumpet", "EarTrumpet.appinstaller", "System Utilities"),
    ("modern-flyouts", "Modern Flyouts", "ModernFlyouts-Community/ModernFlyouts", "ModernFlyouts_*.msixbundle", "System Utilities"),
    ("explorer-patcher", "ExplorerPatcher", "valinet/ExplorerPatcher", "ep_setup.exe", "System Utilities"),

    # Productivity
    ("obsidian", "Obsidian", "obsidianmd/obsidian-releases", "Obsidian.*.exe", "Productivity"),
    ("logseq", "Logseq", "logseq/logseq", "Logseq-win-x64-*.exe", "Productivity"),
    ("joplin", "Joplin", "laurent22/joplin", "Joplin-Setup-*.exe", "Productivity"),
    ("typora", "Typora", "typora/typora-issues", "typora-setup-x64.exe", "Productivity"),
    ("marktext", "MarkText", "marktext/marktext", "marktext-setup.exe", "Productivity"),
    ("appflowy", "AppFlowy", "AppFlowy-IO/AppFlowy", "AppFlowy-windows-x86_64.exe", "Productivity"),
    ("affine", "AFFiNE", "toeverything/AFFiNE", "affine-*-windows-x64.exe", "Productivity"),

    # Chat & Comms
    ("telegram", "Telegram", "telegramdesktop/tdesktop", "tsetup.*.exe", "Messaging"),
    ("discord", "Discord", "discord/discord", "DiscordSetup.exe", "Messaging"),
    ("element", "Element", "vector-im/element-desktop", "Element-Setup-*.exe", "Messaging"),
    ("signal", "Signal", "signalapp/Signal-Desktop", "signal-desktop-windows-*.exe", "Messaging"),
    ("mattermost", "Mattermost", "mattermost/desktop", "mattermost-desktop-*-win-x64.exe", "Messaging"),
    ("teamspeak", "TeamSpeak", "TeamSpeak-Systems/TeamSpeak-Client", "TeamSpeak3-Client-win64-*.exe", "Messaging"), # might not be there
    
    # Browsers
    ("brave", "Brave", "brave/brave-browser", "BraveBrowserSetup.exe", "Browsers"),
    ("thorium", "Thorium", "Alex313031/Thorium-Win", "thorium_*.exe", "Browsers"),
    ("zen", "Zen Browser", "zen-browser/desktop", "zen.installer.exe", "Browsers"),
    ("floorp", "Floorp", "Floorp-Projects/Floorp", "floorp-*-win64-setup.exe", "Browsers"),
    ("librewolf", "LibreWolf", "LibreWolf-Community/librewolf-win", "librewolf-*-windows-x86_64-setup.exe", "Browsers"),
    ("chromium", "Chromium", "Hibbiki/chromium-win64", "mini_installer.sync.exe", "Browsers"),
    
    # Downloading
    ("motrix", "Motrix", "agalwood/Motrix", "Motrix-*-x64.exe", "Utilities"),
    ("qbittorrent", "qBittorrent", "qbittorrent/qBittorrent", "qbittorrent_*_x64_setup.exe", "Utilities"),
    ("aria2", "Aria2", "aria2/aria2", "aria2-*-win-64bit-build1.zip", "Utilities"),
    ("yt-dlp", "yt-dlp", "yt-dlp/yt-dlp", "yt-dlp.exe", "Utilities"),
    ("stremio", "Stremio", "Stremio/stremio-shell", "Stremio+*.exe", "Media Players"),
    ("jdownloader2", "JDownloader 2", "jdownloader/jdownloader", "JDownloader2Setup.exe", "Utilities"), # Might not be on github

    # Media & Graphics
    ("obs", "OBS Studio", "obsproject/obs-studio", "OBS-Studio-*-Full-Installer-x64.exe", "Media Players"),
    ("kdenlive", "Kdenlive", "KDE/kdenlive", "kdenlive-*-x86_64.exe", "Productivity"),
    ("shotcut", "Shotcut", "mltframework/shotcut", "shotcut-win64-*.exe", "Productivity"),
    ("krita", "Krita", "KDE/krita", "krita-*-x64-setup.exe", "Productivity"),
    ("inkscape", "Inkscape", "inkscape/inkscape", "inkscape-*-x64.exe", "Productivity"),
    ("audacity", "Audacity", "audacity/audacity", "audacity-win-*-64bit.exe", "Media Players"),
    ("handbrake", "HandBrake", "HandBrake/HandBrake", "HandBrake-*-x86_64-Win_GUI.exe", "Media Players"),
    ("ffmpeg", "FFmpeg", "BtbN/FFmpeg-Builds", "ffmpeg-master-latest-win64-gpl.zip", "Media Players"),
    ("lossless-cut", "LosslessCut", "mifi/lossless-cut", "LosslessCut-win-x64.exe", "Media Players"),

    # Emulators & Gaming
    ("yuzu", "Yuzu", "yuzu-emu/yuzu-mainline", "yuzu-windows-msvc-*.zip", "Gaming"),
    ("ryujinx", "Ryujinx", "Ryujinx/release-channel-master", "test-ava-ryujinx-*-win_x64.zip", "Gaming"),
    ("ppsspp", "PPSSPP", "hrydgard/ppsspp", "PPSSPPWindows.zip", "Gaming"),
    ("duckstation", "DuckStation", "stenzek/duckstation", "duckstation-windows-x64-release.zip", "Gaming"),
    ("pcsx2", "PCSX2", "PCSX2/pcsx2", "pcsx2-v*-windows-x64-Qt.7z", "Gaming"),
    ("playnite", "Playnite", "JosefNemec/Playnite", "Playnite*exe", "Gaming"),

    # AI Tools
    ("ollama", "Ollama", "ollama/ollama", "OllamaSetup.exe", "AI Tools"),
    ("jan", "Jan", "janhq/jan", "jan-win-x64-*.exe", "AI Tools"),
    ("chatbox", "Chatbox", "Bin-Huang/chatbox", "Chatbox-*-Setup.exe", "AI Tools"),
    ("nextchat", "NextChat", "ChatGPTNextWeb/ChatGPT-Next-Web", "NextChat_*-x64_en-US.msi", "AI Tools"),
    ("anythingllm", "AnythingLLM", "Mintplex-Labs/anything-llm", "AnythingLLMDesktop.exe", "AI Tools"),
    ("gpt4all", "GPT4All", "nomic-ai/gpt4all", "gpt4all-installer-win64.exe", "AI Tools"),
    ("lmstudio", "LM Studio", "lmstudio-ai/lmstudio-bug-tracker", "LM-Studio-*.exe", "AI Tools"),
    ("open-webui", "Open WebUI", "open-webui/open-webui", "open-webui-*-win64.exe", "AI Tools"),
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

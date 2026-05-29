"""把 GitHub topics + 描述关键词映射到现有 category 取值。

现有 category（来自 packages/*.yaml 实际统计）：
Developer Tools / System Utilities / Utilities / Productivity / Media Players /
Network & Proxy / Gaming / AI Tools / Messaging / Browsers /
Security & Privacy / Cloud & DevOps / Operating Systems / Download Tools
"""

from __future__ import annotations

# 顺序即优先级：靠前的先命中
_KEYWORD_CATEGORY: list[tuple[tuple[str, ...], str]] = [
    (("browser", "chromium", "webkit"), "Browsers"),
    (
        ("llm", "ai ", " ai", "gpt", "inference", "stable-diffusion", "chatbot"),
        "AI Tools",
    ),
    (
        ("proxy", "vpn", "v2ray", "clash", "sing-box", "wireguard", "tunnel"),
        "Network & Proxy",
    ),
    (("game", "gaming", "emulator", "launcher", "minecraft"), "Gaming"),
    (("chat", "messaging", "messenger", "im "), "Messaging"),
    (("player", "video", "audio", "music", "media"), "Media Players"),
    (("encrypt", "password", "security", "privacy", "vault"), "Security & Privacy"),
    (("docker", "kubernetes", "k8s", "devops", "cloud", "terraform"), "Cloud & DevOps"),
    (("download", "downloader", "torrent", "aria2"), "Download Tools"),
    (("note", "markdown", "productivity", "todo", "office"), "Productivity"),
    (
        (
            "cli",
            "git",
            "compiler",
            "sdk",
            "developer",
            "ide",
            "editor",
            "terminal",
            "debug",
        ),
        "Developer Tools",
    ),
    (
        ("disk", "system", "monitor", "cleaner", "uninstall", "registry"),
        "System Utilities",
    ),
]


def categorize(topics: list[str], description: str) -> str:
    """根据 GitHub topics 列表和仓库描述推断软件分类。

    Args:
        topics: GitHub 仓库 topics 列表（小写）
        description: 仓库描述文本

    Returns:
        匹配到的 category 字符串，默认返回 "Utilities"
    """
    haystack = " ".join(topics).lower() + " " + (description or "").lower()
    for keywords, category in _KEYWORD_CATEGORY:
        if any(k in haystack for k in keywords):
            return category
    return "Utilities"

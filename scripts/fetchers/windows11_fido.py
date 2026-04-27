"""Windows 11 ISO 抓取器 —— 包装 Fido.ps1。

Fido 是 Pete Batard 开源的 PowerShell 脚本（项目地址 https://github.com/pbatard/Fido，
GPL v3 协议），它通过模拟微软下载页的请求流程拿到一次性的 ISO 直链（约 24h 有效）。
我们只在每次同步时调用它生成新链接，因此 README 中的 ISO 链接每天会刷新。

需要环境里有 pwsh（pwsh-7+，跨平台 PowerShell Core）。在 GitHub Actions 的
ubuntu-latest 上预装；本地若没装可 `brew install --cask powershell`。
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .base import AssetInfo, FetchError, FetchResult


# Fido 脚本位置：从仓库根目录起的 third_party/Fido.ps1
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "third_party" / "Fido.ps1"

# 默认参数
DEFAULT_LANG = "Chinese (Simplified)"
DEFAULT_EDITION = "Pro"
DEFAULT_ARCH = "x64"
TIMEOUT = 180  # subprocess 等 Fido 全程的超时
MAX_ATTEMPTS = 3  # MS 端偶发超时（Fido 内部 30s 硬超时无法外部加长），失败重试
RETRY_BACKOFF = 5  # 重试间隔（秒）


def _run_fido(lang: str, edition: str, arch: str) -> str:
    if not SCRIPT_PATH.exists():
        raise FetchError(
            f"找不到 Fido 脚本：{SCRIPT_PATH}。请运行 scripts/install_fido.sh 或手动下载。"
        )

    cmd = [
        "pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(SCRIPT_PATH),
        "-Win",
        "11",
        "-Lang",
        lang,
        "-Ed",
        edition,
        "-Arch",
        arch,
        # PlatformArch 是 Fido 用来描述运行 Fido 的"主机"CPU 的参数。
        # 不传时 Fido 会调 Get-CimInstance（WMI，Windows 专属），在 Linux pwsh 上崩。
        # 我们对 ISO 架构本身只关心 -Arch（产物），主机架构无关紧要，传死 x64 即可。
        "-PlatformArch",
        "x64",
        "-GetUrl",
    ]
    last_err = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                check=False,
            )
        except FileNotFoundError as e:
            raise FetchError(f"未找到 pwsh，无法运行 Fido：{e}") from e
        except subprocess.TimeoutExpired:
            last_err = f"subprocess 超时（>{TIMEOUT}s）"
        else:
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            url_line = next(
                (
                    line
                    for line in reversed(stdout.splitlines())
                    if line.startswith("http")
                ),
                "",
            )
            if url_line:
                return url_line
            last_err = (
                f"Fido 未返回 URL。stdout={stdout!r} stderr={stderr!r} "
                f"returncode={proc.returncode}"
            )
        if attempt < MAX_ATTEMPTS:
            print(
                f"  ↻ Fido 第 {attempt} 次失败：{last_err[:80]}…，{RETRY_BACKOFF}s 后重试",
                flush=True,
            )
            time.sleep(RETRY_BACKOFF)

    raise FetchError(f"Fido 连续 {MAX_ATTEMPTS} 次失败，最后一次：{last_err}")


def _parse_release_from_url(url: str) -> tuple[str, str | None]:
    """
    从 Fido 返回的 URL 解析 release 名（如 24H2）和文件名。
    URL 形如：
      https://software.download.prss.microsoft.com/dbazure/Win11_24H2_Chinese_Simplified_x64.iso?t=...
    """
    parsed = urlparse(url)
    filename = unquote(Path(parsed.path).name)  # Win11_24H2_Chinese_Simplified_x64.iso
    m = re.search(r"Win11_([0-9]+H[12])", filename, re.IGNORECASE)
    release = m.group(1).upper() if m else "Latest"
    return release, filename or None


def fetch(args: dict[str, Any]) -> FetchResult:
    lang = args.get("lang", DEFAULT_LANG)
    edition = args.get("edition", DEFAULT_EDITION)
    arch = args.get("arch", DEFAULT_ARCH)

    url = _run_fido(lang, edition, arch)
    release, filename = _parse_release_from_url(url)

    asset = AssetInfo(
        platform=f"win-{arch}",
        url=url,
        filename=filename,
    )

    return FetchResult(
        id="",
        name=f"Windows 11 ({lang}, {edition})",
        version=release,
        source="Microsoft Software Download (via Fido)",
        version_kind="release_label",
        version_source="Fido ISO filename parsed from Microsoft download URL",
        homepage="https://www.microsoft.com/software-download/windows11",
        notes_url="https://learn.microsoft.com/windows/release-health/windows11-release-information",
        assets=[asset],
    )

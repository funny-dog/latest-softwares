"""NVIDIA App —— 固定跳转页 fetcher。

下载页为 JavaScript SPA，无法从静态 HTML 提取版本号。
"""

from ._redirect import make_redirect_fetcher


_DOWNLOAD_PAGE = "https://www.nvidia.com/en-us/software/nvidia-app/"

fetch = make_redirect_fetcher(
    id="nvidia-app",
    name="NVIDIA App",
    homepage=_DOWNLOAD_PAGE,
    download_page=_DOWNLOAD_PAGE,
)

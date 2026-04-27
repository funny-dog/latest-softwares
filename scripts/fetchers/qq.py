"""腾讯 QQ（QQNT）—— 固定跳转页 fetcher。

QQ 下载页为 JavaScript SPA，下载链接由 JS 动态生成，无公开版本 API。
"""

from ._redirect import make_redirect_fetcher


fetch = make_redirect_fetcher(
    id="qq",
    name="QQ",
    homepage="https://im.qq.com/",
    download_page="https://im.qq.com/download/",
)

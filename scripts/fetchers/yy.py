"""YY 语音 —— 固定跳转页 fetcher。"""

from ._redirect import make_redirect_fetcher


fetch = make_redirect_fetcher(
    id="yy",
    name="YY 语音",
    homepage="https://www.yy.com/",
    download_page="https://www.yy.com/",
)

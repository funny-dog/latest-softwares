"""WeGame 客户端 —— 固定跳转页 fetcher。

注：原实现 id 字段为空字符串，sync.py / 注册表实际使用的是 yaml 里的 id "wegame"，
此处补全以与 latest.json 中的稳定标识一致。
"""

from ._redirect import make_redirect_fetcher


fetch = make_redirect_fetcher(
    id="wegame",
    name="WeGame",
    homepage="https://www.wegame.com.cn/",
    download_page="https://www.wegame.com.cn/client/",
)

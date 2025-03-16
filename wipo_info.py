import random
import time

import requests
from fake_useragent import UserAgent
from playwright.sync_api import sync_playwright



def main_headless(proxy=None):
    """使用无头浏览器爬取异步加载的页面 proxy格式  http://ip:port 参考 https://requests.readthedocs.io/en/latest/user/advanced/#proxies """
    """无头浏览器安装教程 https://playwright.dev/python/docs/intro """
    playwright = sync_playwright().start()
    if proxy:
        browser_ui = playwright.firefox.launch(headless=False, proxy={"server": proxy})
    else:
        browser_ui = playwright.firefox.launch(headless=False)
    page = browser_ui.new_page()
    # 加载页面
    page.goto("https://patentscope.wipo.int/search/zh/detail.jsf?docId=WO2008012050&_cid=P12-M8B55R-69093-1")
    page.wait_for_load_state('networkidle')
    page.click('text=说明书')
    page.wait_for_load_state('networkidle')
    html=page.inner_html('body')
    time.sleep(1)
    page.close()
    browser_ui.close()
    playwright.stop()
    print(html)
    return html
def main():
    ua= UserAgent("edge")
    headers = {
        "User-Agent": ua.random,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
    }
    web = requests.get("https://patentscope.wipo.int/search/zh/detail.jsf?docId=WO2008012050&_cid=P12-M8B55R-69093-1", headers=headers)
    print(web.text)


if __name__ == '__main__':
    main_headless()
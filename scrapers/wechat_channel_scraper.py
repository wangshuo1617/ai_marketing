# scrapers/wechat_channel_scraper.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import config
import time

def scrape():
    """
    (代理策略) 抓取微信视频号相关内容。
    由于微信生态的封闭性，直接抓取视频号非常困难。
    此函数采用代理策略，通过搜索公开的社交媒体（如此处的微博）
    来发现与"视频号"相关的热门话题和内容。
    (Proxy Strategy) Scrapes content related to WeChat Video Channels.
    Directly scraping is difficult due to WeChat's closed ecosystem.
    This function uses a proxy strategy by searching a public social media platform (like Weibo)
    to find trending topics related to "视频号" (Video Channels).
    """
    print("  (采用代理策略抓取微信视频号相关内容)")
    all_results = []
    keywords = config.SEED_KEYWORDS["WECHAT_CHANNEL_PROXY_SEARCH"]
    
    for keyword in keywords:
        print(f"    - 抓取微博的关键词: '{keyword}'")
        # 使用微博搜索作为代理
        url = config.WECHAT_CHANNEL_PROXY_URL_TEMPLATE.format(query=quote(keyword))
        
        try:
            # 微博需要登录cookie才能看到更多结果，这里只做匿名访问的演示
            response = requests.get(url, headers=config.SCRAPER_HEADERS, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 微博搜索结果的选择器 (非常可能随时间改变)
            weibo_items = soup.select('.card-wrap[action-type="feed_list_item"]')

            for item in weibo_items:
                content_element = item.select_one('.content .txt')
                if content_element:
                    # 提取不含HTML标签的纯文本
                    title = content_element.get_text(strip=True)
                    
                    # 微博没有直接的标题/摘要，我们将整个帖子内容作为标题
                    # 并从帖子中提取链接作为URL
                    link_element = item.select_one('.from a[href*="weibo.com"]')
                    link = "https://weibo.com" + link_element['href'] if link_element else ''
                    
                    all_results.append({
                        'title': title[:150], # 截取一部分作为标题
                        'url': link,
                        'content': title # 内容和标题一致
                    })
            
            time.sleep(2) # 更加友好的抓取间隔

        except requests.exceptions.RequestException as e:
            print(f"      Error scraping Weibo (as proxy) for keyword '{keyword}': {e}")
            continue

    return all_results 
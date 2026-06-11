# scrapers/fdesk_scraper.py

import requests
from bs4 import BeautifulSoup
import config

def scrape():
    """
    抓取纷享销客博客页面的文章标题和链接。
    Scrapes article titles and links from the F-xiaoke (纷享销客) blog page.
    """
    url = config.TARGETS["FDESK_BLOG"]
    try:
        response = requests.get(url, headers=config.SCRAPER_HEADERS, timeout=10)
        response.raise_for_status()  # 如果请求失败则抛出HTTPError
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        articles = []
        # 注意: 此处的选择器(selector)是基于2025年6月纷享销客网站结构。
        # 如果网站改版，这里是唯一需要修改的地方。
        post_items = soup.select('.aw-mod.aw-topic-list .aw-item')
        
        for item in post_items:
            title_element = item.select_one('h4 a')
            if title_element:
                title = title_element.get_text(strip=True)
                link = title_element['href']
                
                if not link.startswith('http'):
                    link = "https://www.f-xiaoke.com" + link
                    
                articles.append({
                    'title': title,
                    'url': link,
                    'content': '' 
                })
        
        return articles

    except requests.exceptions.RequestException as e:
        print(f"Error scraping F-xiaoke: {e}")
        return [] 
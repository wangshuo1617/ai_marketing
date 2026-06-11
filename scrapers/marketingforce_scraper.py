# scrapers/marketingforce_scraper.py

import requests
from bs4 import BeautifulSoup
import config

def scrape():
    """
    抓取Marketingforce新闻页面的文章标题和链接。
    Scrapes article titles and links from the Marketingforce news page.
    """
    url = config.TARGETS["MARKETINGFORCE_NEWS"]
    try:
        response = requests.get(url, headers=config.SCRAPER_HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        articles = []
        post_items = soup.select('.news-list .item')
        
        for item in post_items:
            title_element = item.select_one('.title a')
            if title_element:
                title = title_element.get_text(strip=True)
                link = title_element['href']
                
                if not link.startswith('http'):
                    link = "https://www.marketingforce.com" + link
                
                summary_element = item.select_one('.desc')
                summary = summary_element.get_text(strip=True) if summary_element else ''

                articles.append({
                    'title': title,
                    'url': link,
                    'content': summary
                })
        
        return articles

    except requests.exceptions.RequestException as e:
        print(f"Error scraping Marketingforce: {e}")
        return [] 
# scrapers/zhihu_scraper.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import config
import time

def scrape():
    """
    针对种子关键词，在知乎进行搜索并抓取问题标题和摘要。
    Searches Zhihu for seed keywords and scrapes question titles and snippets.
    """
    all_results = []
    keywords = config.SEED_KEYWORDS["ZHIHU_SEARCH"]
    
    for keyword in keywords:
        print(f"    - 抓取知乎的关键词: '{keyword}'")
        url = config.ZHIHU_SEARCH_URL_TEMPLATE.format(query=quote(keyword))
        
        try:
            response = requests.get(url, headers=config.SCRAPER_HEADERS, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            result_items = soup.select('.SearchResult-Card')
            
            for item in result_items:
                question_element = item.select_one('.Highlight')
                if question_element:
                    title = question_element.get_text(strip=True)
                    
                    answer_element = item.select_one('.RichContent-inner')
                    summary = ''
                    if answer_element:
                        summary = answer_element.get_text(strip=True, separator=' ')[:200] + '...'
                    
                    link_element = item.select_one('a[data-za-detail-view-id]')
                    link = link_element['href'] if link_element else ''
                    if link and not link.startswith('http'):
                       link = "https://www.zhihu.com" + link

                    all_results.append({
                        'title': title,
                        'url': link,
                        'content': summary
                    })
            
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"      Error scraping Zhihu for keyword '{keyword}': {e}")
            continue

    return all_results 
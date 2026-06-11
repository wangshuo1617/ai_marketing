# scrapers/baidu_scraper.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import config
import time

def scrape():
    """
    针对种子关键词，抓取百度搜索结果的前2页。
    Scrapes the first 2 pages of Baidu search results for a list of seed keywords.
    """
    all_results = []
    keywords = config.SEED_KEYWORDS["BAIDU_SEARCH"]
    
    for keyword in keywords:
        print(f"    - 抓取百度的关键词: '{keyword}'")
        for page in range(2): 
            pn = page * 10
            url = config.BAIDU_SEARCH_URL_TEMPLATE.format(query=quote(keyword), page=pn)
            
            try:
                response = requests.get(url, headers=config.SCRAPER_HEADERS, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                result_containers = soup.select('.c-container[id]')
                
                for container in result_containers:
                    title_element = container.select_one('h3 a') or container.select_one('.t a')

                    if title_element:
                        title = title_element.get_text(strip=True)
                        link = title_element['href']
                        
                        summary_element = container.select_one('.c-abstract') or container.select_one('.c-span18')
                        summary = summary_element.get_text(strip=True) if summary_element else ''
                        
                        all_results.append({
                            'title': title,
                            'url': link,
                            'content': summary
                        })
                
                time.sleep(1)

            except requests.exceptions.RequestException as e:
                print(f"      Error scraping Baidu for keyword '{keyword}': {e}")
                continue 

    return all_results 
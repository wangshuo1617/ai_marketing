# scrapers/bilibili_scraper.py

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import quote
import config
import time

def scrape():
    """
    使用Selenium抓取Bilibili搜索结果，因为它是动态加载的。
    Scrapes Bilibili search results using Selenium due to dynamic content loading.
    
    注意：此函数需要本地安装Chrome浏览器和对应的WebDriver。
    `webdriver-manager`库会自动处理WebDriver的下载和路径设置。
    """
    all_results = []
    keywords = config.SEED_KEYWORDS["BILIBILI_SEARCH"]

    # --- Selenium 设置 ---
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式，不打开浏览器窗口
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"user-agent={config.SCRAPER_HEADERS['User-Agent']}")

    try:
        # 使用 webdriver-manager 自动管理 driver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    except Exception as e:
        print(f"  [!] Selenium WebDriver 初始化失败: {e}")
        print("  [!] 请确保您已安装Google Chrome浏览器。")
        print("  [!] 此爬虫将被跳过。")
        return []
    
    print("  (Selenium WebDriver 初始化成功)")

    for keyword in keywords:
        print(f"    - 抓取Bilibili的关键词: '{keyword}'")
        url = config.BILIBILI_SEARCH_URL_TEMPLATE.format(query=quote(keyword))
        
        try:
            driver.get(url)
            # 等待JavaScript加载完成，这里给一个固定的等待时间
            # 更稳健的方法是使用 WebDriverWait 等待特定元素出现
            time.sleep(5) 

            soup = BeautifulSoup(driver.page_source, 'lxml')
            
            # Bilibili搜索结果的选择器 (可能会变)
            video_items = soup.select('.video-list .bili-video-card')

            for item in video_items:
                title_element = item.select_one('.bili-video-card__info--right .bili-video-card__info__tit')
                if title_element:
                    title = title_element.get_text(strip=True)
                    link = title_element.get('href')
                    if link and not link.startswith('http'):
                        link = "https:" + link
                    
                    # 摘要通常是UP主名字和播放量，这里我们组合一下
                    stats_elements = item.select('.bili-video-card__info--right .bili-video-card__stats span')
                    summary = " | ".join([s.get_text(strip=True) for s in stats_elements])

                    all_results.append({
                        'title': title,
                        'url': link,
                        'content': summary
                    })
            
        except Exception as e:
            print(f"      Error scraping Bilibili for keyword '{keyword}': {e}")
            continue

    driver.quit()
    return all_results 
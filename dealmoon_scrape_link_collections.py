import logging
import re
import tempfile
import time
import urllib.parse
import json
from logging.handlers import RotatingFileHandler
import json
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from groq import Groq
from httpx import TimeoutException
from pymongo import MongoClient
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, timezone
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException, StaleElementReferenceException
import ast
import atexit
from datetime import datetime
import pytz
import re
app = Flask(__name__)


def scrape_deals(max_items=100, url="https://www.dealmoon.com/en/clothing-jewelry-bags/womens-clothing", collections=None):    
    app.logger.info(f"Max item count is : {max_items}")
    # chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Remove this line during debugging
    # chrome_options.add_argument('--no-sandbox')
    # chrome_options.add_argument('--disable-dev-shm-usage')
    # chrome_options.add_argument('--disable-gpu')
    # chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    # chrome_options.add_argument("--remote-debugging-port=9222")
    # chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')  # or '--headless' if 'new' causes issues
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # chrome_options.add_argument("--enable-unsafe-swiftshader")


    
    headers = {
        'User-Agent': 'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': url
    }
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')
    user_data_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    try:
        driver = Chrome(options=chrome_options)
        driver.set_page_load_timeout(90)
        driver.implicitly_wait(10)
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "dealsList"))
        )
    # Scroll until no more content loads
        last_height = driver.execute_script("return document.body.scrollHeight")
        # while True:
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # wait for content to load
            print(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break  # no more content
            last_height = new_height

    except TimeoutException:
        driver.quit()
        raise  # re-raise or handle as needed

    # Parse page source after scrolling
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # Get just the dealsList section (optional)
    deals_section = soup.find(id="dealsList")
    link_tags = deals_section.find_all("a", class_="zoom-title event_ga_statistics")

    # collection.create_index("href", unique=True)
    links = []
    for tag in link_tags:
        href = tag.get("href")
        text_span = tag.find("span", class_="txt")
        text = text_span.get_text(strip=True) if text_span else ""
        print(f"hahahhaha{href} and {text}")
        # if not collection.find_one({"href": href}):
        #     collection.insert_one({"href": href, "description": text})
            # Append to list if href is not already present
        if not any(item["href"] == href for item in links):
            links.append({"href": href, "description": text})
        
    with open("dealmoon_links.json", "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=4)





if __name__ == '__main__':
    # client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")
    # db = client["try_database"]                        # database name
    # collection = db["dealmoonlinks"]
    # coupons = scrape_deals(collections=collection)
    # print(coupons)
    scrape_deals()

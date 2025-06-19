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
from selenium import webdriver
app = Flask(__name__)

def get_final_link(url):
    # Setup headless browser
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    # Go to the initial redirect link
    driver.get(url)

    # Wait for redirect to complete
    driver.implicitly_wait(5)

    # Get final URL
    final_url = driver.current_url
    clean_url = final_url.split('?')[0]
    driver.quit()
    return clean_url

def get_right_info(soup):
    right = soup.find(class_='edit-content').find(class_='event_statistics') or soup.select_one('.edit-content.event_statistics')
    
    offers = {
        "description": {},
        "link": None,
        "coupon": None,
        "shipping_info": None
    }

    # Start counters
    desc_counter = 1

    if right:
        for li in right.find_all('li'):
            text = li.get_text(strip=True)

            # Add to description
            offers["description"][desc_counter] = text
            desc_counter += 1

            # Capture first link
            if not offers["link"]:
                a_tag = li.find('a')
                if a_tag:
                    offers["link"] = get_final_link(url=a_tag.get('href'))

            # Capture first coupon
            if not offers["coupon"]:
                b_tag = li.find('b', class_='coupon')
                if b_tag:
                    offers["coupon"] = b_tag.get('data-clipboard-text')

            # Identify shipping info
            if 'shipping' in text.lower() and not offers["shipping_info"]:
                offers["shipping_info"] = text

    # Final result
    result = {
        "offers": offers
    }
    return result

def get_bottom_info(soup):
    elements = soup.find_all(
    lambda tag: tag.has_attr('class') and all(cls in tag['class'] for cls in [
        "js-sp-item", 
        "tw", 
        "detail_page", 
        "criteo_product_item", 
        "large", 
        "heighted"
    ])
    )
    products_dict = {"products": {}}

    # Extract data
    for i, product in enumerate(elements, start=0):
        # data_id = product.get("data-id")
        data_price = product.get("data-price")
        
        link_tag = product.find("a", class_="event_statics_action")
        product_url = get_final_link(link_tag["href"]) if link_tag else None

        # img_tag = product.find("img", class_="lazyload tw_pic")
        # image_url = img_tag.get("data-src") if img_tag else None

        price_p = product.find("p", class_="tw_text")
        current_price = price_p.get_text(strip=True) if price_p else None
        # current_price = price_p.get_text(strip=True).split("\n")[0] if price_p else None
        original_price = price_p.find("i").get_text(strip=True) if price_p and price_p.find("i") else None
        data_price = original_price[0]+data_price if original_price != None else data_price

        title_p = product.find("p", class_="deal_text")
        title = title_p.get_text(strip=True) if title_p else None

        products_dict["products"][i] = {
            # "data_id": data_id,
            "product_url": product_url,
            # "image_url": image_url,
            "current_price": data_price,
            "original_price": original_price,
            "title": title
        }

def format_description(desc):

        # Insert space between lowercase/word and number/uppercase (e.g., "offers40%" → "offers 40%")
        desc = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', desc)
        desc = re.sub(r'(\d)([A-Z])', r'\1 \2', desc)

        # Insert space after punctuation if missing
        desc = re.sub(r'(\.)(\w)', r'\1 \2', desc)

        # Ensure spaces after colons
        desc = re.sub(r':(\S)', r': \1', desc)

        return desc.strip()

def get_soup(url="https://www.dealmoon.com/en/up-to-extra-30-off-bloomingdales-buy-more-save-more-event/5006043.html",max_items=100,  collections=None):    
    app.logger.info(f"Max item count is : {max_items}")
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')  # or '--headless' if 'new' causes issues
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--enable-unsafe-swiftshader")
    


    
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
            #TODO: what 
            EC.presence_of_element_located((By.CLASS_NAME, "mlist_box"))
            # EC.presence_of_element_located((By.CLASS_NAME, "minfor edit-content event_statistics"))
        )

    except TimeoutException:
        driver.quit()
        raise  # re-raise or handle as needed

    # Parse page source after scrolling
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()
    return soup



if __name__ == '__main__':
    # client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")
    # db = client["try_database"]                        # database name
    # collection = db["dealmoonlinks"]
    # coupons = scrape_deals(collections=collection)
    # print(coupons)
    soup = get_soup(url="https://www.dealmoon.com/en/up-to-70-off-soma-semi-annual-sale/5036152.html?rip=aG9tZV9saXN0fGNsb3RoaW5nLWpld2VscnktYmFncyU3Q3dvbWVucy1jbG90aGluZ3wz")
    right = get_right_info(soup=soup)
    print(right)
    bottom = get_bottom_info(soup=soup)
    print(bottom)
    # with open ("dealmoon_links.json", "r", encoding="utf-8") as f:
    #     for store in f:
    #         print(store)
    #         # returned = scrape_deals(url=store.href)

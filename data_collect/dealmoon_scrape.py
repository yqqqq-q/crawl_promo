
import tempfile
import logging
from logging.handlers import RotatingFileHandler
import json
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from httpx import TimeoutException
from pymongo import MongoClient
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, timezone
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException, StaleElementReferenceException, WebDriverException
from datetime import datetime
from selenium import webdriver
import undetected_chromedriver as uc
import time
from urllib.parse import urlparse

logging.basicConfig(
    filename='logs/crawler_detail_dealmoon.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

def dealmoon_scrape_links(file_name, collection, url="https://www.dealmoon.com/en/clothing-jewelry-bags/womens-clothing", ):  
      
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')  # or '--headless' if 'new' causes issues
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')

    
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

        # Get initial scroll height
        last_height = driver.execute_script("return document.body.scrollHeight")
        same_height_count = 0  # Counter to avoid false exit
        max_same_height = 3    # Require 3 unchanged scrolls to consider end

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            driver.implicitly_wait(5)  # Allow time for content to load

            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                same_height_count += 1
                if same_height_count >= max_same_height:
                    print("No more new content. Exiting.")
                    break
            else:
                same_height_count = 0  # Reset if new content loaded

            last_height = new_height
            print("Scrolled, new height:", new_height)

    except TimeoutException:
        driver.quit()
        raise  # re-raise or handle as needed

    # Parse page source after scrolling
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # Get just the dealsList section (optional)
    deals_section = soup.find(id="dealsList")
    link_tags = deals_section.find_all("a", class_="zoom-title event_ga_statistics")

    # update
    collection.update_many({}, {"$set": {"deprecate": True}})


    links = []
    update_count  = 0
    for tag in link_tags:
        href = tag.get("href")
        text_span = tag.find("span", class_="txt")
        text = text_span.get_text(strip=True) if text_span else ""
            # Only insert/update if href is not already in the collection
        status = collection.update_one(
            {"href": href},  # Query filter
            {"$setOnInsert": {"href": href, "description": text, "deprecate": False}},  # Only set if inserting
            upsert=True  # Insert if not already present
        )
    if status.upserted_id is not None:
        update_count += 1
    
    return update_count


def get_final_link(url):
    options = Options()
    # options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(15)  # Set max wait time

        try:
            driver.get(url)
            final_url = driver.current_url
            if final_url.startswith("https://go.dealmoon.com/exec"):
                clean_url = url
            else:
                clean_url = final_url.split('?')[0]
        except TimeoutException:
            print(f"[Timeout] Failed to load: {url}")
            clean_url = url
        except WebDriverException as e:
            print(f"[WebDriver Error] {e} for URL: {url}")
            clean_url = url
        finally:
            driver.quit()
        return clean_url

    except Exception as e:
        print(f"[Fatal Error] Could not start WebDriver: {e}")
        return url

def get_right_info(soup):
    # right = soup.find(class_='edit-content').find(class_='event_statistics') or soup.select_one('.edit-content.event_statistics')
    title = soup.select_one('.title .txt')
    subtitle = soup.select_one('.subtitle')
    details_list = []
    shipping_info = ""
    expire_data = ""
    coupon_code = None

    for li in soup.select('.minfor ul li'):
        text = li.get_text(" ", strip=True)
        if not text or text.lower() in ["buy >>", "buy>>"]:
            continue

        # Extract coupon code correctly
        coupon_tag = li.find('b', class_='coupon')
        coupon_code = coupon_tag.get_text(strip=True) if coupon_tag else None

        # Shipping info detection
        if 'shipping' in text.lower() or 'ship' in text.lower():
            shipping_info = text
            continue

        # Expiry info detection
        if any(kw in text.lower() for kw in ['ends', 'expires', 'until']):
            expire_data = text
            continue

        entry = {"description": text}
        if coupon_code:
            entry["coupon"] = coupon_code

        details_list.append(entry)

    offers = {
        "title": title.get_text(strip=True) if title else "",
        "subtitle": subtitle.get_text(strip=True) if subtitle else "",
        "detail": details_list,
        "shipping_info": shipping_info,
        "expire_info": expire_data
    }
    return offers


def get_bottom_info(collection, soup, href):
    container = soup.find("div", id="spBox", class_=["dpc", "j-dpc"])
    if not container:
        return
    
    products = container.find_all("div", class_="js-sp-item")
    
    for product in products:
        link_tag = product.find("a", class_="event_statics_action")
        product_url = get_final_link(link_tag["href"]) if link_tag else None

        price_block = product.find("p", class_="tw_text")
        if price_block:
            current_price = price_block.find(text=True, recursive=False)
            current_price = current_price.strip() if current_price else None

            i_tag = price_block.find("i")
            original_price = i_tag.get_text(strip=True) if i_tag else None
        else:
            current_price = None
            original_price = None

        title_p = product.find("p", class_="deal_text")
        title = title_p.get_text(strip=True) if title_p else None

        product_data = {
            "href": href,
            "product_url": product_url,
            "current_price": current_price,
            "original_price": original_price,
            "title": title
        }

        collection.update_one(
            {"href": product_url},  # Query condition
            {"$set": product_data},  # Update operation
            upsert=True
        )

def clean_up(link, item, store):
    # Get hrefs from deprecated links
    deprecated_links = link.find({"deprecate": True}, {"href": 1})
    hrefs_to_delete = [doc["href"] for doc in deprecated_links if "href" in doc]
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }

    for href in hrefs_to_delete[:]:  # Use a slice to safely modify the list while iterating
        response = requests.get(href, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Check if the "expire-txt" class exists
        if not soup.find(class_="expire-txt"):
            hrefs_to_delete.remove(href)

    # Delete from store, item and link collection where href matches
    if hrefs_to_delete:
        item.delete_many({"href": {"$in": hrefs_to_delete}})
        store.delete_many({"href": {"$in": hrefs_to_delete}})
        link.delete_many({"href": {"$in": hrefs_to_delete}})
        print(hrefs_to_delete)
    

# TODO: 
def get_final_url_repeat(collection):
    dealmoon_item_collection = collection

    # Find documents where 'product_url' starts with the specified string
    cursor = dealmoon_item_collection.find({
        "product_url": {
            "$regex": r"^https://go\.dealmoon\.com/exec"
        }
    })

    # Print or process the results
    for doc in cursor:
        print(doc)


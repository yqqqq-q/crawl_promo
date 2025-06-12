import logging
import re
import tempfile
import time
import urllib.parse
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

import atexit
app = Flask(__name__)




# def scrape_deals(collection_by_gender, collection_all, max_items=100, url="https://promocodes.com/coupons/clothing"):
def scrape_deals(max_items=100, url="https://promocodes.com/coupons/clothing"):
    app.logger.info(f"Max item count is : {max_items}")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Remove this line during debugging
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument("--remote-debugging-port=9222")

    
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
            EC.presence_of_element_located((By.ID, "__NEXT_DATA__"))
        )
        app.logger.info(f"Starting scrape on URL: {url}")  # Log start of scraping
        while True:
            try:
                # Wait for button to appear
                button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".px-4.py-2.rounded.bg-yellow-100.shadow.text-sm.font-semibold.my-6.w-\\[220px\\]"))
                )
                button.click()

            except (NoSuchElementException, TimeoutException):
                print("No more buttons to click.")
                break
            except ElementClickInterceptedException:
                print("Button not clickable, retrying...")
                break
            except Exception as e:
                print(f"Unexpected error while clicking button: {e}")
                break  # Exit the loop for any other unexpected errors

        soup = BeautifulSoup(driver.page_source, "html.parser")
        extracted_data = soup.find("script", {"id": "__NEXT_DATA__"})


    except TimeoutException:
        print("Failed to load page or locate elements in time. Exiting crawl.")
    finally:
        driver.quit()

    if extracted_data:
        data = json.loads(extracted_data.string)
        full_coupons = data['props']['pageProps'].get('coupons', [])
        coupons = [
            {
                "couponId": c.get("couponId"),
                "description": c.get("description"),
                "expirationDate": c.get("expirationDate")
            }
            for c in full_coupons
        ]
    # # for coupon in coupons:
    for coupon in coupons[:3]:
        url_each = f"{url}?c={coupon['couponId']}"
        print(url_each)
        try:
            driver = Chrome(options=chrome_options)
            driver.set_page_load_timeout(90)
            driver.implicitly_wait(10)
            driver.get(url_each)

            code_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "code"))
        )

        # Extract the code text
            coupon_code = code_element.text.strip()
            print(f"Coupon code found: {coupon_code}")

        # Store it back into the coupon dict
            coupon["couponCode"] = coupon_code
        except TimeoutException:
            print("Failed to load page or locate elements in time. Exiting crawl.")
        finally:
            driver.quit()

    return coupons



if __name__ == '__main__':
    coupons = scrape_deals()
    print(coupons)
    client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")
    db = client["try_database"]
    collection = db["promocode"]
    
    for coupon in coupons:
    # Check if an identical document already exists
        existing = collection.find_one(coupon)
    
        if not existing:
            collection.insert_one(coupon)
            print(f"Inserted couponId: {coupon.get('couponId')}")
        else:
            print(f"Duplicate found, skipped couponId: {coupon.get('couponId')}")


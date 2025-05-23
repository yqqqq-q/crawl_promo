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
import ast
import atexit
app = Flask(__name__)




# def scrape_deals(collection_by_gender, collection_all, max_items=100, url="https://promocodes.com/coupons/clothing"):
def scrape_deals(max_items=100, url="https://www.retailmenot.com/coupons/clothing-shoes-accessories"):
    app.logger.info(f"Max item count is : {max_items}")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Remove this line during debugging
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-software-rasterizer")

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
            EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'bg-purple-700') and contains(@class, 'rounded-full')]"))
        )
        app.logger.info(f"Starting scrape on URL: {url}")  # Log start of scraping
        while True:
            try:
                # Wait for button to appear
                button = WebDriverWait(driver, 5).until(
                    # EC.element_to_be_clickable((By.XPATH, "//*[contains(@class, 'bg-purple-700') and contains(@class, 'rounded-full')]"))
                    EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Show More Offers']]"))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                time.sleep(2)
                print("ckucj clickjshfdskjfhskdjfh")

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

        
        # anchor_elements = driver.find_elements(By.TAG_NAME, "a")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        extracted_data_list = soup.find_all("a", class_=[
        "relative", "mb-5", "block", "flex", "h-full", "cursor-pointer", "overflow-hidden", "bg-white",
        "md:h-auto", "md:min-h-[278px]", "md:flex-col", "md:rounded-xl", "md:border",
        "lg:h-32", "lg:flex-col"
        ]) 
        print(extracted_data_list[1])
        coupons = []

        for a in extracted_data_list:
            x_data = a.get("x-data")
            if x_data:
                match = re.search(r"outclickHandler\((\{.*?\})\)", x_data)
                if match:
                    js_dict_str = match.group(1)
                    try:
                        py_dict = ast.literal_eval(js_dict_str.replace("null", "None"))

                        #if adding more from <a>
                        if py_dict.get("offerType") == "COUPON":
                    # Add store name from <h3>
                            h3 = a.find("h3", class_="text-xs font-bold uppercase tracking-wide md:mt-2")
                            if h3:
                                py_dict["store_name"] = h3.get_text(strip=True)

                    # Add deal description from <p>
                            deal = a.find("p", class_="my-2 line-clamp-2 font-proxima text-base capitalize leading-5 md:mb-auto md:line-clamp-3")
                            if deal:
                                py_dict["deal_description"] = deal.get_text(strip=True)
                            py_dict.pop("offerUuid", None)
                            coupons.append(py_dict)
                    except Exception as e:
                        print("Error parsing x-data:", e)

    except TimeoutException:
        print("Failed to load page or locate elements in time. Exiting crawl.")
    finally:
        driver.quit()


    # # for coupon in coupons:
    for coupon in coupons:
        url_each = f"{url}{coupon['siteLink']}"
        try:
            driver = Chrome(options=chrome_options)
            driver.set_page_load_timeout(90)
            driver.implicitly_wait(10)
            driver.get(url_each)

            soup = BeautifulSoup(driver.page_source, "html.parser")

            expire_date = "unknown"
            opener_div = soup.find("div", class_="opener")
            if opener_div:
                    for p in opener_div.find_all("p", class_="text-base font-semibold", recursive=False):
                        if "Ends" in p.text:
                            expire_date = p.text.strip()
                            break
            coupon["expireAt"] = expire_date
            print(expire_date)

            target_div = soup.find('div', class_=lambda x: x and 'bg-clip-text' in x and 'rounded-full' in x)
            if target_div and target_div.get("x-data") == "codeGenerator()":
                coupon_code = target_div.text.strip()
                coupon["couponCode"]=coupon_code[:-6]
                print(coupon["couponCode"])

        except TimeoutException:
            print("Failed to load page or locate elements in time. Exiting crawl.")
        except Exception as e:
            print("Error parsing x-data:", e)
        finally:
            driver.quit()

    return coupons



if __name__ == '__main__':
    coupons = scrape_deals()
    print(coupons)
    # client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")
    # db = client["try_database"]
    # collection = db["retailmenot_1"]
    
    # for coupon in coupons:
    # # Check if an identical document already exists
    #     existing = collection.find_one(coupon)
    
    #     if not existing:
    #         collection.insert_one(coupon)
    #         print(f"Inserted siteLink: {coupon.get('siteLink')}")
    #     else:
    #         print(f"Duplicate found, skipped siteLink: {coupon.get('siteLink')}")

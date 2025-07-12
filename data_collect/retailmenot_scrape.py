import logging
import re
import tempfile
import time
from logging.handlers import RotatingFileHandler
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from httpx import TimeoutException
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, timezone
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException, StaleElementReferenceException
import ast
import pytz
import re


def retailmenot_scrape_deals(collection, url="https://www.retailmenot.com/coupons/clothing-shoes-accessories", scroll_times=8):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # use "--headless=new" for newer Chrome
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

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
        driver = None
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(90)
        driver.implicitly_wait(10)
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'bg-purple-700') and contains(@class, 'rounded-full')]"))
        )
        # while True:
        for _ in range(scroll_times):
            try:
                # Wait for button to appear
                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Show More Offers']]"))
                )

                # Scroll to button
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)

                driver.implicitly_wait(2)  # Small delay to allow scrolling effects to settle

                button.click()
                print("Button clicked.")

                # Wait for content update to ensure next button is ready (tweak XPATH/content as needed)
                WebDriverWait(driver, 10).until_not(
                    EC.staleness_of(button)
                )

            except (NoSuchElementException, TimeoutException):
                print("No more buttons to click or timeout.")
                break

            except (ElementClickInterceptedException, StaleElementReferenceException):
                print("Button not clickable or stale, retrying...")
                driver.implicitly_wait(2)
                continue

            except Exception as e:
                print(f"Unexpected error while clicking button: {e}")
                break

        # anchor_elements = driver.find_elements(By.TAG_NAME, "a")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        extracted_data_list = soup.find_all("a", class_=[
        "relative", "mb-5", "block", "flex", "h-full", "cursor-pointer", "overflow-hidden", "bg-white",
        "md:h-auto", "md:min-h-[278px]", "md:flex-col", "md:rounded-xl", "md:border",
        "lg:h-32", "lg:flex-col"
        ]) 
        coupons = []

        for a in extracted_data_list:
            x_data = a.get("x-data")
            if x_data:
                match = re.search(r"outclickHandler\((\{.*?\})\)", x_data)
                if match:
                    js_dict_str = match.group(1)
                    try:
                        py_dict = ast.literal_eval(js_dict_str.replace("null", "None"))

                        # if data already collected, skip
                        sitelink = py_dict.get("siteLink")
                        if collection.find_one({"siteLink": sitelink}):
                            continue

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
        if driver:
            driver.quit()


    # for new coupon in coupons:
    count = 0
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
                coupon_raw = target_div.text.strip()
                coupon_raw = coupon_raw[:-6].strip()
                coupon["couponCode"]=coupon_raw
                print(coupon["couponCode"])
            
            count += store_data(collection=collection, coupon=coupon)

        except TimeoutException:
            print("Failed to load page or locate elements in time. Exiting crawl.")
        except Exception as e:
            print("Error:", e)
        finally:
            driver.quit()

    return count


def store_data(collection, coupon):
    expire_text = coupon.get("expireAt", "").strip()
    expire_date = parse_expire_date(expire_text)

    # # Only attach expireDate if valid
    if expire_date:
        coupon["expireDate"] = expire_date
    # else:
    #     coupon["delete_at"] = (datetime.now() + timedelta(weeks=1)).isoformat()

    coupon.pop("expireAt", None)

    status = collection.insert_one(coupon)
    return 1 if status.inserted_id is not None else 0



def parse_expire_date(text):
    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
    if match:
        month, day, year = match.groups()
        # Return as UTC datetime
        return datetime(int(year), int(month), int(day), tzinfo=pytz.UTC)
    return None


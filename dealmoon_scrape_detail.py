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


def scrape_deals(url="https://www.dealmoon.com/en/up-to-extra-30-off-bloomingdales-buy-more-save-more-event/5006043.html",max_items=100,  collections=None):    
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
            EC.presence_of_element_located((By.ID, "spBox"))
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
    returned = scrape_deals(url='https://www.dealmoon.com/en/up-to-50-off-net-a-porter-mid-year-sale/5019789.html')
    print(returned)


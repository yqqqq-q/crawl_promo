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
import atexit

def extract_date_from_string(s):
    # If the string contains a '/', extract the date
    match = re.search(r'(\d{1,2}/\d{1,2})', s)
    if match:
        return match.group(1)
    return None
def scrape_deals(url='https://www.dealmoon.com/en/clothing-jewelry-bags/womens-clothing',  max_items=5):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Remove this line during debugging
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
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
    driver = Chrome(options=chrome_options)

    driver.set_page_load_timeout(90)
    driver.implicitly_wait(10)

    scraped_items = []
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "dealsList"))
        )

    except TimeoutException:
        driver.quit()
        return scraped_items

    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        while len(scraped_items) < max_items:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            deals_list = soup.find('body').find('section', id='dealsList')
            if not deals_list:
                # app.logger.warning(
                    # f"'dealsList' section not found on the page. Skipping further scraping for URL: {url}")
                break

            mlist_divs = deals_list.find_all('div', class_='mlist v2', limit=max_items - len(scraped_items))

            # app.logger.info(f"Found {len(mlist_divs)} deals in current batch")

            for idx, mlist in enumerate(mlist_divs):
                try:
                    # 提取 dealId
                    deal_id = mlist.get('data-dmt-d-deal-id')
                    if not deal_id:
                        # app.logger.warning(f"Skipping deal {idx + 1}: 'dealId' not found")
                        continue

                    # if collection_by_gender.count_documents({'dealId': deal_id}) > 0:
                    #     app.logger.info(f"Skipping deal {deal_id} as it already exists in the database")
                    #     continue

                    p_left = mlist.find('div', class_='p-left')
                    if not p_left:
                        # app.logger.warning(f"Skipping deal {idx + 1}: 'p-left' div not found")
                        continue

                    shop_now_link = p_left.find('a', class_='btn-buy')
                    if shop_now_link is None or 'href' not in shop_now_link.attrs:
                        # app.logger.warning(f"Skipping deal {idx + 1}: 'shop_now_link' not found or invalid")
                        continue

                    shop_now_link = shop_now_link['href']

                    try:
                        driver.get(shop_now_link)
                        final_url = driver.current_url
                    except (requests.RequestException, Exception) as e:
                        # app.logger.error(f"Failed to follow redirects for {shop_now_link}: {str(e)}")
                        final_url = shop_now_link  # Fall back to shop_now_link

                    parsed_url = urllib.parse.urlparse(final_url)
                    cleaned_url = urllib.parse.urlunparse(
                        (parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

                    p_right = mlist.find('div', class_='p-right')
                    if not p_right:
                        # app.logger.warning(f"Skipping deal {idx + 1}: 'p-right' div not found")
                        continue

                    title_link = p_right.find('a', class_='zoom-title')
                    if not title_link or 'href' not in title_link.attrs:
                        # app.logger.warning(f"Skipping deal {idx + 1}: 'title_link' not found or invalid")
                        continue
                    title_link = title_link['href']

                    # app.logger.info(f"Scraping deal details at: {title_link}")

                    try:
                        # detail_response = requests.get(title_link, headers=headers, timeout=10)
                        # detail_response.raise_for_status()
                        detail_soup = BeautifulSoup(driver.page_source, "html.parser")
                    except (requests.RequestException, Exception) as e:
                        # app.logger.error(f"Failed to fetch details from {title_link}: {str(e)}")
                        continue  # Skip to next deal

                    title = detail_soup.find('h1', class_='title')
                    if not title:
                        # app.logger.warning(f"No title found for deal: {title_link}")
                        title = "Unknown Title"
                    else:
                        title = title.get_text(strip=True)

                    subtitle = detail_soup.find('div', class_='subtitle')
                    subtitle = subtitle.get_text(strip=True) if subtitle else "No Subtitle Available"

                    details_ul = detail_soup.select_one('div.mbody .minfor ul')
                    details = []
                    expire_at = datetime.now() + timedelta(days=30)
                    # app.logger.info(f"Default expire time is {expire_at} for deal: {title_link}")
                    if details_ul:
                        for li in details_ul.find_all('li'):
                            text = li.get_text(strip=True)
                            details.append(text)
                            if text.startswith('Deal ends'):
                                # app.logger.info(f"Expire info is {text} for deal: {title_link}")
                                expire_at_str = extract_date_from_string(text)
                                # app.logger.info(f"Expire info is {expire_at_str} for deal: {title_link}")
                                expire_at = datetime.strptime(expire_at_str, '%m/%d')
                                current_year = datetime.now().year
                                expire_at = expire_at.replace(year=current_year)
                                expire_at = expire_at.replace(tzinfo=timezone.utc)
                                # app.logger.info(f"Final expire time is {expire_at} for deal: {title_link}")
                                break
                    else:
                        print("no detail found")
                        # app.logger.warning(f"No details found for deal: {title_link}")

                    deal_info = {
                        'dealId': deal_id,
                        'shop_now_link': cleaned_url,
                        'title_link': title_link,
                        'title': title,
                        'subtitle': subtitle,
                        'details': details,
                        'scrape_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'expireAt': expire_at.strftime('%Y-%m-%d')
                    }

                    # app.logger.debug(f"Scraped deal info: {deal_info}")
                    scraped_items.append(deal_info)

                    # Save periodically to ensure scraped data is not lost in case of crashes
                    # if len(scraped_items) % 5 == 0:  # Every 5 deals
                    #     app.logger.info(f"Saving {len(scraped_items)} deals to the database")
                    #     collection_by_gender.insert_many(scraped_items)
                    #     collection_all.insert_many(scraped_items)
                    #     scraped_items.clear()  # Clear list after saving to avoid duplication

                    if len(scraped_items) >= max_items:
                        # app.logger.info("Reached maximum specified items for scraping")
                        break

                except Exception as inner_e:
                    print(inner_e)
                    # app.logger.error(f"Exception occurred while processing a deal: {str(inner_e)}", exc_info=True)

    except Exception as e:
        # app.logger.error(f"Exception occurred during scraping: {str(e)}", exc_info=True)
        print(e)
        driver.quit()

    finally:
        driver.quit()

    # if scraped_items:
    #     app.logger.info(f"Saving remaining {len(scraped_items)} deals to the database")
    #     collection_by_gender.insert_many(scraped_items)
    #     collection_all.insert_many(scraped_items)  # Save any remaining deals after the loop

    # app.logger.info(f"Total scraped items: {len(scraped_items)}")
    return scraped_items


if __name__ == '__main__':
    coupons = scrape_deals()
    with open("deals.json", "w") as f:
        json.dump(coupons, f, indent=4)
    # print(coupons)
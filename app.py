import logging
import re
import tempfile
import time
import urllib.parse
from logging.handlers import RotatingFileHandler

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


def rewrite_sentence(sentence):
    api_key = "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"
    client = Groq(api_key=api_key)
    prompt = f"Rewrite the following sentence while maintaining the original length and immediately return the new sentence without any additional text or comments: '{sentence}'"
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        model="llama3-8b-8192",
    )
    rewritten_sentence = chat_completion.choices[0].message.content
    rewritten_sentence = rewritten_sentence.replace('"', '').replace("'", "")
    return rewritten_sentence


def ensure_expire_index(collection, expire_after):
    """
    Ensure that the given collection has a TTL index on the "expireAt" field
    with expireAfterSeconds set to the provided expire_after value.
    If such an index does not exist, create it.

    :param collection: The MongoDB collection.
    :param expire_after: The number of seconds after expireAt for the document to expire.
    """
    # Retrieve existing index information; this returns a dictionary where keys are index names.
    indexes = collection.index_information()

    # Flag to indicate if an appropriate TTL index is found.
    found = False

    # Iterate over the existing indexes
    for index_name, index_info in indexes.items():
        # The "key" field is a list of tuples, e.g., [('expireAt', 1)]
        if any(field == "expireAt" for field, order in index_info.get("key", [])):
            # Check if the TTL option is present and matches the desired value.
            if index_info.get("expireAfterSeconds") == expire_after:
                found = True
                break

    # If no matching TTL index is found, create one.
    if not found:
        collection.create_index("expireAt", expireAfterSeconds=expire_after)

def extract_date_from_string(s):
    # If the string contains a '/', extract the date
    match = re.search(r'(\d{1,2}/\d{1,2})', s)
    if match:
        return match.group(1)
    return None
app = Flask(__name__)
if not app.debug:
    file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    app.logger.setLevel(logging.DEBUG)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('Application startup')

# client = MongoClient("mongodb+srv://logoman:abcd1234@cluster0.om1oelb.mongodb.net/?retryWrites=true&w=majority")
# client = MongoClient('mongodb://localhost/')
client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")

db = client['deals_database']
women_deals_collection = db['women_deals']
men_deals_collection = db['men_deals']
deals_collection = db['deals']

ensure_expire_index(women_deals_collection, 86400)
ensure_expire_index(men_deals_collection, 86400)
ensure_expire_index(deals_collection, 86400)


def scheduled_scrape():
    men_url = 'https://www.dealmoon.com/en/clothing-jewelry-bags/mens-clothing'
    women_url = 'https://www.dealmoon.com/en/clothing-jewelry-bags/womens-clothing'

    app.logger.info("fetching men")
    scrape_deals(men_url, men_deals_collection, deals_collection, max_items=100)
    app.logger.info("fetching women")
    scrape_deals(women_url, women_deals_collection,deals_collection, max_items=100)
    app.logger.info("All deals scraped and saved successfully")

scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_scrape, trigger='interval', hours=6)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())


@app.route('/get-women-deals', methods=['GET'])
def get_women_deals():
    deals = list(women_deals_collection.find({}, {'_id': 0}))
    return jsonify(deals)


@app.route('/get-men-deals', methods=['GET'])
def get_men_deals():
    deals = list(men_deals_collection.find({}, {'_id': 0}))
    return jsonify(deals)

@app.route('/get-all-deals', methods=['GET'])
def get_all_deals():
    deals = list(deals_collection.find({}, {'_id': 0}))
    return jsonify(deals)


def scrape_deals(url, collection_by_gender, collection_all, max_items=100):
    app.logger.info(f"Max item count is : {max_items}")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Remove this line during debugging
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
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

    app.logger.info(f"Starting scrape on URL: {url}")  # Log start of scraping
    scraped_items = []
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "dealsList"))
        )
        app.logger.info(f"Loaded page and found deals list for URL: {url}")

    except TimeoutException:
        app.logger.error("Failed to locate 'dealsList' within timeout. Exiting crawl")
        driver.quit()
        return scraped_items

    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        app.logger.info(f"Last height is {last_height}. Starting scrolling...")
        while len(scraped_items) < max_items:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            app.logger.info(f"New height is {new_height}.")
            if new_height == last_height:
                app.logger.info("Reached end of page, no further scrolling possible")
                break
            last_height = new_height

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            deals_list = soup.find('body').find('section', id='dealsList')
            if not deals_list:
                app.logger.warning(
                    f"'dealsList' section not found on the page. Skipping further scraping for URL: {url}")
                break

            mlist_divs = deals_list.find_all('div', class_='mlist v2', limit=max_items - len(scraped_items))
            app.logger.info(f"Found {len(mlist_divs)} deals in current batch")

            for idx, mlist in enumerate(mlist_divs):
                try:
                    # 提取 dealId
                    deal_id = mlist.get('data-dmt-d-deal-id')
                    if not deal_id:
                        app.logger.warning(f"Skipping deal {idx + 1}: 'dealId' not found")
                        continue

                    if collection_by_gender.count_documents({'dealId': deal_id}) > 0:
                        app.logger.info(f"Skipping deal {deal_id} as it already exists in the database")
                        continue

                    p_left = mlist.find('div', class_='p-left')
                    if not p_left:
                        app.logger.warning(f"Skipping deal {idx + 1}: 'p-left' div not found")
                        continue

                    shop_now_link = p_left.find('a', class_='btn-buy')
                    if shop_now_link is None or 'href' not in shop_now_link.attrs:
                        app.logger.warning(f"Skipping deal {idx + 1}: 'shop_now_link' not found or invalid")
                        continue

                    shop_now_link = shop_now_link['href']

                    try:
                        driver.get(shop_now_link)
                        final_url = driver.current_url
                    except (requests.RequestException, Exception) as e:
                        app.logger.error(f"Failed to follow redirects for {shop_now_link}: {str(e)}")
                        final_url = shop_now_link  # Fall back to shop_now_link

                    parsed_url = urllib.parse.urlparse(final_url)
                    cleaned_url = urllib.parse.urlunparse(
                        (parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

                    p_right = mlist.find('div', class_='p-right')
                    if not p_right:
                        app.logger.warning(f"Skipping deal {idx + 1}: 'p-right' div not found")
                        continue

                    title_link = p_right.find('a', class_='zoom-title')
                    if not title_link or 'href' not in title_link.attrs:
                        app.logger.warning(f"Skipping deal {idx + 1}: 'title_link' not found or invalid")
                        continue
                    title_link = title_link['href']

                    app.logger.info(f"Scraping deal details at: {title_link}")

                    try:
                        detail_response = requests.get(title_link, headers=headers, timeout=10)
                        detail_response.raise_for_status()
                        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                    except (requests.RequestException, Exception) as e:
                        app.logger.error(f"Failed to fetch details from {title_link}: {str(e)}")
                        continue  # Skip to next deal

                    title = detail_soup.find('h1', class_='title')
                    if not title:
                        app.logger.warning(f"No title found for deal: {title_link}")
                        title = "Unknown Title"
                    else:
                        title = title.get_text(strip=True)

                    subtitle = detail_soup.find('div', class_='subtitle')
                    subtitle = subtitle.get_text(strip=True) if subtitle else "No Subtitle Available"

                    details_ul = detail_soup.select_one('div.mbody .minfor ul')
                    details = []
                    expire_at = datetime.now() + timedelta(days=30)
                    app.logger.info(f"Default expire time is {expire_at} for deal: {title_link}")
                    if details_ul:
                        for li in details_ul.find_all('li'):
                            text = li.get_text(strip=True)
                            details.append(text)
                            if text.startswith('Deal ends'):
                                app.logger.info(f"Expire info is {text} for deal: {title_link}")
                                expire_at_str = extract_date_from_string(text)
                                app.logger.info(f"Expire info is {expire_at_str} for deal: {title_link}")
                                expire_at = datetime.strptime(expire_at_str, '%m/%d')
                                current_year = datetime.now().year
                                expire_at = expire_at.replace(year=current_year)
                                expire_at = expire_at.replace(tzinfo=timezone.utc)
                                app.logger.info(f"Final expire time is {expire_at} for deal: {title_link}")
                                break
                    else:
                        app.logger.warning(f"No details found for deal: {title_link}")

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

                    app.logger.debug(f"Scraped deal info: {deal_info}")
                    scraped_items.append(deal_info)

                    # Save periodically to ensure scraped data is not lost in case of crashes
                    if len(scraped_items) % 5 == 0:  # Every 5 deals
                        app.logger.info(f"Saving {len(scraped_items)} deals to the database")
                        collection_by_gender.insert_many(scraped_items)
                        collection_all.insert_many(scraped_items)
                        scraped_items.clear()  # Clear list after saving to avoid duplication

                    if len(scraped_items) >= max_items:
                        app.logger.info("Reached maximum specified items for scraping")
                        break

                except Exception as inner_e:
                    app.logger.error(f"Exception occurred while processing a deal: {str(inner_e)}", exc_info=True)

    except Exception as e:
        app.logger.error(f"Exception occurred during scraping: {str(e)}", exc_info=True)

    finally:
        driver.quit()

    if scraped_items:
        app.logger.info(f"Saving remaining {len(scraped_items)} deals to the database")
        collection_by_gender.insert_many(scraped_items)
        collection_all.insert_many(scraped_items)  # Save any remaining deals after the loop

    app.logger.info(f"Total scraped items: {len(scraped_items)}")
    return scraped_items




@app.route('/deals-by-domain-women', methods=['POST'])
def get_deals_by_domain_women():
    data = request.get_json()
    domain = data.get('domain')

    if not domain:
        return jsonify({'error': 'Domain parameter is missing'}), 400

    deals = list(women_deals_collection.find({'shop_now_link': {'$regex': domain}}, {'_id': 0}))

    if not deals:
        return jsonify({'message': 'No deals found for the specified domain'}), 404

    return jsonify(deals)


@app.route('/deals-by-domain-men', methods=['POST'])
def get_deals_by_domain_men():
    data = request.get_json()
    domain = data.get('domain')

    if not domain:
        return jsonify({'error': 'Domain parameter is missing'}), 400

    deals = list(men_deals_collection.find({'shop_now_link': {'$regex': domain}}, {'_id': 0}))

    if not deals:
        return jsonify({'message': 'No deals found for the specified domain'}), 404

    return jsonify(deals)

@app.route('/deals-by-domain', methods=['POST'])
def get_deals_by_domain():
    data = request.get_json()
    domain = data.get('domain')

    if not domain:
        return jsonify({'error': 'Domain parameter is missing'}), 400

    # Fetch women's deals
    women_deals = list(women_deals_collection.find({'shop_now_link': {'$regex': domain}}, {'_id': 0}))

    # Fetch men's deals
    men_deals = list(men_deals_collection.find({'shop_now_link': {'$regex': domain}}, {'_id': 0}))

    # Combine the lists
    combined_deals = women_deals + men_deals

    # Sort by scrape_date (newest first)
    combined_deals.sort(key=lambda x: datetime.strptime(x['scrape_date'], '%Y-%m-%d %H:%M:%S'), reverse=True)

    # Remove duplicates based on shop_now_link
    unique_deals = {}
    for deal in combined_deals:
        link = deal['shop_now_link']
        if link not in unique_deals:
            unique_deals[link] = deal

    # Return the unique deals as a list
    return jsonify(list(unique_deals.values()))

@app.route('/clean-urls', methods=['POST'])
def clean_urls():
    collections = [women_deals_collection, men_deals_collection]
    for collection in collections:
        deals = list(collection.find({}))
        for deal in deals:
            original_url = deal.get('shop_now_link', '')
            parsed_url = urllib.parse.urlparse(original_url)
            cleaned_url = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
            collection.update_one({'_id': deal['_id']}, {'$set': {'shop_now_link': cleaned_url}})
    return jsonify({'message': 'URLs cleaned successfully'}), 200

@app.route('/manual-scrape', methods=['GET'])
def manual_scrape():
    try:
        scheduled_scrape()
        return jsonify({'message': 'Scraping triggered manually and data saved successfully'}), 200
    except Exception as e:
        app.logger.error(f"Failed to scrape: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/scrape', methods=['GET'])
def test_scrape():
    url = request.args.get('url', 'https://www.dealmoon.com/en/clothing-jewelry-bags/mens-clothing')
    max_items = int(request.args.get('max_items', 20))
    deals = scrape_deals(url, men_deals_collection, deals_collection, max_items)
    clean_deals = []
    for deal in deals:
        deal['_id'] = str(deal['_id'])
        clean_deals.append(deal)

    return jsonify(clean_deals)

@app.route('/edit-deals', methods=['POST'])
def edit_deals():
    try:
        deals = list(men_deals_collection.find({}))
        for deal in deals:
            updated_details = []
            for detail in deal['details']:
                detail = re.sub(r'(?i)(code)(next|\w*)\s*((?:\w+\s*)*)',
                            lambda m: m.group(1) + ' ' + m.group(2) + ''.join(m.group(3).split()), detail)
                updated_details.append(detail)
            print(updated_details)
            men_deals_collection.update_one(
                {'_id': deal['_id']},
                {'$set': {'details': updated_details}}
            )

        return jsonify({'message': 'Deals updated successfully'}), 200
    except Exception as e:
        app.logger.error(f"Failed to edit deals: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5004)



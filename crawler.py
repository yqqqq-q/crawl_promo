import logging
import traceback
from datetime import datetime
from pymongo import MongoClient
import data_collect.retailmenot_scrape as retailmenot_scrape
from data_collect.dealmoon_scrape import get_right_info, get_bottom_info, dealmoon_scrape_links, clean_up
from config import Config
import requests
from bs4 import BeautifulSoup


# Configure logging
logging.basicConfig(
    filename='logs/crawler.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)


def main():
    logging.info("Crawler started")
    try:
        db = Config.get_database()


# #dealmoon links collection
        dealmoon_link_short_collection = db[Config.DEALMOON["link"]]

        women_cloth_link_update=dealmoon_scrape_links(file_name="womens_clothing", collection=dealmoon_link_short_collection, url="https://www.dealmoon.com/en/clothing-jewelry-bags/womens-clothing")
        logging.info(f"!Dealmoon link updated for women clothing: {women_cloth_link_update}")
        men_cloth_link_update=dealmoon_scrape_links(file_name="mens_clothing", collection=dealmoon_link_short_collection, url="https://www.dealmoon.com/en/clothing-jewelry-bags/mens-clothing")
        logging.info(f"!Dealmoon link updated for men clothing: {men_cloth_link_update}")
        women_acc_link=dealmoon_scrape_links(file_name="womens_accesories", collection=dealmoon_link_short_collection, url="https://www.dealmoon.com/en/clothing-jewelry-bags/women-watches-jewelry-accessories")
        logging.info(f"!Dealmoon link updated for women acc: {women_acc_link}")

# # # dealmoon store detail
        dealmoon_store_collection = db[Config.DEALMOON["store"]]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        stores = list(dealmoon_link_short_collection.find())
        for item in stores:
            href = item["href"]

            try:

                response = requests.get(href, headers=headers)
                print(f"getting {href}")

                soup = BeautifulSoup(response.text, "html.parser")

                right = get_right_info(soup=soup)
                right["href"] = href

                dealmoon_store_collection.update_one(
                        {"href": href},
                        {"$set": right},
                        upsert=True
                    )

            except Exception as e:
                logging.error(f"Error processing {href}: {e}")
                logging.error(traceback.format_exc())
        
        logging.info(f"!Dealmoon store updated: {len(stores)}")

        
# # dealmoon detail items
        logging.info("Detail dealmoon start crawling")
        dealmoon_item_collection = db[Config.DEALMOON["item"]]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        # for item in dealmoon_link_short_collection.find({"$or": [{"item_status": {"$exists": False}}]}):        
        for item in dealmoon_link_short_collection.find():              
            href = item["href"]
            print(href)

            try:
                response = requests.get(href, headers=headers)
                print(f"gettinging {href}")

                soup = BeautifulSoup(response.text, "html.parser")
                get_bottom_info(
                    soup=soup,
                    href=href,
                    collection=dealmoon_item_collection
                )

                # dealmoon_link_short_collection.update_one(
                #     {"href": href},
                #     {"$set": {"item_status": True, "item_last_processed": datetime.now()}}
                # )
                logging.info(f"!Dealmoon detail updated for: {href}")

            except Exception as e:
                logging.error(f"Error processing {href}: {e}")
                logging.error(traceback.format_exc())

        logging.info("Crawler completed.")

        clean_up(link=dealmoon_link_short_collection, store=dealmoon_store_collection, item=dealmoon_item_collection)
        
        
    # # retailmenot
        retailmenot_collection = db[Config.RETAILMENOT]
        # Mark all existing documents
        retailmenot_collection.update_many({}, {"$set": {"marked_for_delete": True}})
        # Run the scraper (this should insert fresh documents WITHOUT the marked flag)
        retaill_updated = retailmenot_scrape.retailmenot_scrape_deals(collection=retailmenot_collection)
        # Delete previously marked (i.e., old) documents
        retailmenot_collection.delete_many({"marked_for_delete": True})
        logging.info(f"!Retailmenot update: {retaill_updated}")
    except Exception as e:
        logging.critical(f"Fatal error: {e}")
        logging.critical(traceback.format_exc())

if __name__ == '__main__':
    main()

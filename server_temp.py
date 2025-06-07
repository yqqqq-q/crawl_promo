import os
import sys
import logging

from flask import Flask, abort, jsonify
from pymongo import MongoClient
from bson.errors import InvalidId
from bson import json_util

app = Flask(__name__)

# # Use an env var if present, otherwise fall back
# MONGO_URI = os.getenv(
#     "MONGO_URI",
#     "mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin",
# )
# mongo = MongoClient(MONGO_URI)
# db = mongo["try_database"]
# collection = db["retailmenot"]

def setup_logging(name="server"):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger(name)

logger = setup_logging("server")

@app.route("/coupon/<string:item_slug>", methods=["GET"])
def get_item(item_slug):

    # item = collection.find_one({"requestSlug": item_slug})
    # if not item:
    #     abort(404, description="Item not found")

    # return app.response_class(
    #     response=json_util.dumps(item),
    #     status=200,
    #     mimetype="application/json",
    # )
    item = None
    if not item_slug:
        abort(404, description="Not found")
    if item_slug == "walmart.com":
        item = {
        "_id": "683bbcc11de2be437cf4ebbb",
        "siteLink": "?u=QRTJNLACUVC3ZES45VDR6T4PNU&outclicked=true",
        "offerType": "COUPON",
        "requestSlug": "walmart.com",
        "store_name": "Walmart",
        "deal_description": "Eligible Customers Only! $20 Off Your Order",
        "expireAt": "unknown",
        "couponCode": "TRIPLE20"
    }
    elif item_slug == "shein.com":
        item = {
        "_id": "683bbcc11de2be437cf4ebba",
        "siteLink": "?u=VTSC23GQXVDB7KRS73ITMOTE4A&outclicked=true",
        "offerType": "COUPON",
        "requestSlug": "shein.com",
        "store_name": "SHEIN",
        "deal_description": "30% Off Sitewide",
        "expireAt": "Ends 07/08/2025",
        "couponCode": "9YKU"
    }
    else:
        abort(404, description="not in example")

    return app.response_class(
        response=json_util.dumps(item),
        status=200,
        mimetype="application/json",
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    app.run(host="0.0.0.0", port=port, debug=False)

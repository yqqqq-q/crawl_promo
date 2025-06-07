import os
import sys
import logging

from flask import Flask, abort, jsonify
from pymongo import MongoClient
from bson.errors import InvalidId
from bson import json_util

app = Flask(__name__)

# Use an env var if present, otherwise fall back
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin",
)
mongo = MongoClient(MONGO_URI)
db = mongo["try_database"]
collection = db["retailmenot"]

def setup_logging(name="server"):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger(name)

logger = setup_logging("server")

@app.route("/coupon/<string:item_slug>", methods=["GET"])
def get_item(item_slug):

    item = collection.find_one({"requestSlug": item_slug})
    if not item:
        abort(404, description="Item not found")

    return app.response_class(
        response=json_util.dumps(item),
        status=200,
        mimetype="application/json",
    )

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    app.run(host="0.0.0.0", port=port, debug=False)

import json
import logging
import re
import sys
from urllib.parse import urlparse, urlunparse

from bson.objectid import ObjectId
from firecrawl import FirecrawlApp
from flask import Flask, request, jsonify
from flask_cors import CORS
# Assuming you have an OpenAI library that supports GPT-4 Vision (this is a placeholder)
from openai import OpenAI
from pymongo import MongoClient

import rakuten_utils
from config.log_config import setup_logging
import re
import sys
import os
import http.client
import ssl
import certifi
import sqlite3

app = Flask(__name__)
CORS(app)

# MongoDB connection setup
client = MongoClient('mongodb://localhost/')  # Update with your MongoDB URI if different
db = client.brand  # Replace with your database name
links_collection = db.links
size_guides_collection = db.size_guide
# Create a new collection for storing request results
recommendations_collection = db.recommendations

# OpenAI client (this is a placeholder, ensure your OpenAI library supports this syntax)
client = OpenAI()

firecrawl = FirecrawlApp()


# coupon databse
coupon_db=client.coupon_data
retailmenot_data = coupon_db.retailmenot

@app.route("/coupon/<string:item_slug>", methods=["GET"])
def get_item(item_slug):

    item = retailmenot_data.find_one({"requestSlug": item_slug})
    if not item:
        abort(404, description="Item not found")

    return app.response_class(
        response=json_util.dumps(item),
        status=200,
        mimetype="application/json",
    )
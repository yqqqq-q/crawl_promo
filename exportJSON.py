# from pymongo import MongoClient
# import json

# # 1. Connect to MongoDB
# client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")
# db = client["try_database"]
# collection = db["retailmenot"]

# # 2. Fetch all documents
# documents = list(collection.find())

# # 3. Convert ObjectId to string (JSON can't serialize ObjectId)
# for doc in documents:
#     doc["_id"] = str(doc["_id"])

# # 4. Export to JSON file
# with open("retailmenot_clothing_shoes_accessories.json", "w", encoding="utf-8") as f:
#     json.dump(documents, f, indent=4)

import json

# Load your data (if from a file)
with open('retailmenot_clothing_shoes_accessories.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Clean couponCode fields
for item in data:
    if 'couponCode' in item:
        item['couponCode'] = item['couponCode'].strip()

# Optionally save back to a new file
with open('retailmenot_clothing_shoes_accessories.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("Cleaned couponCode fields.")
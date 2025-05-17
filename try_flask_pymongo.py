# from flask import Flask, request
# import json
# app = Flask(__name__)

# json_file={
#   "props": {
#     "pageProps": {
#       "slug": "/coupons/clothing"}}}

# @app.route('/')
# def home():
#     return json_file


# @app.route('/about/<name>')
# def about(name=None):
#     return f"This is the about page, {name}"

# # @app.route('/login', methods=['GET', 'POST'])
# # def login():
# #     if request.method == 'POST':
# #         return do_the_login()
# #     else:
# #         return show_the_login_form()

# if __name__ == '__main__':
#     app.run(debug=True)



from pymongo import MongoClient

# Replace the URI below with your MongoDB connection string
# client = MongoClient("mongodb://localhost:27417/")
client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")

# Access a specific database
db = client["try_database"]

# Access a collection
collection = db["mycollection"]

# Example operation: insert a document
collection.insert_one({"name": "Aliceeeeeeee", "age": 301})

# Example operation: find a document
result = collection.find_one({"name": "Aliceeeeeeee"})
print(result)
docker run -d --name crawl -p 27417:27017 -e MONGO_INITDB_ROOT_USERNAME=ruser1 -e MONGO_INITDB_ROOT_PASSWORD=rpassw1 -v $HOME/DOCKER/dockerMongoDB/datafiles602:/data/db mongo:latest

docker start mongodbcrawl

docker exec -it eb0b2d976406 bash
/
docker exec -it mongodbcrawl bash

mongosh -u ruser1 -p rpassw1 --authenticationDatabase admin

# mongo
show bds
use xx
show collections

> use mydatabase
> db.mycollection.find()


# pymongo
from pymongo import MongoClient

client = MongoClient("mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")

db = client["try_database"]

collection = db["mycollection"]

collection.insert_one({"name": "Aliceeeeeeee", "age": 301})

result = collection.find_one({"name": "Aliceeeeeeee"})
print(result)

# flask
from flask import Flask, request
import json
app = Flask(__name__)

json_file={
  "props": {
    "pageProps": {
      "slug": "/coupons/clothing"}}}

@app.route('/')
def home():
    return json_file


@app.route('/about/<name>')
def about(name=None):
    return f"This is the about page, {name}"

## @app.route('/login', methods=['GET', 'POST'])
## def login():
##     if request.method == 'POST':
##         return do_the_login()
##     else:
##         return show_the_login_form()



if __name__ == '__main__':
    app.run(debug=True)
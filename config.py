import os
from dotenv import load_dotenv
from pymongo import MongoClient

# 加载.env文件中的环境变量
load_dotenv()

class Config:
    """Configuration class for the application"""
    
    # # Flask settings
    PORT = int(os.getenv("PORT", 5004))
    DEBUG = os.getenv("DEBUG", "False").lower() in ['true', '1', 't']
    HOST = os.getenv("HOST", "0.0.0.0")
    
    # MongoDB settings
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    DATABASE_NAME = "deals"
    
    # Collections
    RETAILMENOT = "retailmenot"
    DEALMOON = {"link": "dealmoon_link", "store":"dealmoon_by_store", "item":"dealmoon_by_item"}

    # # MongoDB settings
    # MONGO_URI = os.getenv("MONGO_URI", "mongodb://ruser1:rpassw1@localhost:27417/?authSource=admin")
    # DATABASE_NAME = "another_database"
    
    # # Collections
    # RETAILMENOT = "retailmenot"
    # DEALMOON = {"link": "dealmoon_link", "store":"dealmoon_by_store", "item":"dealmoon_by_item"}
    
    @staticmethod
    def get_database():
        """Get MongoDB database connection"""
        client = MongoClient(Config.MONGO_URI)
        return client[Config.DATABASE_NAME] 

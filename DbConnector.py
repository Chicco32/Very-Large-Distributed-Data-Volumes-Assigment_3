from pymongo import MongoClient, version
from dotenv import load_dotenv
import os

load_dotenv()

class DbConnector:
    """
    Connects to the MongoDB server (Docker container or Ubuntu virtual machine).
    Connector needs HOST, USER and PASSWORD to connect.
    """

    def __init__(self):
        load_dotenv()
        self.DATABASE = os.getenv("DATABASE", "db_name")
        self.HOST = os.getenv("HOST", "localhost")
        self.USER = os.getenv("MONGO_INITDB_ROOT_USERNAME") or os.getenv("USER")
        self.PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD") or os.getenv("PASSWORD")
        self.PORT = os.getenv("PORT", "27017")
        if self.USER and self.PASSWORD:
            uri = "mongodb://%s:%s@%s:%s/%s?authSource=admin" % (
                self.USER, self.PASSWORD, self.HOST, self.PORT, self.DATABASE
            )
        else:
            uri = "mongodb://%s:%s/%s" % (self.HOST, self.PORT, self.DATABASE)

        # Connect to the databases
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.DATABASE]
        except Exception as e:
            print("ERROR: Failed to connect to db:", e)

        # get database information
        try:
            print("You are connected to the database:", self.db.name)
            print("-----------------------------------------------\n")
        except Exception:
            pass

    def close_connection(self):
        # close the DB connection
        self.client.close()
        print("\n-----------------------------------------------")
        print("Connection to %s-db is closed" % self.db.name)

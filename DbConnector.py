from pymongo import MongoClient, version
from dotenv import load_dotenv
import os



load_dotenv()

class DbConnector:
    """
    Connects to the MongoDB server on the Ubuntu virtual machine.
    Connector needs HOST, USER and PASSWORD to connect.

    Example:
    HOST = "tdt4225-00.idi.ntnu.no" // Your server IP address/domain name
    USER = "testuser" // This is the user you created and added privileges for
    PASSWORD = "test123" // The password you set for said user
    """

    def __init__(self):
        load_dotenv()
        self.DATABASE = os.getenv("DATABASE")
        self.HOST = os.getenv("HOST")
        self.USER = os.getenv("MONGO_INITDB_ROOT_USERNAME")
        self.PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
        self.PORT = os.getenv("PORT", "27017")
        uri = "mongodb://%s:%s@%s:%s/%s?authSource=admin" % (
            self.USER, self.PASSWORD, self.HOST, self.PORT, self.DATABASE
        )
        # Connect to the databases
        try:
            self.client = MongoClient(uri)
            self.db = self.client[self.DATABASE]
        except Exception as e:
            print("ERROR: Failed to connect to db:", e)

        # get database information
        print("You are connected to the database:", self.db.name)
        print("-----------------------------------------------\n")

    def close_connection(self):
        # close the cursor
        # close the DB connection
        self.client.close()
        print("\n-----------------------------------------------")
        print("Connection to %s-db is closed" % self.db.name)

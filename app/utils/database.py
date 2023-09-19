import os
from dotenv import load_dotenv
import datetime as dt


def get_database_uri():
    load_dotenv()
    return os.getenv("MONGO_URI")

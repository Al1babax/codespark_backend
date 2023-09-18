import os
from dotenv import load_dotenv
import datetime as dt


def get_database_uri():
    load_dotenv()
    return os.getenv("MONGO_URI")


def create_user_session(username: str, session_id: str, db):
    creation_time = dt.datetime.now()
    expire_time = creation_time + dt.timedelta(days=1)

    db.sessions.insert_one({
        "username": username,
        "session_id": session_id,
        "creation_time": creation_time,
        "expire_time": expire_time
    })

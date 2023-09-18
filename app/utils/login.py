import os
from dotenv import load_dotenv
import httpx
from uuid import uuid4
import bcrypt
import datetime as dt


def get_client_id():
    load_dotenv()
    return os.getenv("CLIENT_ID")


def get_client_secret():
    load_dotenv()
    return os.getenv("CLIENT_SECRET")


def construct_github_login_url():
    client_id = get_client_id()
    redirect_uri = "http://localhost:8000/api/oauth/github/redirect"
    scopes = ["user"]
    return f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scopes}"


async def get_access_token(code: str):
    client_id = get_client_id()
    client_secret = get_client_secret()
    url = "https://github.com/login/oauth/access_token"

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code
    }

    headers = {
        "Accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload, headers=headers)
        response_json = response.json()

    return response_json["access_token"]


def generate_uuid():
    return str(uuid4())


def check_uuid_not_taken(uuid: str, db):
    col = db["sessions"]
    return col.find_one({"uuid": uuid}) is None


def hash_session_id(session_id: str) -> bytes:
    return bcrypt.hashpw(session_id.encode(), bcrypt.gensalt())


def check_session_id(username: str, hashed_session_id: str, db) -> bool:
    """
    Check if the session id is valid by checking if the hashed session id is the same as the one in the database
    Also checks that the session id is not expired
    :param username:
    :param hashed_session_id:
    :param db:
    :return:
    """
    # Find username from session database
    col = db["sessions"]

    # If username is not found, return False
    user = col.find_one({"username": username})

    if user is None:
        return False

    session_id = user["session_id"]

    # Check if the session id is expired
    if user["expire_time"] < dt.datetime.now():
        return False

    # Check if the hashed session id is the same as the one in the database
    return bcrypt.checkpw(session_id.encode(), hashed_session_id.encode())


async def get_user_info(access_token: str):
    """
    Get user info from github using the access token
    :param access_token:
    :return:
    """
    uri = "https://api.github.com/user"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(uri, headers=headers)
        response_json = response.json()

    return response_json

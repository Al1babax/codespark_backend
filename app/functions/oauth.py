""" Currently only for github """
import httpx
import os
from dotenv import load_dotenv
from uuid import uuid4
import datetime as dt
import bcrypt


class OauthWorkflow:

    def __init__(self, db):
        self.db = db

        self.client_id = self.get_client_id()
        self.client_secret = self.get_client_secret()
        self.redirect_uri = self.get_redirect_uri()
        self.col_session = self.db["sessions"]
        self.col_users = self.db["users"]

        self.access_token = None
        self.session_id = None
        self.hashed_session_id = None
        self.username = None

        self.has_profile = False

    def construct_login_url(self):
        scopes = ["user"]
        url = f"https://github.com/login/oauth/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope={scopes}"
        return url

    async def get_access_token(self, code: str):
        url = f"https://github.com/login/oauth/access_token"

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code
        }

        headers = {
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload, headers=headers)

            if response.status_code != 200:
                return None

            response_json = response.json()

        return response_json["access_token"]

    async def get_user_info(self):
        """
        Get user info from github using the access token
        :param access_token:
        :return:
        """

        if self.access_token is None:
            return None

        uri = "https://api.github.com/user"

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(uri, headers=headers)

            if response.status_code != 200:
                return None

            response_json = response.json()

        self.username = response_json["login"]

        return response_json

    def generate_new_unique_session_id(self) -> str:
        uuid = self.generate_id()
        while self.is_session_id_taken(uuid):
            uuid = self.generate_id()
        return uuid

    def is_session_id_taken(self, uuid: str) -> bool:
        return self.col_session.find_one({"session_id": uuid}) is not None

    def has_session(self) -> bool:
        if self.username is None:
            return False

        session = self.col_session.find_one({"username": self.username})

        if session is None:
            return False

        return True

    def has_user_profile(self) -> bool:
        """
        Checks if user has profile, if not create one
        Also checks if the user profile is complete
        :return:
        """
        if self.username is None or self.username == "":
            return False

        user_profile = self.col_users.find_one({"username": self.username})

        if user_profile is None:
            self.create_user_profile()
            return True

        fields = ["email", "discord_username", "natural_languages", "background", "looking_for", "how_contribute"]

        # Check if fields are none or empty
        for field in fields:
            if user_profile[field] is None or user_profile[field] == "":
                return True

        # If user profile is complete
        self.has_profile = True
        return True

    def hash_session_id(self):
        if self.session_id is None:
            return None

        self.hashed_session_id = bcrypt.hashpw(self.session_id.encode(), bcrypt.gensalt())

        return True

    def create_user_profile(self):
        if self.username is None:
            return None

        self.col_users.insert_one({
            "username": self.username,
            "email": "",
            "discord_username": "",
            "profile_picture": "",
            "natural_languages": "",
            "background": "",
            "looking_for": "",
            "how_contribute": "",
            "created_at": dt.datetime.now(),
        })

        return True

    def create_session(self):
        if self.username is None or self.session_id is None:
            return None

        creation_time = dt.datetime.now()
        expire_time = creation_time + dt.timedelta(days=1)

        self.col_session.insert_one({
            "username": self.username,
            "session_id": self.session_id,
            "creation_time": creation_time,
            "expire_time": expire_time
        })

        return True

    def delete_user_session(self):
        if self.username is None:
            return None

        self.col_session.delete_one({"username": self.username})

        return True

    async def run(self, code: str):
        # Get access token from github
        self.access_token = await self.get_access_token(code)

        if self.access_token is None:
            return None

        # Generate an uuid for the user
        self.session_id = self.generate_new_unique_session_id()

        # Hash the session_id
        success = self.hash_session_id()
        if not success:
            return None

        # Get the user info from github
        user_info = await self.get_user_info()

        if user_info is None:
            return None

        # Check if the user has a profile, if not create one
        success = self.has_user_profile()

        if not success:
            return None

        # Check if user has a session, if they have one, delete it
        if self.has_session():
            self.delete_user_session()

        # Create new session
        success = self.create_session()

        if not success:
            return None

        # Return with package
        package = {
            "username": self.username,
            "session_id": self.hashed_session_id,
            "has_profile": str(self.has_profile)
        }

        return package

    @staticmethod
    def get_client_id():
        load_dotenv()
        return os.getenv("CLIENT_ID")

    @staticmethod
    def get_client_secret():
        load_dotenv()
        return os.getenv("CLIENT_SECRET")

    @staticmethod
    def get_redirect_uri():
        return "http://84.250.88.117:8000/init_login"

    @staticmethod
    def generate_id():
        return str(uuid4())

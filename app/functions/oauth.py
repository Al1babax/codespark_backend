""" Currently only for github """
import httpx
import os
from dotenv import load_dotenv
from uuid import uuid4
import datetime as dt
import bcrypt

# TODO: not saving session data atm, make separate colleciton to save them
# TODO: If user changes github account and has codespark account. Solve how user can access their old account!
# TODO: cronjob on host server that removes old sessions OR save for analytics


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

    def generate_new_unique_session_id(self):
        # Create session id
        session_id = f"{self.generate_id()}-{self.username}"

        # Hash the session id
        hashed_session_id = bcrypt.hashpw(session_id.encode(), bcrypt.gensalt())

        # Store the session id and hashed session id
        self.hashed_session_id = hashed_session_id
        self.session_id = session_id

    def is_session_id_taken(self, hashed_session_id: bytes) -> bool:
        return self.col_session.find_one({"hashed_session_id": hashed_session_id}) is not None

    def has_session(self) -> bool:
        if self.username is None:
            return False

        # Get user id
        user = self.col_users.find_one({"username": self.username, "active": True})
        user_id = user["_id"]

        session = self.col_session.find_one({"user_id": user_id, "active": True})

        if session is None:
            return False

        # CHeck that session has not expired
        if session["expired_at"] < dt.datetime.now():
            # Change the active to false
            self.col_session.update_one({"_id": session["_id"]},
                                        {"$set": {"active": False, "last_used": dt.datetime.now()}})
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

        user_profile = self.col_users.find_one({"username": self.username, "active": True})

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

    def create_user_profile(self):
        if self.username is None:
            return None

        current_time = dt.datetime.now()

        self.col_users.insert_one({
            "username": self.username,
            "email": "",
            "discord_username": "",
            "profile_picture": "",
            "natural_languages": "",
            "background": "",
            "looking_for": "",
            "how_contribute": "",
            "likes": [],
            "matches": [],
            "created_at": current_time,
            "updated_at": current_time,
            "last_login": current_time,
            "active": True
        })

        return True

    def create_session(self):
        if self.username is None or self.session_id is None or self.hashed_session_id is None:
            return None

        creation_time = dt.datetime.now()
        expire_time = creation_time + dt.timedelta(days=1)

        # Find user id
        user = self.col_users.find_one({"username": self.username, "active": True})
        user_id = user["_id"]

        self.col_session.insert_one({
            "user_id": user_id,
            "username": self.username,
            "hashed_session_id": self.hashed_session_id,
            "created_at": creation_time,
            "expired_at": expire_time,
            "last_used": creation_time,
            "active": True
        })

        # Update the last login time
        self.col_users.update_one({"_id": user_id}, {"$set": {"last_login": creation_time}})

        return True

    def remove_session(self):
        if self.username is None:
            return None

        # Find user id
        user = self.col_users.find_one({"username": self.username, "active": True})
        user_id = user["_id"]

        # Find all sessions for the user and delete them
        self.col_session.delete_many({"user_id": user_id})

        return True

    async def run(self, code: str):
        # Get access token from github
        self.access_token = await self.get_access_token(code)

        if self.access_token is None:
            return None

        # Get the user info from github
        user_info = await self.get_user_info()

        if user_info is None:
            return None

        # Check if the user has a profile, if not create one
        success = self.has_user_profile()

        if not success:
            return None

        # Generate an uuid for the user
        self.generate_new_unique_session_id()

        # Check if user has a session, if so remove it
        if self.has_session():
            # Remove the old session
            self.remove_session()

        success = self.create_session()

        if not success:
            return None

        # Return with package
        package = {
            "username": self.username,
            "session_id": self.session_id,
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

import bcrypt
import datetime
from fastapi import Header, HTTPException, status, Request
import pymongo

from utils import database


# TODO: handle profile pictures
# TODO: add update time to user profile


def verify_session_id(request: Request = None):
    """
    Verifies that the session id is valid ROUTE PROTECTOR
    :param request:
    :return:
    """
    client = pymongo.MongoClient(database.get_database_uri())
    db = client["codespark"]

    # Check if the request is None
    if request is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No request provided")

    # Get the username and session id
    username = request.headers.get("username")
    session_id = request.headers.get("session_id")

    # Check if the username is None
    if username is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No username provided")

    # Check if the session id is None
    if session_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No session id provided")

    # Check if the session id is valid and has not expired
    col = db["sessions"]

    user = col.find_one({"username": username})

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session id")

    # Make sure the session id is not expired
    if user["expired_at"] < datetime.datetime.now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session id expired")

    # Use bcrypt to compare the session id
    if bcrypt.checkpw(user["session_id"].encode(), session_id.encode()):
        return username, session_id


class UserManagement:

    def __init__(self, db):
        self.db = db

        self.col_users = self.db["users"]
        self.col_sessions = self.db["sessions"]

    def update_user_profile(self, username: str, data: dict) -> bool:
        """
        Updates the user profile
        :param username:
        :param data:
        :return:
        """

        # Check if the data is None
        if data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No data provided")

        # Find the user
        user_data = self.col_users.find_one({"username": username})

        # Check if the user is None
        if user_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Loop over all the fields in the data
        for field in user_data:
            # Skip fields that never update
            if field in ["username", "_id", "created_at"]:
                continue

            # Skip profile_picture too
            if field == "profile_picture":
                continue

            # Check if the field is in the data
            if field in data:
                # Update the field
                user_data[field] = data[field]

        # Update the user
        self.col_users.update_one({"username": username}, {"$set": user_data})

        return True

    def get_user_profile(self, username: str) -> dict:
        """
        Gets the user profile
        :param username:
        :return:
        """

        # Check if the username is None
        if username is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No username provided")

        # Find the user
        user_data = self.col_users.find_one({"username": username})

        # Check if the user is None
        if user_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Fields to to deliver
        schema = ["username", "email", "discord_username", "profile_picture", "natural_languages", "background",
                  "looking_for", "how_contribute"]

        # Create the user data
        user_data = {field: user_data[field] for field in schema}

        return user_data

    def get_matches_view(self, username: str, match_username: str) -> dict:
        """
        Gets the user profile
        :param username:
        :param match_username:
        :return:
        """

        # Check if the username is None
        if username is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No username provided")

        # Find the user
        user_data = self.col_users.find_one({"username": username})

        # Find the match user
        matched_user = self.col_users.find_one({"username": match_username})

        # Check if the user is None
        if user_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Fields to to deliver
        schema = ["username", "profile_picture", "background"]

        # Create the user data
        user_data = {field: user_data[field] for field in schema}

        return user_data

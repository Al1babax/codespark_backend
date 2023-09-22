import bcrypt
import datetime as dt
from fastapi import Header, HTTPException, status, Request
import pymongo
import time
import datetime
from bson import ObjectId

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

    # Get user id
    col_users = db["users"]
    col_sessions = db["sessions"]

    user = col_users.find_one({"username": username, "active": True})
    user_id = user["_id"]
    session = col_sessions.find_one({"user_id": user_id, "active": True})

    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session id")

    # Make sure session is active
    if not session["active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is not active")

    # Make sure the session id is not expired
    if session["expired_at"] < datetime.datetime.now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session id expired")

    # Use bcrypt to compare the session id
    if not bcrypt.checkpw(session_id.encode(), session["hashed_session_id"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session id")

    # Update the session
    col_sessions.update_one({"_id": session["_id"]}, {"$set": {"last_used": datetime.datetime.now()}})


class UserManagement:

    def __init__(self, db):
        self.db = db

        self.col_users = self.db["users"]
        self.col_sessions = self.db["sessions"]
        self.col_likes = self.db["likes"]
        self.col_matches = self.db["matches"]

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
        user_data = self.col_users.find_one({"username": username, "active": True})

        # Check if the user is None
        if user_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Loop over all the fields in the data
        for field in user_data:
            # Skip fields that never update
            if field in ["username", "_id", "created_at", "updated_at", "active", "last_login", "likes", "matches"]:
                continue

            # Skip profile_picture too
            if field == "profile_picture":
                continue

            # Check if the field is in the data
            if field in data:
                # Update the field
                user_data[field] = data[field]

        # New update time
        user_data["updated_at"] = datetime.datetime.now()

        # Update the user
        self.col_users.update_one({"_id": user_data["_id"]}, {"$set": user_data})

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
        user_data = self.col_users.find_one({"username": username, "active": True})

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

    def delete_user(self, username: str):
        """
        Deletes the user account aka puts the active status to false and session status to false
        :param username:
        :return:
        """

        # Check if the username is None
        if username is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No username provided")

        # Find the user
        user_data = self.col_users.find_one({"username": username, "active": True})

        # Check if the user is None
        if user_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Update the user
        self.col_users.update_one({"username": username},
                                  {"$set": {"active": False, "updated_at": datetime.datetime.now()}})

        # Update the session
        self.col_sessions.update_one({"username": username},
                                     {"$set": {"active": False, "last_used": datetime.datetime.now()}})

        return True

    def like(self, user1, user2) -> bool:
        """
        User 1 likes user 2
        0. Add like to user 1
        1. Check if user 1 has liked user 2 before --> Do nothing
        2. Check if user 2 has liked user 1 before --> Create match, remove likes from both users
        :param user1:
        :param user2:
        :return:
        """
        # Get users
        user1_data = self.col_users.find_one({"username": user1, "active": True})
        user2_data = self.col_users.find_one({"username": user2, "active": True})

        # get user ids
        user1_id = user1_data["_id"]
        user2_id = user2_data["_id"]

        # Check if the users are None
        if user1_data is None or user2_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Check if user 1 has liked user 2 before
        query = self.col_likes.find_one({"user_id": user1_id, "liked_user_id": user2_id, "active": True})

        if query is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has already liked this user")

        # Check if user 2 has liked user 1 before
        query = self.col_likes.find_one({"user_id": user2_id, "liked_user_id": user1_id, "active": True})

        # If this query is not None, then create a match
        if query is not None:
            # Create match
            self.col_matches.insert_one({
                "user1_id": user1_id,
                "user2_id": user2_id,
                "created_at": datetime.datetime.now(),
                "active": True
            })

        # Final case, user 1 has not liked user 2 before and user 2 has not liked user 1 before
        # Create like object
        self.like_user(user1, user2)

        return True

    def like_user(self, user1, user2):
        # Generate a unique custom _id
        package_id = ObjectId()

        # Check if the custom _id is already in use (unlikely but possible)
        while self.col_likes.find_one({"_id": package_id}):
            package_id = ObjectId()  # Generate a new custom _id

        # Get the user id of the user
        user1 = self.col_users.find_one({"username": user1, "active": True})
        user1_id = user1["_id"]

        # Get the user id of the liked user
        user2 = self.col_users.find_one({"username": user2, "active": True})
        user2_id = user2["_id"]

        package = {
            "_id": package_id,
            "active": True,
            "user_id": user1_id,
            "liked_user_id": user2_id,
            "created_at": dt.datetime.now(),
            "deleted_at": None
        }

        self.col_likes.insert_one(package)

        # Update the user's likes
        self.col_users.update_one({"username": user1, "active": True}, {"$push": {"likes": package_id}})

        # Update the liked user's likes
        self.col_users.update_one({"username": user2, "active": True}, {"$push": {"likes": package_id}})

    def create_match(self, user1_id, user2_id):
        """
        1. Make sure both users like each other
        2. Deactivate like objects in like collection (like ids can stay under user profile to link users to deactivated likes)
        3. Create match object in match collection
        4. Add match id to both users
        :param user1_id:
        :param user2_id:
        :return:
        """
        # Generate a unique custom _id
        package_id = ObjectId()

        # Check if the custom _id is already in use (unlikely but possible)
        while self.col_matches.find_one({"_id": package_id}):
            package_id = ObjectId()  # Generate a new custom _id

        # Check if both users like each other
        query = self.col_likes.find_one({"user_id": user1_id, "liked_user_id": user2_id, "active": True})

        if query is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User 1 does not like user 2")

        query = self.col_likes.find_one({"user_id": user2_id, "liked_user_id": user1_id, "active": True})

        if query is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User 2 does not like user 1")

        # To have exact same time for both users
        dt_object = datetime.datetime.now()

        # Deactivate like objects in like collection
        self.col_likes.update_one({"user_id": user1_id, "liked_user_id": user2_id, "active": True},
                                  {"$set": {"active": False, "deleted_at": dt_object}})

        self.col_likes.update_one({"user_id": user2_id, "liked_user_id": user1_id, "active": True},
                                  {"$set": {"active": False, "deleted_at": dt_object}})

        # Create match object in match collection
        self.col_matches.insert_one({
            "_id": package_id,
            "active": True,
            "user1_id": user1_id,
            "user2_id": user2_id,
            "created_at": datetime.datetime.now(),
            "deleted_at": None
        })

        # Add match id to both users
        self.col_users.update_one({"_id": user1_id, "active": True}, {"$push": {"matches": package_id}})
        self.col_users.update_one({"_id": user2_id, "active": True}, {"$push": {"matches": package_id}})

    def dislike(self, user1, user2) -> bool:
        """
        0. Check if users have a match --> deactivate match and Delete likes for both users
        1. Check if user 1 has liked user 2 before --> Delete like object and remove like id from both users
        :param user1:
        :param user2:
        :return:
        """
        # Get users
        user1 = self.col_users.find_one({"username": user1, "active": True})
        user2 = self.col_users.find_one({"username": user2, "active": True})

        # Get user ids
        user1_id = user1["_id"]
        user2_id = user2["_id"]

        # Check if the users are None
        if user1 is None or user2 is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Check if users have a match
        query1 = self.col_matches.find_one({"user1_id": user1_id, "user2_id": user2_id, "active": True})
        query2 = self.col_matches.find_one({"user1_id": user2_id, "user2_id": user1_id, "active": True})

        if query1 is not None or query2 is not None:
            self.delete_match(user1_id, user2_id)

        # Check if user 1 has liked user 2 before
        query = self.col_likes.find_one({"user_id": user1_id, "liked_user_id": user2_id, "active": True})

        if query is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has not liked this user")

        # Delete like object
        self.col_likes.update_one({"user_id": user1_id, "liked_user_id": user2_id, "active": True},
                                  {"$set": {"active": False, "deleted_at": datetime.datetime.now()}})

        # Remove like id from both users
        self.col_users.update_one({"_id": user1_id, "active": True}, {"$pull": {"likes": query["_id"]}})
        self.col_users.update_one({"_id": user2_id, "active": True}, {"$pull": {"likes": query["_id"]}})

        return True

    def delete_match(self, user1_id, user2_id):
        """
        1. Make sure both users have a match
        2. Deactivate match object in match collection
        3. Remove match id from both users
        :param user1_id:
        :param user2_id:
        :return:
        """
        # Check if both users have a match
        query1 = self.col_matches.find_one({"user1_id": user1_id, "user2_id": user2_id, "active": True})
        query2 = self.col_matches.find_one({"user1_id": user2_id, "user2_id": user1_id, "active": True})

        # If both queries are None, then there is no match
        if query1 is None and query2 is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Users do not have a match")

        # Deactivate match object in match collection
        if query1 is not None:
            # Deactivate match object in match collection
            self.col_matches.update_one({"user1_id": user1_id, "user2_id": user2_id, "active": True},
                                        {"$set": {"active": False, "deleted_at": datetime.datetime.now()}})

            # Remove match id from both users
            self.col_users.update_one({"_id": user1_id, "active": True}, {"$pull": {"matches": query1["_id"]}})
            self.col_users.update_one({"_id": user2_id, "active": True}, {"$pull": {"matches": query1["_id"]}})

        if query2 is not None:
            # Deactivate match object in match collection
            self.col_matches.update_one({"user1_id": user2_id, "user2_id": user1_id, "active": True},
                                        {"$set": {"active": False, "deleted_at": datetime.datetime.now()}})

            # Remove match id from both users
            self.col_users.update_one({"_id": user1_id, "active": True}, {"$pull": {"matches": query2["_id"]}})
            self.col_users.update_one({"_id": user2_id, "active": True}, {"$pull": {"matches": query2["_id"]}})

    def get_matches(self, username: str) -> list:
        pass

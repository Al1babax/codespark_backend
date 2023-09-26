import bcrypt
import datetime as dt
from fastapi import Header, HTTPException, status, Request
import pymongo
import time
import datetime
from bson import ObjectId
import os
from dotenv import load_dotenv


from utils import database


# TODO: handle profile pictures
# TODO: handle discovers into sessions, simple sorting algorithm based on time


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
        0. Make sure users are not the same
        1. Check if user 1 has liked user 2 before --> Do nothing
        2. Check if user 2 has liked user 1 before --> Create match, remove likes from both users
        3. Add like to user 1
        :param user1:
        :param user2:
        :return:
        """
        # Make sure users are not the same
        if user1 == user2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot like yourself")

        # Get users
        user1_data = self.col_users.find_one({"username": user1, "active": True})
        user2_data = self.col_users.find_one({"username": user2, "active": True})

        # Check that the users are not None
        if user1_data is None or user2_data is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # get user ids
        user1_id = user1_data["_id"]
        user2_id = user2_data["_id"]

        # Check if user 1 has liked user 2 before
        query = self.col_likes.find_one(
            {"user_id": user1_id, "liked_user_id": user2_id, "active": True, "is_like": True})

        if query is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has already liked this user")

        # Check if user 2 has liked user 1 before
        query = self.col_likes.find_one(
            {"user_id": user2_id, "liked_user_id": user1_id, "active": True, "is_like": True})

        # If this query is not None, then create a match
        if query is not None:
            # Create like
            self.like_user(user1, user2)
            # Create match
            self.create_match(user1_id, user2_id)
            return True

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
            "is_like": True,
            "user_id": user1_id,
            "liked_user_id": user2_id,
            "created_at": dt.datetime.now(),
            "deleted_at": None
        }

        self.col_likes.insert_one(package)

        # Update the user's likes
        self.col_users.update_one({"_id": user1_id, "active": True}, {"$push": {"likes": package_id}})

        # Update the liked user's likes
        self.col_users.update_one({"_id": user2_id, "active": True}, {"$push": {"likes": package_id}})

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

        # Check that both users have liked each other
        query1 = self.col_likes.find_one(
            {"user_id": user2_id, "liked_user_id": user1_id, "active": True, "is_like": True})
        query2 = self.col_likes.find_one(
            {"user_id": user1_id, "liked_user_id": user2_id, "active": True, "is_like": True})

        if query1 is None or query2 is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Users do not have a match")

        # To have exact same time for both users
        dt_object = datetime.datetime.now()

        # Deactivate like objects in like collection
        self.col_likes.update_one({"user_id": user1_id, "liked_user_id": user2_id, "active": True, "is_like": True},
                                  {"$set": {"active": False, "deleted_at": dt_object}})

        self.col_likes.update_one({"user_id": user2_id, "liked_user_id": user1_id, "active": True, "is_like": True},
                                  {"$set": {"active": False, "deleted_at": dt_object}})

        # Create match object in match collection
        self.col_matches.insert_one({
            "_id": package_id,
            "active": True,
            "user_id": user1_id,
            "matched_user_id": user2_id,
            "created_at": datetime.datetime.now(),
            "deleted_at": None
        })

        # Add match id to both users
        self.col_users.update_one({"_id": user1_id, "active": True}, {"$push": {"matches": package_id}})
        self.col_users.update_one({"_id": user2_id, "active": True}, {"$push": {"matches": package_id}})

    def dislike(self, user1, user2) -> bool:
        """
        0. Check if users have a match --> deactivate match
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
        query = self.col_likes.find_one(
            {"user_id": user1_id, "liked_user_id": user2_id, "active": True, "is_like": True})

        if query is not None:
            # Deactivate like object in like collection
            self.col_likes.update_one({"user_id": user1_id, "liked_user_id": user2_id, "active": True, "is_like": True},
                                      {"$set": {"active": False, "deleted_at": datetime.datetime.now()}})

        # Create unique id
        package_id = ObjectId()

        # Check if the custom _id is already in use (unlikely but possible)
        while self.col_likes.find_one({"_id": package_id}):
            package_id = ObjectId()

        # Create dislike package
        package = {
            "_id": package_id,
            "active": True,
            "is_like": False,
            "user_id": user1_id,
            "liked_user_id": user2_id,
            "created_at": dt.datetime.now(),
            "deleted_at": None
        }

        # Insert dislike package
        self.col_likes.insert_one(package)

        # Update the user's likes
        self.col_users.update_one({"_id": user1_id, "active": True}, {"$push": {"likes": package_id}})
        self.col_users.update_one({"_id": user2_id, "active": True}, {"$push": {"likes": package_id}})

        return True

    def delete_match(self, user1_id, user2_id):
        """
        1. Make sure the match exists
        2. Deactivate match object in match collection
        :param user1_id:
        :param user2_id:
        :return:
        """
        # Check if match exists
        query1 = self.col_matches.find_one({"user_id": user1_id, "matched_user_id": user2_id, "active": True})
        query2 = self.col_matches.find_one({"user_id": user2_id, "matched_user_id": user1_id, "active": True})

        # If both queries are None, then there is no match
        if query1 is None and query2 is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Users do not have a match")

        # Deactivate match object in match collection
        if query1 is not None:
            # Deactivate match object in match collection
            self.col_matches.update_one({"_id": query1["_id"], "active": True},
                                        {"$set": {"active": False, "deleted_at": datetime.datetime.now()}})

        if query2 is not None:
            # Deactivate match object in match collection
            self.col_matches.update_one({"_id": query2["_id"], "active": True},
                                        {"$set": {"active": False, "deleted_at": datetime.datetime.now()}})

    def unmatched(self, user1, user2) -> bool:
        """
        Unmatch users
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

        # delete match
        self.delete_match(user1_id, user2_id)

        return True

    def get_matches(self, username: str) -> list:
        """
        1. Get all matches by id
        2. Get user info for each match
        :param username:
        :return:
        """
        # Get user
        user = self.col_users.find_one({"username": username, "active": True})

        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Get user id
        user_id = user["_id"]

        # Get all matches by id
        matches = user["matches"]

        # Get user info for each match
        matches_info = []

        for match_id in matches:
            matched_user_info = self.get_user_info_matches(user_id, match_id)

            # Check that the matched user is not empty
            if matched_user_info != {}:
                matches_info.append(matched_user_info)

        return matches_info

    def get_user_info_matches(self, user_id: ObjectId, match_id: ObjectId) -> dict:
        """
        Use user_id to know which one is the user and which one is the match
        Get basic information about the matched user
        :param user_id:
        :param match_id:
        :return:
        """
        # Get match
        match = self.col_matches.find_one({"_id": match_id, "active": True})

        # Check if the match is None
        if match is None:
            return {}

        # Get user2 id from the match
        user2_id = match["user_id"] if match["user_id"] != user_id else match["matched_user_id"]

        # Get user2
        user2 = self.col_users.find_one({"_id": user2_id, "active": True})

        # Make sure the user2 is not None, if so then skip
        if user2 is None:
            return {}

        # Schema to deliver of user 2
        schema = ["username", "email", "discord_username", "profile_picture", "natural_languages", "background",
                  "looking_for", "how_contribute"]

        user2_info = {field: user2[field] for field in schema}

        return user2_info

    def get_likes(self, user) -> dict:
        """
        1. Get all likes by id
        2. Get user info for each like
        :param user:
        :return:
        """
        # Get user
        user = self.col_users.find_one({"username": user, "active": True})

        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Get user id
        user_id = user["_id"]

        # Get all likes by id
        likes = user["likes"]

        # List of all users that the user has liked
        user_liked = []

        # List of all users that have liked the user
        liked_user = []

        # Get users that the user has liked
        for like_id in likes:
            user_info, user_liked_flag, liked_user_flag = self.get_user_info_likes(user_id, like_id)

            # Check that the liked user is not empty, then append
            if user_info != {} and user_liked_flag is True:
                user_liked.append(user_info)

            # Check that the liked user is not empty, then append
            if user_info != {} and liked_user_flag is True:
                liked_user.append(user_info)

        # Combine the two lists into dict
        likes_info = {
            "user_liked": user_liked,
            "liked_user": liked_user
        }

        return likes_info

    def get_dislikes(self, user) -> dict:
        """
        1. Get all likes by id
        2. Get user info for each like
        :param user:
        :return:
        """
        # Get user
        user = self.col_users.find_one({"username": user, "active": True})

        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Get user id
        user_id = user["_id"]

        # Get all likes by id
        likes = user["likes"]

        # List of all users that the user has liked
        user_disliked = []

        # List of all users that have liked the user
        disliked_user = []

        # Get users that the user has liked
        for like_id in likes:
            user_info, user_disliked_flag, disliked_user_flag = self.get_user_info_likes(user_id, like_id, False)

            # Check that the liked user is not empty, then append
            if user_info != {} and user_disliked_flag is True:
                user_disliked.append(user_info)

            # Check that the liked user is not empty, then append
            if user_info != {} and disliked_user_flag is True:
                disliked_user.append(user_info)

        # Combine the two lists into dict
        dislikes_info = {
            "user_disliked": user_disliked,
            "disliked_user": disliked_user
        }

        return dislikes_info

    def get_user_info_likes(self, user_id: ObjectId, like_id: ObjectId, is_like: bool = True):
        """
        Use user_id to know which one is the user and which one is the liked user
        Get basic information about the liked user
        :param user_id:
        :param like_id:
        :param is_like:
        :return:
        """
        # Init flags
        user_liked_flag = False
        liked_user_flag = False

        # Get like, Also make sure the like is active
        like = self.col_likes.find_one({"_id": like_id, "active": True, "is_like": is_like})

        # Make sure the like is not None
        if like is None:
            return {}, user_liked_flag, liked_user_flag

        # Check if the user is the user that liked the other user
        if like["user_id"] == user_id:
            user_liked_flag = True
        else:
            liked_user_flag = True

        # Get liked user id from the like
        liked_user_id = like["liked_user_id"] if user_liked_flag else like["user_id"]

        # Get liked user
        liked_user = self.col_users.find_one({"_id": liked_user_id, "active": True})

        # Make sure the liked user is not None, if so then skip
        if liked_user is None:
            return {}, user_liked_flag, liked_user_flag

        # Schema to deliver of liked user
        schema = ["username", "profile_picture", "natural_languages", "background",
                  "looking_for", "how_contribute"]

        liked_user_info = {field: liked_user[field] for field in schema}

        return liked_user_info, user_liked_flag, liked_user_flag

    def get_discover_users(self, username: str) -> list:
        """
        Gets up to 100 users that the user has not liked or disliked or matched
        Then sort them by last_login
        :return:
        """
        # Get user
        user = self.col_users.find_one({"username": username, "active": True})

        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

        # Get user id
        user_id = user["_id"]

        # Get all likes by id
        likes = user["likes"]

        # Get all matches by id
        matches = user["matches"]

        # Get all users
        users = self.col_users.find({"active": True})

        # List of all users that the user has liked
        user_liked = self.get_likes(username)["user_liked"]

        # List of all users that have liked the user
        liked_user = self.get_likes(username)["liked_user"]

        # List of all users that the user has matched
        user_matched = self.get_matches(username)

        # List of all users that the user has disliked
        user_disliked = self.get_dislikes(username)["user_disliked"]

        # List of all users that have disliked the user
        disliked_user = self.get_dislikes(username)["disliked_user"]

        # Check if the user has liked or matched or disliked anyone
        if len(likes) == 0 and len(matches) == 0:
            users = list(users)[:100]
            # Sort users by last_login
            users = sorted(users, key=lambda x: x["last_login"], reverse=True)
            return users

        # List of all usernames to exclude, start with the user's username
        exclude = [username]

        # Add all users that the user has liked to exclude
        for user in user_liked:
            exclude.append(user["username"])

        # Add all users that have liked the user to exclude
        for user in liked_user:
            exclude.append(user["username"])

        # Add all users that the user has matched to exclude
        for user in user_matched:
            exclude.append(user["username"])

        # Add all users that the user has disliked to exclude
        for user in user_disliked:
            exclude.append(user["username"])

        # Add all users that have disliked the user to exclude
        for user in disliked_user:
            exclude.append(user["username"])

        # Get all users that the user has not liked or disliked or matched
        users = self.col_users.find({"username": {"$nin": exclude}, "active": True})

        # Check that users is not none
        if users is None:
            return []

        users = list(users)

        # Check if the user has liked or matched or disliked anyone
        if users == 0:
            return []

        # Get up to 100 users
        users_list = users[:100]

        # Sort users by last_login datetime
        users_list = sorted(users_list, key=lambda x: x["last_login"], reverse=True)

        # Schema to deliver of user_list
        schema = ["username", "profile_picture", "natural_languages", "background",
                  "looking_for", "how_contribute"]

        # Create the user data
        users_list = [{field: user[field] for field in schema} for user in users_list]

        return users_list


def reset_database(user_management: UserManagement):
    """
    1. Empty likes collection
    2. Empty matches collections
    3. Empty sessions collections
    4. Loop through every user and empty their likes and matches
    :return:
    """
    # Empty likes collection
    user_management.col_likes.delete_many({})

    # Empty matches collections
    user_management.col_matches.delete_many({})

    # Empty sessions collections
    user_management.col_sessions.delete_many({})

    # Loop through every user and empty their likes and matches
    for user in user_management.col_users.find({}):
        user_management.col_users.update_one({"_id": user["_id"]}, {"$set": {"likes": [], "matches": []}})


def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")

    client = pymongo.MongoClient(mongo_uri)
    db = client["codespark"]

    user_management = UserManagement(db)

    # Reset database
    reset_database(user_management)

    # Test get user profile
    # print(user_management.get_user_profile("Al1babax"))

    # Test like user
    user_management.like("Al1babax", "user0")
    user_management.like("Al1babax", "user5")
    user_management.like("user1", "Al1babax")
    user_management.like("user2", "Al1babax")
    user_management.like("user3", "Al1babax")

    # Test like user, approve the match
    # user_management.like("user0", "Al1babax")
    user_management.like("user5", "Al1babax")

    # Test unmatched
    # user_management.unmatched("Al1babax", "user0")
    # user_management.unmatched("user0", "Al1babax")

    # Test dislike user
    # user_management.dislike("Al1babax", "user0")
    # user_management.dislike("user5", "Al1babax")

    # Test find matches
    matches = user_management.get_matches("Al1babax")

    print("Matches:")
    for match in matches:
        # print in nice format
        for key in match.keys():
            print(key, ":", match[key])
        print("\n")

    # Test find likes
    likes = user_management.get_likes("Al1babax")

    print("You like:")
    for like in likes["user_liked"]:
        # print in nice format
        for key in like.keys():
            print(key, ":", like[key])
        print("\n")

    print("Likes you:")
    for like in likes["liked_user"]:
        # print in nice format
        for key in like.keys():
            print(key, ":", like[key])
        print("\n")

    # Test find dislikes
    dislikes = user_management.get_dislikes("Al1babax")

    print("You dislike:")
    for dislike in dislikes["user_disliked"]:
        # print in nice format
        for key in dislike.keys():
            print(key, ":", dislike[key])
        print("\n")

    print("Dislikes you:")
    for dislike in dislikes["disliked_user"]:
        # print in nice format
        for key in dislike.keys():
            print(key, ":", dislike[key])
        print("\n")

    # Test discover users
    discover_users = user_management.get_discover_users("Al1babax")

    print("Discover users:")
    for user in discover_users:
        # print in nice format
        for key in user.keys():
            print(key, ":", user[key])
        print("\n")


if __name__ == '__main__':
    main()

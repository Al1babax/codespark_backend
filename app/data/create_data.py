"""Create synthetic data for testing purposes"""

import random
import pymongo
from dotenv import load_dotenv
import os
import datetime as dt
from bson.objectid import ObjectId


def create_user(username):
    languages = ["Python", "Java", "C++", "C#", "JavaScript", "TypeScript", "HTML", "CSS", "SQL", "PHP", "Ruby", "Rust"]
    natural_languages = ["English", "Spanish", "French", "German", "Chinese", "Japanese", "Korean", "Russian", "Arabic"]
    looking_for = [
        "A partner to work on a project",
        "A partner to learn a language",
        "A partner to teach a language",
        "A partner to work on a project and learn a language",
        "A partner to work on a project and teach a language",
        "A partner to learn a language and teach a language",
    ]
    how_contribute = [
        "I can help you with your project",
        "I can teach you a language",
        "I can learn a language from you",
        "I can help you with your project and teach you a language",
    ]

    # Make natural languages string by choosing random amount of languages
    natural_languages_string = ""
    for i in range(random.randint(1, len(natural_languages))):
        natural_languages_string += natural_languages[i] + ", "

    # Make languages string by choosing random amount of languages
    languages_string = ""
    for i in range(random.randint(1, len(languages))):
        languages_string += languages[i] + ", "

    col_users.insert_one({
        "username": username,
        "email": f"{username}@gmail.com",
        "discord_username": username + f"#{random.randint(1000, 9999)}",
        "profile_picture": "",
        "natural_languages": natural_languages_string,
        "background": languages_string,
        "looking_for": looking_for[random.randint(0, len(looking_for) - 1)],
        "how_contribute": how_contribute[random.randint(0, len(how_contribute) - 1)],
        "likes": [],
        "matches": [],
        "created_at": dt.datetime.now(),
        "updated_at": dt.datetime.now(),
        "last_login": dt.datetime.now(),
        "active": True
    })


def like_user(username, liked_username):
    # Generate a unique custom _id
    package_id = ObjectId()

    # Check if the custom _id is already in use (unlikely but possible)
    while col_likes.find_one({"_id": package_id}):
        package_id = ObjectId()  # Generate a new custom _id

    # Get the user id of the user
    user = col_users.find_one({"username": username})
    user_id = user["_id"]

    # Get the user id of the liked user
    liked_user = col_users.find_one({"username": liked_username})
    liked_user_id = liked_user["_id"]

    package = {
        "_id": package_id,
        "active": True,
        "user_id": user_id,
        "liked_user_id": liked_user_id,
        "created_at": dt.datetime.now(),
        "deleted_at": None
    }

    col_likes.insert_one(package)

    # Update the user's likes
    col_users.update_one({"username": username}, {"$push": {"likes": package_id}})

    # Update the liked user's likes
    col_users.update_one({"username": liked_username}, {"$push": {"likes": package_id}})


def remove_all_likes():
    col_likes.delete_many({})
    for user in col_users.find({}):
        col_users.update_one({"username": user["username"]}, {"$set": {"likes": []}})


def remove_all_matches():
    col_matches.delete_many({})
    for user in col_users.find({}):
        col_users.update_one({"username": user["username"]}, {"$set": {"matches": []}})


def remove_all_users():
    col_users.delete_many({})


def match_user(username, matched_username):
    # Generate a unique custom _id
    package_id = ObjectId()

    # Check if the custom _id is already in use (unlikely but possible)
    while col_likes.find_one({"_id": package_id}):
        package_id = ObjectId()  # Generate a new custom _id

    # Get the user id of the user
    user = col_users.find_one({"username": username})
    user_id = user["_id"]

    # Get the user id of the matched user
    matched_user = col_users.find_one({"username": matched_username})
    matched_user_id = matched_user["_id"]

    package = {
        "_id": package_id,
        "active": True,
        "user_id": user_id,
        "matched_user_id": matched_user_id,
        "created_at": dt.datetime.now(),
        "deleted_at": None
    }

    col_matches.insert_one(package)

    # Update the user's matches
    col_users.update_one({"username": username}, {"$push": {"matches": package_id}})

    # Update the matched user's matches
    col_users.update_one({"username": matched_username}, {"$push": {"matches": package_id}})


def create_random_likes(username="Al1babax"):
    all_users = list(col_users.find({}))

    # Generate 10 likes for the user
    ten_usernames = [user["username"] for user in all_users[1:11]]

    # user likes 10 users
    for liked_username in ten_usernames:
        like_user(username, liked_username)

    # Generate next 10 likes for the user
    ten_usernames = [user["username"] for user in all_users[11:21]]

    # 10 users like the user
    for liked_username in ten_usernames:
        like_user(liked_username, username)


def create_random_matches(username="Al1babax"):
    all_users = list(col_users.find({}))

    # Generate 10 matches for the user
    ten_usernames = [user["username"] for user in all_users[30:40]]

    # user matches 10 users
    for matched_username in ten_usernames:
        match_user(username, matched_username)


def get_database_uri():
    load_dotenv()
    return os.getenv("MONGO_URI")


if __name__ == '__main__':
    client = pymongo.MongoClient(get_database_uri())
    db = client["codespark"]
    col_users = db["users"]
    col_likes = db["likes"]
    col_matches = db["matches"]

    # remove_all_matches()
    # remove_all_likes()
    # remove_all_users()
    # exit(0)

    # Generate 100 users
    for i in range(100):
        create_user(f"user{i}")

    create_random_likes()

    create_random_matches()

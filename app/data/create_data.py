"""Create synthetic data for testing purposes"""

import random
import pymongo
from dotenv import load_dotenv
import os
import datetime as dt


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
    })


def create_random_likes(username="Al1babax"):
    pass


def create_random_matches(username="Al1babax"):
    pass


def get_database_uri():
    load_dotenv()
    return os.getenv("MONGO_URI")


if __name__ == '__main__':
    client = pymongo.MongoClient(get_database_uri())
    db = client["codespark"]
    col_users = db["users"]
    col_likes = db["likes"]
    col_matches = db["matches"]

    # Generate 100 users
    for i in range(100):
        create_user(f"user{i}")

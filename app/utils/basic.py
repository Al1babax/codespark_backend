import pymongo
import bcrypt


class BasicUtils:

    def __init__(self, db):
        self.db = db

        self.col_users = self.db["users"]
        self.col_sessions = self.db["sessions"]

    def find_username(self, hashed_session_id) -> str:
        # Loop over all the sessions and find the username
        for session in self.get_all_sessions():
            if bcrypt.checkpw(hashed_session_id.encode(), session["session_id"]):
                return session["username"]

    def get_all_sessions(self):
        sessions = self.col_sessions.find({})
        return sessions



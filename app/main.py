from typing import Optional
import hmac
import uvicorn
from fastapi import FastAPI, Response, status, HTTPException, Cookie, Form, UploadFile, File, Request, Depends, Body, \
    Header
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasicCredentials, OAuth2AuthorizationCodeBearer
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import datetime as dt
import pymongo
import requests
import base64
from configparser import ConfigParser
import json

# TODO: Create functions to revoke access token and delete session
# TODO: Change all monogdb functions to use motor instead for async

# Custom utils
import utils.database as database
from functions.oauth import OauthWorkflow
from utils.basic import BasicUtils

# Custom functions
from functions.user_management import verify_session_id, UserManagement

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/", tags=["testing"])
async def root():
    return {"message": "Hello World"}


@app.get("/api/login/github", tags=["login"])
async def github_login(response: Response):
    # Create an oauth workflow
    oauth_workflow = OauthWorkflow(db)

    # Construct the login url
    uri = oauth_workflow.construct_login_url()

    # Check if the uri is None
    if uri is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    response.status_code = status.HTTP_200_OK
    return {"url": uri}


@app.get("/api/oauth/github/session_id", tags=["login"])
async def github_login_redirect(code: str, response: Response):
    # Create an oauth workflow
    oauth_workflow = OauthWorkflow(db)

    # Run workflow
    package = await oauth_workflow.run(code)

    # Check if the package is None
    if package is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return package
    response.status_code = status.HTTP_200_OK
    return package


@app.get("/init_login", tags=["login"])
async def init_login(code: str, response: Response):
    response.status_code = status.HTTP_200_OK
    print(code)


@app.post("/api/update_profile", tags=["profile"], dependencies=[Depends(verify_session_id)])
async def update_profile(response: Response, body: dict = Body(...), username: str = Header(None)):
    # Check if the body is None
    if body is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No body provided"}

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Update the user profile
    success = user_management.update_user_profile(username, body)

    # Check if the update was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "Profile updated"}


@app.get("/api/get_profile", tags=["profile"], dependencies=[Depends(verify_session_id)])
async def get_profile(response: Response, username: str = Header(None)):
    """
    Gets the users full profile
    :param response:
    :param username:
    :return:
    """
    # TODO: Make sure only the owner can access their own profile, this should be the case already

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Get the user profile
    profile = user_management.get_user_profile(username)

    # Check if the profile is None
    if profile is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the profile
    response.status_code = status.HTTP_200_OK
    return profile


@app.get("/api/get_matches_view", tags=["profile"], dependencies=[Depends(verify_session_id)])
async def get_matches_view(response: Response, match_username: str, username: str = Header(None)):
    """
    Gets limited view of the user profile
    :param response:
    :param username:
    :param match_username:
    :return:
    """
    # TODO: finish this

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Get the user profile
    profile_view = user_management.get_matches_view(username, match_username)

    # Check if the profile is None
    if profile_view is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the profile
    response.status_code = status.HTTP_200_OK
    return profile_view


@app.get("/api/get_likes_view", tags=["profile"], dependencies=[Depends(verify_session_id)])
async def get_likes_view(response: Response, username: str = Header(None)):
    """
    Gets limited view of the user profile
    :param response:
    :param username:
    :return:
    """
    # TODO: finish this

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Get the user profile
    profile_view = user_management.get_likes_view(username)

    # Check if the profile is None
    if profile_view is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the profile
    response.status_code = status.HTTP_200_OK
    return profile_view


@app.get("/api/get_likes", tags=["likes"], dependencies=[Depends(verify_session_id)])
async def get_likes(response: Response, username: str = Header(None)):
    """
    Gets the users likes
    :param response:
    :param username:
    :return:
    """
    # TODO: finish this

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Get the users likes
    likes = user_management.get_likes(username)

    # Check if the likes is None
    if likes is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the likes
    response.status_code = status.HTTP_200_OK
    return likes


@app.get("/api/get_matches", tags=["matches"], dependencies=[Depends(verify_session_id)])
async def get_matches(response: Response, username: str = Header(None)):
    """
    Gets the users matches
    :param response:
    :param username:
    :return:
    """
    # TODO: finish this

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Get the users matches
    matches = user_management.get_matches(username)

    # Check if the matches is None
    if matches is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the matches
    response.status_code = status.HTTP_200_OK
    return matches


@app.delete("/api/delete_user", tags=["user"], dependencies=[Depends(verify_session_id)])
async def delete_user(response: Response, username: str = Header(None)):
    """
    Deletes the user
    :param response:
    :param username:
    :return:
    """
    # raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Delete the user
    success = user_management.delete_user(username)

    # Check if to delete was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "User deleted"}


@app.get("/api/verify_session_id", tags=["user"])
async def verify_session_id(response: Response, session_id: str = Header(None), username: str = Header(None)):
    """
    Verify if session still exists and is not expired
    :param response:
    :param session_id:
    :param username:
    :return:
    """
    # Check if the session_id is None
    if session_id is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No session_id provided"}

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Verify the session_id
    success = user_management.verify_session_id(session_id, username)

    # Check if the verification was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "Session verified"}


@app.put("/api/like_user", tags=["likes"], dependencies=[Depends(verify_session_id)])
async def like_user(response: Response, liked_username: str, username: str = Header(None)):
    """
    Likes a user
    :param response:
    :param liked_username:
    :param username:
    :return:
    """
    # Check if the liked_username is None
    if liked_username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No liked_username provided"}

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Like the user
    success = user_management.like(username, liked_username)

    # Check if the like was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "User liked"}


@app.put("/api/dislike_user", tags=["likes"], dependencies=[Depends(verify_session_id)])
async def dislike_user(response: Response, liked_username: str, username: str = Header(None)):
    """
    Unlikes a user
    :param response:
    :param liked_username:
    :param username:
    :return:
    """
    # Check if the liked_username is None
    if liked_username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No liked_username provided"}

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Unlike the user
    success = user_management.dislike(username, liked_username)

    # Check if the unlike was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "User unliked"}


@app.get("/api/logout", tags=["user"], dependencies=[Depends(verify_session_id)])
async def logout(response: Response, username: str = Header(None)):
    """
    Logs the user out
    :param response:
    :param username:
    :return:
    """
    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Log the user out
    success = user_management.logout(username)

    # Check if the logout was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "Logged out"}


if __name__ == '__main__':
    client = pymongo.MongoClient(database.get_database_uri())
    db = client["codespark"]
    user_management = UserManagement(db)
    basic_utils = BasicUtils(db)
    uvicorn.run(app, host="84.250.88.117", port=8000)

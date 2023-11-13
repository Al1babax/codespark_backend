from typing import Optional
import hmac
import uvicorn
from fastapi import FastAPI, Response, status, HTTPException, Cookie, Form, UploadFile, File, Request, Depends, Body, \
    Header
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
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
from starlette.responses import HTMLResponse
from starlette import status

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

dev_server_address = "http://localhost:3000"
prod_server_address = "https://codespark-v2.vercel.app/"


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
    # Process the authentication code as needed and send back to client with a session id and username

    # Create an oauth workflow
    oauth_workflow = OauthWorkflow(db)

    # Run workflow
    package = await oauth_workflow.run(code)

    # Package contains username, session_id and has_profile boolean

    # Check if the package is None
    if package is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # If user has profile redirect to home page otherwise to create profile page
    if package["has_profile"]:
        redirect_url = f'http://localhost:3000/?username={package["username"]}&session_id={package["session_id"]}&has_profile={package["has_profile"]}'
    else:
        redirect_url = f'http://localhost:3000/create_profile?username={package["username"]}&session_id={package["session_id"]}&has_profile={package["has_profile"]}'

    # Create an HTML response with a script for redirection
    html_content = f"""
        <html>
            <head>
                <script>
                    // Redirect the user back to the React app
                    window.location.href = "{redirect_url}";
                </script>
            </head>
            <body>
                <p>Authentication successful. Redirecting...</p>
            </body>
        </html>
        """
    return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)


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


@app.post("/api/upload_profile_picture", tags=["profile"], dependencies=[Depends(verify_session_id)])
async def upload_profile_picture(response: Response, body: dict = Body(...), username: str = Header(None)):
    """
    Profile picture is encoded as a base64 string in body["image"]
    :param response:
    :param body:
    :param username:
    :return:
    """
    # Check if the body is None
    if body is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No body provided"}

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Check if the image is None
    if body["image"] is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No image provided"}

    # Decode the image
    image = base64.b64decode(body["image"])

    # Upload the image
    success = user_management.upload_profile_picture(username, image)

    # Check if the upload was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "Profile picture uploaded"}


@app.get("/api/get_profile_picture/{file_name}", tags=["profile"])
async def get_profile_picture(response: Response, file_name: str):
    """
    Gets the users profile picture
    :param response:
    :param file_name:
    :param username:
    :return:
    """
    # Check if the file_name is None
    if file_name is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No file_name provided"}

    # Get the profile picture
    profile_picture_path = user_management.get_profile_picture_path(file_name)

    # Check if the profile picture is None
    if profile_picture_path is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the profile picture
    response.status_code = status.HTTP_200_OK
    return FileResponse(profile_picture_path)


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


@app.get("/api/get_likes", tags=["likes"], dependencies=[Depends(verify_session_id)])
async def get_likes(response: Response, username: str = Header(None)):
    """
    Gets the users likes
    :param response:
    :param username:
    :return:
    """
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


@app.get("/api/get_discovers", tags=["discovers"], dependencies=[Depends(verify_session_id)])
async def get_discovers(response: Response, username: str = Header(None)):
    """
    Gets the users discovers
    :param response:
    :param username:
    :return:
    """
    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Get the users discovers
    discovers = user_management.get_discover_users(username)

    # Check if the discovers is None
    if discovers is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the discovers
    response.status_code = status.HTTP_200_OK
    return discovers


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


@app.put("/api/like_user/{liked_username}", tags=["likes"], dependencies=[Depends(verify_session_id)])
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


@app.put("/api/dislike_user/{disliked_username}", tags=["likes"], dependencies=[Depends(verify_session_id)])
async def dislike_user(response: Response, disliked_username: str, username: str = Header(None)):
    """
    Unlikes a user
    :param response:
    :param disliked_username:
    :param username:
    :return:
    """
    # Check if the liked_username is None
    if disliked_username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No liked_username provided"}

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Unlike the user
    success = user_management.dislike(username, disliked_username)

    # Check if the unlike was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "User unliked"}


@app.delete("/api/unmatch", tags=["matches"], dependencies=[Depends(verify_session_id)])
async def unmatch(response: Response, matched_username: str, username: str = Header(None)):
    """
    Unmatches a user
    :param response:
    :param matched_username:
    :param username:
    :return:
    """
    # Check if the matched_username is None
    if matched_username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No matched_username provided"}

    # Check if the username is None
    if username is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "No username provided"}

    # Unmatch the user
    success = user_management.unmatched(username, matched_username)

    # Check if the unmatch was successful
    if not success:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error"}

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "User unmatched"}


@app.get("/api/logout", tags=["user"], dependencies=[Depends(verify_session_id)])
async def logout(response: Response, username: str = Header(None)):
    """
    Logs the user out
    :param response:
    :param username:
    :return:
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")

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

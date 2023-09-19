from typing import Optional
import hmac
import hashlib
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
import bcrypt
import requests
import base64
from configparser import ConfigParser
import json

# TODO: Create functions to revoke access token and delete session

# Custom utils
import utils.database as database
from functions.oauth import OauthWorkflow

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

    user_management.update_user_profile(username, body)

    # Return the response
    response.status_code = status.HTTP_200_OK
    return {"message": "Profile updated"}


if __name__ == '__main__':
    client = pymongo.MongoClient(database.get_database_uri())
    db = client["codespark"]
    user_management = UserManagement(db)
    uvicorn.run(app, host="84.250.88.117", port=8000)

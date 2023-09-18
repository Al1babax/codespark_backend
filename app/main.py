from typing import Optional
import hmac
import hashlib
import uvicorn
from fastapi import FastAPI, Response, status, HTTPException, Cookie, Form, UploadFile, File, Request, Depends, Body, \
    Header
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasicCredentials
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

# Custom utils
import utils.login as login
import utils.database as database

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
    uri = login.construct_github_login_url()
    response.status_code = status.HTTP_200_OK
    return {"url": uri}


@app.get("/api/oauth/github/redirect", tags=["login"])
async def github_login_redirect(code: str):
    # Get access token from github
    access_token = await login.get_access_token(code)

    # If access token is None, return error
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    # Generate an uuid for the user
    uuid = login.generate_uuid()

    # Check if uuid is not taken
    while not login.check_uuid_not_taken(uuid, db):
        uuid = login.generate_uuid()

    # Hash the session_id
    hashed_session_id = login.hash_session_id(uuid)

    # Get the user info from github
    user_info = await login.get_user_info(access_token)

    username = user_info["login"]

    # Insert the user into the database
    database.create_user_session(username, uuid, db)

    # Return the session_id
    return {"username": username, "session_id": hashed_session_id}


if __name__ == '__main__':
    client = pymongo.MongoClient(database.get_database_uri())
    db = client["codespark"]
    uvicorn.run(app, host="0.0.0.0", port=8000)

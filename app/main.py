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

# TODO: modify code so that it receives a code from the frontend, and then sends a request to github to get the access token
# TODO: Create functions to revoke access token and delete session

# Custom utils
import utils.login as login
import utils.database as database
from functions.oauth import OauthWorkflow

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


@app.get("/api/oauth/github/redirect", tags=["login"])
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


if __name__ == '__main__':
    client = pymongo.MongoClient(database.get_database_uri())
    db = client["codespark"]
    uvicorn.run(app, host="0.0.0.0", port=8000)

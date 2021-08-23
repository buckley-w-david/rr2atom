from datetime import datetime

from imapclient.response_types import Envelope  # type: ignore

from pydantic import BaseModel, HttpUrl


class Story(BaseModel):
    title: str
    author_name: str
    url: HttpUrl
    description: str


class Chapter(BaseModel):
    url: HttpUrl
    title: str
    description: str
    published: datetime


class UpdateEmail(BaseModel):
    envelope: Envelope
    plaintext_content: str

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class Story(BaseModel):
    title: str
    author_name: str
    url: str
    description: str


class Chapter(BaseModel):
    url: HttpUrl
    title: str
    description: str
    published: datetime

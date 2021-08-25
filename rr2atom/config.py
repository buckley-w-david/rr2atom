from datetime import datetime
import enum
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
import toml
from datetime import datetime
import pathlib


class TomlModel(BaseModel):
    @classmethod
    def load(cls, file):
        with open(file, "r") as f:
            return cls.parse_obj(toml.load(f))

    def dump(self, file):
        with open(file, "w") as f:
            toml.dump(self.dict(), f)


class Rr2AtomConfig(TomlModel):
    username: str = ""
    password: str = ""
    host: str = ""
    folder: str = ""
    db: str = "sqlite:///rr2atom.sqlite"
    feeds_directory: str = "feeds"
    feed_base_url: HttpUrl = "https://example.com/"

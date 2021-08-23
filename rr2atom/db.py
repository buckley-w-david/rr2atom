import contextlib
from typing import Optional, Tuple

import sqlalchemy  # type: ignore
from sqlalchemy import create_engine  # type: ignore
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    MetaData,
    ForeignKey,
    Boolean,
    DateTime,
)  # type: ignore
from sqlalchemy.sql import text, select  # type: ignore

from rr2atom.models import Story, Chapter

metadata = MetaData()
stories = Table(
    "stories",
    metadata,
    Column("story_id", Integer, primary_key=True),
    Column("title", String, nullable=False),
    Column("author_name", String, nullable=False),
    Column("url", String, nullable=False),
    Column("description", String, nullable=False),
)

chapters = Table(
    "chapters",
    metadata,
    Column("chapter_id", Integer, primary_key=True),
    Column("story_id", None, ForeignKey("stories.story_id")),
    Column("url", String, nullable=False),
    Column("title", String, nullable=False),
    Column("description", String, nullable=False),
    Column("published", DateTime, nullable=False),
)


@contextlib.contextmanager
def connect(connection_string: str) -> sqlalchemy.engine.Connection:
    engine = create_engine(connection_string)
    metadata.create_all(engine)
    try:
        with engine.connect() as conn:
            yield conn
    finally:
        engine.dispose()


def add_story(conn, story: Story) -> int:
    result = conn.execute(
        stories.insert(),
        title=story.title,
        author_name=story.author_name,
        url=str(story.url),
        description=story.description,
    )
    return result.inserted_primary_key[0]


def add_chapter(conn, story_id: int, chapter: Chapter) -> int:
    result = conn.execute(
        chapters.insert(),
        story_id=story_id,
        url=str(chapter.url),
        title=chapter.title,
        description=chapter.description,
        published=chapter.published,
    )
    return result.inserted_primary_key[0]


def story_id_from_title(conn, title: str) -> Optional[Tuple[int]]:
    s = select(stories.c.story_id).where(stories.c.title == title)
    result = conn.execute(s).fetchone()
    return result[0] if result else None


def get_stories(conn):
    s = select(stories)
    return conn.execute(s).fetchall()


def get_story_chapters(conn, story_id: int):
    s = select(chapters).where(chapters.c.story_id == story_id)
    return conn.execute(s).fetchall()


# def get_scan_sources(conn):
#     query = text(
#         '''
#         SELECT sources.source_id, sources.data_type, sources.data FROM sources
#           LEFT OUTER JOIN events ON sources.source_id = events.source_id
#         WHERE NOT sources.once OR events.source_id IS NULL
#         '''
#     )
#
#     for result in conn.execute(query):
#         yield result
#
# def get_events(conn):
#     for result in conn.execute(select([events.c.url, events.c.title, events.c.description, events.c.event_date])):
#         yield Event(
#             url=result.url,
#             title=result.title,
#             description=result.description,
#             date=result.event_date
#         )

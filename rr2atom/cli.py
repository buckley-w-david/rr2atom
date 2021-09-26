from datetime import datetime, timedelta
from imaplib import IMAP4
import logging
import re
from typing import Optional, List, Protocol
from pathlib import Path
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup  # type: ignore
from imapclient import IMAPClient  # type: ignore
import typer

import opml.writer
import opml.models

from rr2atom import db
from rr2atom import email
from rr2atom.feed import generate_feed
from rr2atom.config import Rr2AtomConfig
from rr2atom.models import Chapter, Story

# Email RFC
# https://datatracker.ietf.org/doc/html/rfc3501

# TODO configurable log level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"(?P<url>https?://[^\s]+)")
AUTHOR_PATTERN = re.compile(r"(?P<author>.*) has just posted a new chapter of")
DESC_PATTERN = re.compile(r"has just posted a new chapter of (?P<title>.*) titled ")
CHAPTER_TITLE_PATTERN = re.compile(
    r"has just posted a new chapter of .* titled (?P<title>.*)"
)


def create_story(envelope, body) -> Story:
    if match := AUTHOR_PATTERN.search(body):
        author = match.group("author")
    else:
        author = "Author"

    if match := DESC_PATTERN.search(body):
        description = match.group("title")
    else:
        description = "Story Title"

    if match := URL_PATTERN.search(body):
        chapter_url = match.group("url")
        story_url = chapter_url[: chapter_url.index("/chapter")]
    else:
        story_url = "https://royalroad.com/"

    return Story(
        title=envelope.subject.decode("utf-8"),
        author_name=author,
        url=story_url,
        description=description,
    )


def create_chapter(envelope, body) -> Chapter:
    if match := CHAPTER_TITLE_PATTERN.search(body):
        title = match.group("title")
    else:
        title = "New Chapter"

    if match := URL_PATTERN.search(body):
        chapter_url = match.group("url")
    else:
        chapter_url = "https://royalroad.com"

    return Chapter(
        url=chapter_url,
        title=title,
        description=body,
        published=envelope.date,
    )


def fetch_new_chapters(db_conn, imap_client):
    for chapter_email in email.fetch_unprocessed(imap_client):
        envelope = chapter_email.envelope
        body = chapter_email.plaintext_content

        story_id = db.story_id_from_title(db_conn, envelope.subject.decode("utf-8"))
        if story_id is None:
            story = create_story(envelope, body)
            story_id = db.add_story(db_conn, story)

        chapter = create_chapter(envelope, body)
        db.add_chapter(db_conn, story_id, chapter)


def write_feeds(db_conn, feed_dir: Path, feed_base_url: str):
    # Regenerate Feeds
    opml_version = opml.models.Version.VERSION2
    opml_head = opml.models.Head()
    outlines = []
    for story_row in db.get_stories(db_conn):
        story_id = story_row.story_id
        story = Story(**story_row._mapping)
        chapters = [
            Chapter(**chapter_row._mapping)
            for chapter_row in db.get_story_chapters(db_conn, story_id)
        ]
        feed = generate_feed(story, chapters)
        feed.atom_file(f"{feed_dir / story.title}.xml")
        outlines.append(
            opml.models.Outline(
                text=story.title,
                attributes={
                    "type": "rss",
                    "xmlUrl": urljoin(feed_base_url, f"{quote(story.title)}.xml"),
                },
            )
        )

    updated_opml = opml.models.Opml(
        version=opml_version, head=opml_head, body=opml.models.Body(outlines=outlines)
    )
    opml.writer.write(str(feed_dir / "subscriptions.xml"), updated_opml)


app = typer.Typer()


@app.command()
def touch(config_file: Path = Path("rr2atom.toml")):
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config = Rr2AtomConfig()  # Creates a config structure with default values
        config.dump(config_file)


@app.command()
def update(config_file: Path = Path("rr2atom.toml")):
    touch(config_file)
    config = Rr2AtomConfig.load(config_file)

    feed_dir = Path(config.feeds_directory)
    feed_dir.mkdir(parents=True, exist_ok=True)

    with db.connect(config.db) as conn, IMAPClient(host=config.host) as client:
        client.login(config.username, config.password)
        client.select_folder(config.folder)

        fetch_new_chapters(conn, client)
        write_feeds(conn, feed_dir, config.feed_base_url)


@app.command()
def serve(config_file: Path = Path("rr2atom.toml")):
    touch(config_file)
    config = Rr2AtomConfig.load(config_file)

    feed_dir = Path(config.feeds_directory)
    feed_dir.mkdir(parents=True, exist_ok=True)

    with db.connect(config.db) as conn, IMAPClient(host=config.host) as client:
        client.login(config.username, config.password)
        client.select_folder(config.folder)

        fetch_new_chapters(conn, client)
        write_feeds(conn, feed_dir, config.feed_base_url)

        # Switch to idle mode and handle events as they come in
        while True:
            # > clients using IDLE are advised to terminate the IDLE and re-issue it at least every 29 minutes to avoid being logged off
            # https://datatracker.ietf.org/doc/html/rfc2177.html
            reset = datetime.now() + timedelta(minutes=10)
            try:
                client.idle()
                while datetime.now() < reset:
                    # Wait for up to 30 seconds for an IDLE response
                    responses = client.idle_check(timeout=30)
                    if responses and responses != [(b"OK", b"Still here")]:
                        # You're not allowed to send the server other stuff while idling
                        # FIXME: while the new messages are fetched, new incoming ones aren't discovered!
                        # This isn't too big a deal since they would be picked up at the next update
                        client.idle_done()
                        fetch_new_chapters(conn, client)
                        client.idle()

                        write_feeds(conn, feed_dir, config.feed_base_url)
            except:
                pass
            finally:
                try:
                    client.idle_done()
                except:
                    pass


if __name__ == "__main__":
    app()

import email
import logging
import re
from typing import Optional, List, Protocol
from pathlib import Path

from bs4 import BeautifulSoup
from imapclient import IMAPClient  # type: ignore
import typer

from rr2atom import db
from rr2atom.feed import generate_feed
from rr2atom.config import Rr2AtomConfig
from rr2atom.models import Chapter, Story

# TODO configurable log level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()

AUTHOR_PATTERN = re.compile(r"(?P<author>.*) has just posted a new chapter of")
URL_PATTERN = re.compile(r"(?P<url>https?://[^\s]+)")
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

    return Story(
        title=envelope.subject.decode(
            "utf-8"
        ),  # Should this be the title, or the subject?
        author_name=author,
        url="https://royalroad.com",  # Would like a better url, but we don't have it
        description=description,  # Would like a better feed description
    )


def touch(config_file: Path):
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config = Rr2RssConfig()  # Creates a config structure with default values
        config.dump(config_file)


@app.command()
def main(config_file: Path = Path("rr2atom.toml")):
    touch(config_file)
    config = Rr2AtomConfig.load(config_file)

    feed_dir = Path(config.feeds_directory)
    feed_dir.mkdir(parents=True, exist_ok=True)

    with db.connect(config.db) as conn, IMAPClient(host=config.host) as client:
        client.login(config.username, config.password)
        client.select_folder(config.folder)

        # Deal with unprocessed backlog
        messages = client.search("ALL")
        # messages = client.search(["UNSEEN", 'SUBJECT', 'New Chapter of'])
        for uid, data in client.fetch(messages, ["ENVELOPE", "RFC822"]).items():
            envelope = data[b"ENVELOPE"]
            # *sigh*
            # I would love to not bother with the html version at all
            # Originally I fetched BODY[1] instead of RFC822
            # Unfortunatly Royal Road's notification email system is a bit bugged
            # and their text/plain versions have broken chapter links
            # I really like the simplicity of the text/plain version
            # so we're hackin' the correct link in.
            email_message = email.message_from_bytes(data[b"RFC822"])
            soup = BeautifulSoup(
                email_message.get_payload(1).get_payload(), "html.parser"
            )

            body = email_message.get_payload(0).get_payload()
            chapter_url = soup.find("a", {"data-color": "Button Link"}).get("href")

            body = URL_PATTERN.sub(chapter_url, body, count=1).replace("\r", "")

            composite_story_id = db.story_id_from_title(
                conn, envelope.subject.decode("utf-8")
            )
            if composite_story_id is None:
                story = create_story(envelope, body)
                story_id = db.add_story(conn, story)
            else:
                story_id = composite_story_id[0]

            if match := CHAPTER_TITLE_PATTERN.search(body):
                title = match.group("title")
            else:
                title = "New Chapter"

            chapter = Chapter(
                url=chapter_url,
                title=title,
                description=body,
                published=envelope.date,
            )
            db.add_chapter(conn, story_id, chapter)

        # Regenerate Feeds
        for story_row in db.get_stories(conn):
            story_id = story_row.story_id
            story = Story(**story_row._mapping)
            chapters = [
                Chapter(**chapter_row._mapping)
                for chapter_row in db.get_story_chapters(conn, story_id)
            ]
            feed = generate_feed(story, chapters)
            feed.atom_file(f"{feed_dir / story.title}.xml")

        # Switch to idle mode and handle events as they come in
        # TODO Users are advised to renew the IDLE command every 10 minutes to avoid the connection from being abruptly closed.
        # try:
        #     client.idle()
        #     while True:
        #         # Wait for up to 30 seconds for an IDLE response
        #         responses = client.idle_check(timeout=30)
        #         print("Server sent:", responses if responses else "nothing")
        # finally:
        #     client.idle_done()


if __name__ == "__main__":
    app()

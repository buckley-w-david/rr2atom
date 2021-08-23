from datetime import timezone
from typing import List

from feedgen.feed import FeedGenerator  # type: ignore

from rr2atom.models import Story, Chapter


def generate_feed(story: Story, chapters: List[Chapter]) -> FeedGenerator:
    atom_feed = FeedGenerator()
    atom_feed.id(story.url)
    atom_feed.title(story.title)
    atom_feed.author(
        {
            "name": story.author_name,
        }
    )
    atom_feed.description(story.description)
    atom_feed.link(href=story.url, rel="alternate")
    atom_feed.language("en")

    for chapter in chapters:
        feed_entry = atom_feed.add_entry()

        feed_entry.id(chapter.url)
        feed_entry.title(chapter.title)
        feed_entry.description(chapter.description)
        feed_entry.link(href=chapter.url, rel="alternate")
        feed_entry.published(chapter.published.replace(tzinfo=timezone.utc))

    return atom_feed

from datetime import datetime, timedelta
import email
import re

from bs4 import BeautifulSoup  # type: ignore
from imapclient import IMAPClient  # type: ignore

from rr2atom.models import UpdateEmail

URL_PATTERN = re.compile(r"(?P<url>https?://[^\s]+)")


def fetch_unprocessed(imap_client):
    messages = imap_client.search(
        ["UNSEEN", "SUBJECT", "New Chapter of", "FROM", "noreply@royalroad.com"]
    )
    for uid, data in imap_client.fetch(messages, ["ENVELOPE", "RFC822"]).items():
        envelope = data[b"ENVELOPE"]
        # *sigh*
        # I would love to not bother with the html version at all
        # Originally I fetched BODY[1] instead of RFC822
        # Unfortunatly Royal Road's notification email system is a bit bugged
        # and their text/plain versions have broken chapter links
        # I really like the simplicity of the text/plain version
        # so we're hackin' the correct link in.
        email_message = email.message_from_bytes(data[b"RFC822"])
        soup = BeautifulSoup(email_message.get_payload(1).get_payload(), "html.parser")

        body = email_message.get_payload(0).get_payload()
        chapter_url = soup.find("a", {"data-color": "Button Link"}).get("href")

        body = URL_PATTERN.sub(chapter_url, body, count=1).replace("\r", "")
        yield UpdateEmail(envelope=envelope, plaintext_content=body)

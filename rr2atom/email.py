from datetime import datetime, timedelta
import email
import logging
import re
import urllib.request
import urllib.error

from imapclient import IMAPClient  # type: ignore

from rr2atom.models import UpdateEmail

URL_PATTERN = re.compile(r"(?P<url>https?://[^\s]+)")
TRACKING_PATTERN = re.compile(r"https://email-click.royalroad.com/\w+/\w+")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_unprocessed(imap_client):
    messages = imap_client.search(
        ["UNSEEN", "SUBJECT", "New Chapter of", "FROM", "noreply@royalroad.com"]
    )
    for uid, data in imap_client.fetch(messages, ["ENVELOPE", "RFC822"]).items():
        envelope = data[b"ENVELOPE"]
        email_message = email.message_from_bytes(data[b"RFC822"])

        body = email_message.get_payload(0).get_payload(decode=True).decode("utf-8")
        if match := URL_PATTERN.search(body):
            email_url = match.group("url")
            try:
                # While I'm at it, lets resolve the email tracking redirect
                req = urllib.request.Request(
                    email_url, data=None, headers={"User-Agent": USER_AGENT}
                )
                with urllib.request.urlopen(req) as f:
                    chapter_url = f.url

                body = URL_PATTERN.sub(chapter_url, body, count=1).replace("\r", "")
                body = TRACKING_PATTERN.sub("", body)
            except urllib.error.HTTPError as e:
                # Skip old broken update link emails
                logger.warning(e)
                continue

        yield UpdateEmail(envelope=envelope, plaintext_content=body)

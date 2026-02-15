"""
Fetch bank notification emails from Gmail via IMAP.

This script connects to Gmail using IMAP with an App Password
and retrieves unread emails from your bank for processing.
Uses Python's built-in imaplib and email modules — no external dependencies needed.
"""

import imaplib
import email
from email.header import decode_header
from typing import TypedDict
from datetime import datetime


class gmail_imap(TypedDict):
    """Windmill resource type for Gmail IMAP credentials."""
    email: str
    app_password: str


class EmailMessage(TypedDict):
    """Parsed email message structure."""
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    body_text: str
    body_html: str


def decode_mime_header(header_value: str) -> str:
    """Decode a MIME-encoded email header."""
    if not header_value:
        return ""
    decoded_parts = decode_header(header_value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="ignore"))
        else:
            result.append(part)
    return " ".join(result)


def extract_body(msg: email.message.Message) -> tuple[str, str]:
    """Extract plain text and HTML body from an email message."""
    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="ignore")

                if content_type == "text/plain":
                    body_text = decoded
                elif content_type == "text/html":
                    body_html = decoded
            except Exception:
                continue
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="ignore")
                if content_type == "text/plain":
                    body_text = decoded
                elif content_type == "text/html":
                    body_html = decoded
        except Exception:
            pass

    # If no plain text, strip HTML tags as fallback
    if not body_text and body_html:
        import re
        body_text = re.sub(r'<[^>]+>', ' ', body_html)
        body_text = re.sub(r'\s+', ' ', body_text).strip()

    return body_text, body_html


def main(
    gmail_imap_resource: gmail_imap,
    bank_sender_email: str = "",
    max_emails: int = 10,
) -> list[EmailMessage]:
    """
    Fetch unread bank notification emails from Gmail via IMAP.

    Args:
        gmail_imap_resource: Windmill gmail_imap resource with email and app_password
        bank_sender_email: Bank's sender email address (e.g., 'alerts@chase.com').
                          If empty, fetches all unread emails.
        max_emails: Maximum number of emails to fetch per run

    Returns:
        List of email messages with parsed content
    """
    user_email = gmail_imap_resource["email"]
    app_password = gmail_imap_resource["app_password"]

    # Connect to Gmail IMAP
    print(f"Connecting to Gmail IMAP as {user_email}...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(user_email, app_password)
    mail.select("INBOX")

    # Build search criteria
    if bank_sender_email:
        search_criteria = f'(UNSEEN FROM "{bank_sender_email}")'
    else:
        search_criteria = "(UNSEEN)"

    print(f"Searching with criteria: {search_criteria}")
    status, message_numbers = mail.search(None, search_criteria)

    if status != "OK" or not message_numbers[0]:
        print("No new bank emails found")
        mail.logout()
        return []

    # Get message IDs (most recent first)
    msg_ids = message_numbers[0].split()
    msg_ids = msg_ids[-max_emails:]  # Limit to max_emails (take most recent)
    msg_ids.reverse()  # Most recent first

    print(f"Found {len(msg_ids)} unread email(s)")

    emails: list[EmailMessage] = []

    for msg_id in msg_ids:
        try:
            # Fetch email without marking as read (use BODY.PEEK)
            status, msg_data = mail.fetch(msg_id, "(BODY.PEEK[])")

            if status != "OK" or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Parse headers
            subject = decode_mime_header(msg.get("Subject", ""))
            sender = decode_mime_header(msg.get("From", ""))
            date_str = msg.get("Date", "")
            message_id = msg.get("Message-ID", str(msg_id))

            # Extract body
            body_text, body_html = extract_body(msg)

            email_msg: EmailMessage = {
                "id": msg_id.decode("utf-8") if isinstance(msg_id, bytes) else str(msg_id),
                "thread_id": message_id,
                "subject": subject,
                "sender": sender,
                "date": date_str,
                "body_text": body_text,
                "body_html": body_html,
            }

            emails.append(email_msg)
            print(f"Fetched: {subject[:60]}...")

        except Exception as e:
            print(f"Error fetching email {msg_id}: {e}")
            continue

    mail.logout()
    print(f"Successfully fetched {len(emails)} email(s)")
    return emails

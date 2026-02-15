import imaplib
import email
from email.header import decode_header
from typing import TypedDict, List
import re
from html import unescape

class gmail_imap(TypedDict):
    email: str
    app_password: str

class EmailMessage(TypedDict):
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    body_text: str
    body_html: str

def decode_mime_header(header_value: str) -> str:
    """Decode MIME encoded email headers."""
    if not header_value:
        return ""
    
    decoded_parts = decode_header(header_value)
    result = []
    
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(encoding or 'utf-8', errors='ignore'))
            except (UnicodeDecodeError, LookupError, AttributeError):
                result.append(part.decode('utf-8', errors='ignore'))
        else:
            result.append(str(part))
    
    return ''.join(result)

def strip_html(html: str) -> str:
    """Basic HTML tag removal."""
    if not html:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html)
    # Decode HTML entities
    text = unescape(text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_body(msg) -> tuple:
    """Extract text and HTML body from email message."""
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
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    decoded = payload.decode(charset, errors='ignore')
                    
                    if content_type == "text/plain":
                        body_text = decoded
                    elif content_type == "text/html":
                        body_html = decoded
            except (UnicodeDecodeError, LookupError, AttributeError):
                continue
    else:
        # Not multipart
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='ignore')
                
                if msg.get_content_type() == "text/plain":
                    body_text = decoded
                elif msg.get_content_type() == "text/html":
                    body_html = decoded
        except (UnicodeDecodeError, LookupError, AttributeError):
            pass
    
    # If no text body, extract from HTML
    if not body_text and body_html:
        body_text = strip_html(body_html)
    
    return body_text, body_html

def main(
    gmail_imap_resource: gmail_imap,
    bank_sender_email: str = "",
    max_emails: int = 50
) -> List[EmailMessage]:
    """
    Fetch unread bank transaction emails via IMAP.
    
    Args:
        gmail_imap_resource: Gmail IMAP credentials (email, app_password)
        bank_sender_email: Optional filter for sender email (e.g., 'alerts@chase.com')
        max_emails: Maximum number of emails to fetch
    
    Returns:
        List of EmailMessage dictionaries
    """
    email_address = gmail_imap_resource["email"]
    app_password = gmail_imap_resource["app_password"]
    
    # Connect to Gmail IMAP
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(email_address, app_password)
    
    # Select inbox
    mail.select("INBOX")
    
    # Build search criteria
    if bank_sender_email:
        search_criteria = f'(UNSEEN FROM "{bank_sender_email}")'
    else:
        search_criteria = "(UNSEEN)"
    
    # Search for unread emails
    status, message_ids = mail.search(None, search_criteria)
    
    if status != "OK":
        mail.logout()
        return []
    
    email_ids = message_ids[0].split()
    
    # Limit to max_emails
    email_ids = email_ids[:max_emails]
    
    emails = []
    
    for email_id in email_ids:
        try:
            # Fetch email using BODY.PEEK to not mark as read
            status, msg_data = mail.fetch(email_id, "(BODY.PEEK[])")
            
            if status != "OK":
                continue
            
            # Parse email
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Extract headers
            subject = decode_mime_header(msg.get("Subject", ""))
            sender = decode_mime_header(msg.get("From", ""))
            date = msg.get("Date", "")
            message_id = msg.get("Message-ID", "")
            thread_id = msg.get("Thread-Index", "") or message_id
            
            # Extract body
            body_text, body_html = extract_body(msg)
            
            emails.append({
                "id": email_id.decode(),
                "thread_id": thread_id,
                "subject": subject,
                "sender": sender,
                "date": date,
                "body_text": body_text,
                "body_html": body_html
            })
        except Exception as e:
            # Skip problematic emails
            print(f"Error processing email {email_id}: {e}")
            continue
    
    mail.logout()
    
    return emails
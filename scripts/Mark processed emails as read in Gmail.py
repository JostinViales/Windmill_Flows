import imaplib
from typing import TypedDict, List

class gmail_imap(TypedDict):
    email: str
    app_password: str

def main(
    gmail_imap_resource: gmail_imap,
    email_ids: List[str]
) -> dict:
    """
    Mark processed emails as read in Gmail.
    
    Args:
        gmail_imap_resource: Gmail IMAP credentials
        email_ids: List of email IDs to mark as read
    
    Returns:
        Dictionary with success status and count of processed emails
    """
    if not email_ids:
        return {
            "success": True,
            "processed": 0,
            "total": 0,
            "message": "No emails to mark as read"
        }
    
    email_address = gmail_imap_resource["email"]
    app_password = gmail_imap_resource["app_password"]
    
    # Connect to Gmail IMAP
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(email_address, app_password)
    
    # Select inbox
    mail.select("INBOX")
    
    processed_count = 0
    failed_count = 0
    
    for email_id in email_ids:
        try:
            # Mark as read by adding \Seen flag
            status, _ = mail.store(email_id.encode(), '+FLAGS', '\\Seen')
            
            if status == "OK":
                processed_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"Error marking email {email_id} as read: {e}")
            failed_count += 1
    
    mail.logout()
    
    return {
        "success": True,
        "processed": processed_count,
        "failed": failed_count,
        "total": len(email_ids),
        "message": f"Marked {processed_count} of {len(email_ids)} emails as read"
    }
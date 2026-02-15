"""
Parse bank transaction emails to extract transaction details.

This script uses regex patterns to extract amount, merchant, date,
and other transaction details from bank notification emails.

Supports:
- BAC Costa Rica (Banco de América Central) - Spanish notifications
- US banks (Chase, BofA, Wells Fargo, Capital One, Citi)
- Generic fallback for other banks
"""

import re
import json
from typing import TypedDict, Optional
from datetime import datetime


class TransactionData(TypedDict):
    """Parsed transaction data structure."""
    email_id: str
    date: str
    amount: float
    merchant: str
    card_last_4: str
    transaction_type: str  # DEBIT or CREDIT
    raw_text: str
    confidence: float  # 0.0 to 1.0 confidence in parsing


class EmailMessage(TypedDict):
    """Input email message structure."""
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    body_text: str
    body_html: str


def clean_html(html: str) -> str:
    """
    Convert HTML to readable text by removing tags and cleaning up.
    Better than the basic strip used in the fetch script.
    """
    if not html:
        return ""

    # Remove style and script blocks entirely
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Replace common block elements with newlines
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<td[^>]*>', ' | ', text, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Decode common HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&apos;', "'")

    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)

    return text.strip()


def parse_bac_costa_rica(email_msg: dict) -> Optional[dict]:
    """
    Parse BAC Costa Rica bank notification emails.

    Subject format: "Notificación de transacción MERCHANT DD-MM-YYYY - HH:MM"
    Body contains: amount, card info, and transaction details in Spanish/HTML
    """
    subject = email_msg.get("subject", "")
    body_html = email_msg.get("body_html", "")
    body_text = email_msg.get("body_text", "")

    # Use HTML body as primary source (body_text often has CSS artifacts for BAC)
    clean_body = clean_html(body_html) if body_html else body_text

    # Combine all text for searching
    full_text = f"{subject}\n{clean_body}"

    print(f"  [BAC CR] Parsing: {subject[:80]}")
    print(f"  [BAC CR] Clean body length: {len(clean_body)} chars")
    print(f"  [BAC CR] Clean body preview: {clean_body[:300]}...")

    # --- Extract MERCHANT from subject ---
    # Pattern: "Notificación de transacción MERCHANT DD-MM-YYYY"
    merchant = "Unknown Merchant"
    merchant_match = re.search(
        r'[Nn]otificaci[oó]n\s+de\s+transacci[oó]n\s+(.+?)\s+\d{2}-\d{2}-\d{4}',
        subject
    )
    if merchant_match:
        merchant = merchant_match.group(1).strip()
        print(f"  [BAC CR] Merchant from subject: {merchant}")

    # --- Extract DATE from subject ---
    date_str = ""
    date_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', subject)
    if date_match:
        day, month, year = date_match.group(1), date_match.group(2), date_match.group(3)
        date_str = f"{year}-{month}-{day}"  # Convert DD-MM-YYYY to YYYY-MM-DD
        print(f"  [BAC CR] Date from subject: {date_str}")
    else:
        # Fallback to email date header
        try:
            from email.utils import parsedate_to_datetime
            parsed = parsedate_to_datetime(email_msg.get("date", ""))
            date_str = parsed.strftime("%Y-%m-%d")
        except Exception:
            date_str = datetime.now().strftime("%Y-%m-%d")

    # --- Extract AMOUNT from body ---
    # BAC CR uses various formats: ₡1,234.56 or $1,234.56 or USD 1,234.56 or CRC 1,234.56
    amount = 0.0
    amount_found = False

    # Try multiple amount patterns (most specific first)
    amount_patterns = [
        # Colones/Dollars with currency symbol: ₡1,234.56 or $1,234.56
        r'[₡$¢]\s*([0-9]{1,3}(?:[,.]?\d{3})*(?:[.,]\d{2}))',
        # With currency code: USD 1,234.56 or CRC 1,234.56
        r'(?:USD|CRC|US\$)\s*([0-9]{1,3}(?:[,.]?\d{3})*(?:[.,]\d{2}))',
        # "Monto" (amount in Spanish): Monto: 1,234.56 or Monto 1234.56
        r'[Mm]onto[:\s]+[₡$]?\s*([0-9]{1,3}(?:[,.]?\d{3})*(?:[.,]\d{2}))',
        # "Cantidad" (quantity/amount in Spanish)
        r'[Cc]antidad[:\s]+[₡$]?\s*([0-9]{1,3}(?:[,.]?\d{3})*(?:[.,]\d{2}))',
        # "Total" field
        r'[Tt]otal[:\s]+[₡$]?\s*([0-9]{1,3}(?:[,.]?\d{3})*(?:[.,]\d{2}))',
        # Generic dollar/colon amount
        r'([0-9]{1,3}(?:,\d{3})*\.\d{2})',
    ]

    for pattern in amount_patterns:
        match = re.search(pattern, full_text)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                amount = float(amount_str)
                if amount > 0:
                    amount_found = True
                    print(f"  [BAC CR] Amount found: {amount} (pattern: {pattern[:30]}...)")
                    break
            except ValueError:
                continue

    # --- Extract CARD last 4 digits ---
    card_last_four = ""
    card_patterns = [
        r'(?:tarjeta|card|ending|terminada?\s+en|xxxx)\s*[:\s]*\*{0,4}\s*(\d{4})',
        r'\*{4}(\d{4})',
        r'[Xx]{4}(\d{4})',
        r'(?:terminaci[oó]n|final)\s*[:\s]*(\d{4})',
    ]
    for pattern in card_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            card_last_four = match.group(1)
            print(f"  [BAC CR] Card last 4: {card_last_four}")
            break

    # --- Determine transaction type ---
    debit_keywords = [
        "compra", "purchase", "cargo", "débito", "debito", "retiro",
        "withdrawal", "pago", "payment", "cobro", "charge", "spent",
        "cajero", "atm"
    ]
    credit_keywords = [
        "crédito", "credito", "credit", "depósito", "deposito", "deposit",
        "abono", "reembolso", "refund", "devolución", "devolucion"
    ]

    text_lower = full_text.lower()
    debit_score = sum(1 for kw in debit_keywords if kw in text_lower)
    credit_score = sum(1 for kw in credit_keywords if kw in text_lower)
    transaction_type = "CREDIT" if credit_score > debit_score else "DEBIT"

    # --- Calculate confidence ---
    confidence = 0.0
    if merchant != "Unknown Merchant":
        confidence += 0.3
    if date_str:
        confidence += 0.2
    if amount_found:
        confidence += 0.4
    if card_last_four:
        confidence += 0.1

    return {
        "merchant": merchant,
        "date": date_str,
        "amount": amount,
        "card_last_4": card_last_four,
        "transaction_type": transaction_type,
        "confidence": confidence,
        "raw_text": full_text[:500]
    }


def parse_generic(email_msg: dict) -> Optional[dict]:
    """
    Generic email parser for US banks and unknown formats.
    """
    subject = email_msg.get("subject", "")
    body_text = email_msg.get("body_text", "")
    body_html = email_msg.get("body_html", "")

    # If body_text looks like CSS/garbage, try HTML
    if body_text and body_text.strip().startswith("@media"):
        body_text = clean_html(body_html) if body_html else ""

    full_text = f"{subject} {body_text}"

    # Amount
    amount = 0.0
    amount_match = re.search(r'\$([0-9,]+\.[0-9]{2})', full_text)
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))

    # Merchant
    merchant = "Unknown Merchant"
    merchant_patterns = [
        r'(?:at|from|to|with)\s+([A-Za-z0-9\s&\'\-\.]+?)(?:\s+on|\s+for|\s+\$|\.|,|$)',
        r'(?:merchant|comercio)[:\s]+([A-Za-z0-9\s&\'\-\.]+?)(?:\s|$)',
    ]
    for pattern in merchant_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()[:50]
            break

    # Date
    date_str = ""
    date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', full_text)
    if date_match:
        raw_date = date_match.group(1)
        for fmt in ["%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%d/%m/%Y"]:
            try:
                parsed = datetime.strptime(raw_date, fmt)
                date_str = parsed.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
    if not date_str:
        try:
            from email.utils import parsedate_to_datetime
            parsed = parsedate_to_datetime(email_msg.get("date", ""))
            date_str = parsed.strftime("%Y-%m-%d")
        except Exception:
            date_str = datetime.now().strftime("%Y-%m-%d")

    # Card last 4
    card_last_four = ""
    card_match = re.search(r'(?:ending in|card|xxxx)\s*(\d{4})', full_text, re.IGNORECASE)
    if card_match:
        card_last_four = card_match.group(1)

    # Transaction type
    text_lower = full_text.lower()
    debit_kw = ["purchase", "spent", "charge", "debit", "withdrawal", "payment"]
    credit_kw = ["credit", "deposit", "refund", "received", "cashback"]
    transaction_type = "CREDIT" if sum(1 for k in credit_kw if k in text_lower) > sum(1 for k in debit_kw if k in text_lower) else "DEBIT"

    confidence = 0.0
    if amount > 0: confidence += 0.4
    if merchant != "Unknown Merchant": confidence += 0.3
    if date_str: confidence += 0.2
    if card_last_four: confidence += 0.1

    return {
        "merchant": merchant,
        "date": date_str,
        "amount": amount,
        "card_last_4": card_last_four,
        "transaction_type": transaction_type,
        "confidence": confidence,
        "raw_text": full_text[:500]
    }


def detect_bank(sender: str) -> str:
    """Detect which bank sent the email based on sender address."""
    sender_lower = sender.lower()

    bank_map = {
        "notificacionesbaccr": "bac_cr",
        "baborigen": "bac_cr",
        "baccredomatic": "bac_cr",
        "chase.com": "chase",
        "bankofamerica": "bofa",
        "wellsfargo": "wells_fargo",
        "capitalone": "capital_one",
        "citi.com": "citi",
    }

    for pattern, bank_id in bank_map.items():
        if pattern in sender_lower:
            return bank_id

    return "generic"


def main(emails: list[EmailMessage]) -> list[TransactionData]:
    """
    Parse a list of bank emails and extract transaction data.

    Args:
        emails: List of email messages from fetch_bank_emails

    Returns:
        List of parsed transaction data
    """
    if not emails:
        print("No emails to parse")
        return []

    print(f"Parsing {len(emails)} email(s)...")
    transactions: list[TransactionData] = []

    for email_msg in emails:
        try:
            # Detect bank
            bank_id = detect_bank(email_msg.get("sender", ""))
            print(f"\nProcessing email from bank: {bank_id}")
            print(f"  Subject: {email_msg.get('subject', '')[:80]}")

            # Parse based on bank
            if bank_id == "bac_cr":
                parsed = parse_bac_costa_rica(email_msg)
            else:
                parsed = parse_generic(email_msg)

            if parsed is None:
                print(f"  SKIPPED: Could not parse email {email_msg.get('id', '?')}")
                continue

            transaction: TransactionData = {
                "email_id": email_msg.get("id", ""),
                "date": parsed["date"],
                "amount": parsed["amount"],
                "merchant": parsed["merchant"],
                "card_last_4": parsed["card_last_4"],
                "transaction_type": parsed["transaction_type"],
                "raw_text": parsed["raw_text"],
                "confidence": parsed["confidence"]
            }

            transactions.append(transaction)
            print(f"  ✓ Parsed: ${parsed['amount']:.2f} at {parsed['merchant']} on {parsed['date']} ({parsed['transaction_type']})")

        except Exception as e:
            print(f"  ERROR parsing email {email_msg.get('id', '?')}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\nTotal parsed: {len(transactions)} transaction(s)")
    return transactions
import re
import quopri
from typing import TypedDict, List, Optional

class EmailMessage(TypedDict):
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    body_text: str
    body_html: str

class TransactionData(TypedDict):
    email_id: str
    date: str
    amount: float
    currency: str
    merchant: str
    card_last_4: str
    transaction_type: str
    confidence: float
    raw_text: str

def decode_quoted_printable(text: str) -> str:
    """Decode quoted-printable encoding (e.g., =3D becomes =)."""
    try:
        # Handle quoted-printable encoding
        decoded = quopri.decodestring(text.encode('latin-1')).decode('utf-8', errors='ignore')
        return decoded
    except:
        return text

def clean_html(html: str) -> str:
    """Clean and decode HTML content."""
    if not html:
        return ""
    
    # Decode quoted-printable encoding
    html = decode_quoted_printable(html)
    
    # Remove soft line breaks (=\n)
    html = re.sub(r'=\s*\n', '', html)
    
    return html

def extract_amount(text: str, html: str = "") -> Optional[tuple]:
    """Extract amount and currency from text or HTML."""
    # Clean HTML first
    html_clean = clean_html(html)
    combined = f"{text} {html_clean}"
    
    print(f"   🔍 Searching for amount...")
    print(f"   Raw HTML sample: {html[:200]}")
    print(f"   Cleaned HTML sample: {html_clean[:200]}")
    
    # Pattern 1: Most specific - Monto: in table row with amount in next cell
    # Handles: <td><p>Monto:</p></td><td...><p>CRC 1,850.00</p></td>
    monto_patterns = [
        # Pattern for table structure with Monto label
        r'<p>\s*Monto:\s*</p>\s*</td>\s*<td[^>]*>\s*<p>\s*(CRC|USD|₡|US\$|\$)?\s*([0-9]{1,3}(?:[,\.][0-9]{3})*[,\.][0-9]{2})\s*</p>',
        # More flexible pattern
        r'Monto:\s*</p>.*?<p>\s*(CRC|USD|₡|US\$|\$)?\s*([0-9]{1,3}(?:[,\.][0-9]{3})*[,\.][0-9]{2})\s*</p>',
        # Even more flexible - just look for Monto: followed by currency and amount
        r'Monto:.*?(CRC|USD|₡|US\$|\$)\s*([0-9]{1,3}(?:[,\.][0-9]{3})*[,\.][0-9]{2})',
    ]
    
    for i, pattern in enumerate(monto_patterns):
        match = re.search(pattern, html_clean, re.IGNORECASE | re.DOTALL)
        if match:
            groups = match.groups()
            currency = groups[0] if groups[0] else 'CRC'
            amount_str = groups[1]
            
            # Normalize currency
            if currency in ['₡', 'CRC']:
                currency = 'CRC'
            elif currency in ['$', 'US$', 'USD']:
                currency = 'USD'
            
            # Parse amount
            parsed_amount = parse_amount_string(amount_str)
            if parsed_amount:
                print(f"   ✅ Found amount via Monto pattern {i+1}: {currency} {parsed_amount}")
                return float(parsed_amount), currency, 1.0
    
    # Pattern 2: Look for currency followed by amount anywhere
    currency_patterns = [
        (r'CRC\s*([0-9]{1,3}(?:[,\.][0-9]{3})*[,\.][0-9]{2})', 'CRC'),
        (r'USD\s*([0-9]{1,3}(?:[,\.][0-9]{3})*[,\.][0-9]{2})', 'USD'),
        (r'₡\s*([0-9]{1,3}(?:[,\.][0-9]{3})*[,\.][0-9]{2})', 'CRC'),
        (r'\$\s*([0-9]{1,3}(?:[,\.][0-9]{3})*[,\.][0-9]{2})', 'USD'),
    ]
    
    for pattern, curr in currency_patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            amount_str = match.group(1)
            parsed_amount = parse_amount_string(amount_str)
            if parsed_amount:
                print(f"   ✅ Found amount via currency pattern: {curr} {parsed_amount}")
                return float(parsed_amount), curr, 0.9
    
    print("   ❌ No amount pattern matched")
    return None

def parse_amount_string(amount_str: str) -> Optional[str]:
    """Parse amount string handling different decimal/thousand separators."""
    if ',' in amount_str and '.' in amount_str:
        # Both present - determine which is decimal
        if amount_str.rindex(',') > amount_str.rindex('.'):
            # Comma is last, so it's decimal (European style)
            amount_str = amount_str.replace('.', '').replace(',', '.')
        else:
            # Period is last, so it's decimal (US style)
            amount_str = amount_str.replace(',', '')
    elif ',' in amount_str:
        # Only comma - check if it's decimal or thousands
        parts = amount_str.split(',')
        if len(parts[-1]) == 2:
            # Last part is 2 digits, likely decimal
            amount_str = amount_str.replace(',', '.')
        else:
            # Likely thousands separator
            amount_str = amount_str.replace(',', '')
    
    try:
        amount = float(amount_str)
        if amount > 0:
            return amount_str
    except ValueError:
        pass
    
    return None

def extract_merchant(text: str, html: str = "", subject: str = "") -> Optional[tuple]:
    """Extract merchant name from text, HTML, or subject."""
    # Clean HTML first
    html_clean = clean_html(html)
    
    print(f"   🔍 Searching for merchant...")
    print(f"   Raw HTML sample: {html[:200]}")
    print(f"   Cleaned HTML sample: {html_clean[:200]}")
    
    # Pattern 1: Most specific - Comercio: in table row with merchant in next cell
    # Handles: <td><p>Comercio:</p></td><td...><p>CARIARI MARKET</p></td>
    comercio_patterns = [
        # Pattern for table structure with Comercio label
        r'<p>\s*Comercio:\s*</p>\s*</td>\s*<td[^>]*>\s*<p>\s*([A-ZÁÉÍÓÚÑa-záéíóúñ0-9][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s&\.\-]{2,100}?)\s*</p>',
        # More flexible pattern
        r'Comercio:\s*</p>.*?<p>\s*([A-ZÁÉÍÓÚÑa-záéíóúñ0-9][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s&\.\-]{2,100}?)\s*</p>',
        # Even more flexible - just look for Comercio: followed by merchant name
        r'Comercio:.*?<p>\s*([A-ZÁÉÍÓÚÑa-záéíóúñ0-9][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s&\.\-]{2,100}?)\s*</p>',
    ]
    
    for i, pattern in enumerate(comercio_patterns):
        match = re.search(pattern, html_clean, re.IGNORECASE | re.DOTALL)
        if match:
            merchant = match.group(1).strip()
            # Clean up merchant name
            merchant = re.sub(r'\s+', ' ', merchant)
            merchant = re.sub(r'[,\.\-<>]+$', '', merchant)
            if len(merchant) >= 3:
                print(f"   ✅ Found merchant via Comercio pattern {i+1}: {merchant}")
                return merchant, 1.0
    
    # Pattern 2: Try subject - often has merchant name
    subject_match = re.search(r'(?:transacci[oó]n|transaction)\s+(.+?)\s+\d{1,2}-\d{1,2}-\d{4}', subject, re.IGNORECASE)
    if subject_match:
        merchant = subject_match.group(1).strip()
        if len(merchant) >= 3:
            print(f"   ✅ Found merchant in subject: {merchant}")
            return merchant, 0.95
    
    # Pattern 3: General patterns
    combined = f"{text} {html_clean}"
    patterns = [
        r'(?:comercio|establecimiento)[:\s]+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s&\.\-]{2,50})(?:\s+|<|$)',
        r'(?:at|from|merchant)[:\s]+([A-Z][A-Za-z0-9\s&\.\-]{2,50})(?:\s+|<|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            merchant = re.sub(r'\s+', ' ', merchant)
            merchant = re.sub(r'[,\.\-<>]+$', '', merchant)
            merchant = re.sub(r'<[^>]+>', '', merchant)
            if len(merchant) >= 3:
                print(f"   ✅ Found merchant via general pattern: {merchant}")
                return merchant, 0.8
    
    print("   ⚠️ No merchant pattern matched")
    return None

def extract_card_last_4(text: str, html: str = "") -> Optional[tuple]:
    """Extract last 4 digits of card."""
    html = clean_html(html)
    combined = f"{text} {html}"
    
    patterns = [
        r'\*+(\d{4})',
        r'x{4,}(\d{4})',
        r'(?:MASTER|VISA|tarjeta|card).*?(\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            return match.group(1), 1.0
    
    return None

def extract_transaction_type(text: str, html: str = "") -> tuple:
    """Determine if transaction is DEBIT or CREDIT."""
    combined = f"{text} {html}".lower()
    
    debit_keywords = [
        'compra', 'purchase', 'debit', 'd[eé]bito', 'retiro', 'withdrawal', 
        'pago', 'payment', 'cargo', 'charge', 'gasto', 'spent'
    ]
    credit_keywords = [
        'cr[eé]dito', 'credit', 'dep[oó]sito', 'deposit', 'reembolso', 
        'refund', 'devoluci[oó]n', 'abono', 'payment received'
    ]
    
    for keyword in debit_keywords:
        if re.search(keyword, combined):
            return 'DEBIT', 0.9
    
    for keyword in credit_keywords:
        if re.search(keyword, combined):
            return 'CREDIT', 0.9
    
    return 'DEBIT', 0.3

def extract_date(text: str, html: str = "", email_date: str = "") -> tuple:
    """Extract transaction date from text/HTML or use email date."""
    html = clean_html(html)
    combined = f"{text} {html}"
    
    patterns = [
        r'Fecha:\s*</p>.*?<p>\s*([A-Za-z]{3}\s+\d{1,2},\s+\d{4},\s+\d{2}:\d{2})',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)\s+\d{1,2},\s+\d{4}',
        r'(\d{1,2}/\d{1,2}/\d{2,4})',
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{1,2}-\d{1,2}-\d{2,4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1), 0.8
    
    return email_date, 0.5

def parse_transaction(email: EmailMessage) -> Optional[TransactionData]:
    """Parse a single email into transaction data."""
    text = email.get('body_text', '')
    html = email.get('body_html', '')
    subject = email.get('subject', '')
    
    if not text and not html:
        print(f"⚠️ Email {email['id']}: No content found")
        return None
    
    print(f"\n📧 Parsing email {email['id']}")
    print(f"   Subject: {subject[:100]}")
    
    # Extract components
    amount_result = extract_amount(text, html)
    merchant_result = extract_merchant(text, html, subject)
    card_result = extract_card_last_4(text, html)
    transaction_type, type_confidence = extract_transaction_type(text, html)
    date_str, date_confidence = extract_date(text, html, email.get("date", ""))
    
    if not amount_result:
        print("   ❌ FAILED: No amount found")
        return None
    
    amount, currency, amount_confidence = amount_result
    print(f"   ✅ Amount: {currency} {amount}")
    
    confidence_scores = [amount_confidence, type_confidence, date_confidence]
    
    if merchant_result:
        merchant, merchant_confidence = merchant_result
        confidence_scores.append(merchant_confidence)
        print(f"   ✅ Merchant: {merchant}")
    else:
        merchant = "Unknown Merchant"
        print(f"   ⚠️ Merchant: Not found (using default)")
    
    if card_result:
        card_last_4, card_confidence = card_result
        confidence_scores.append(card_confidence)
        print(f"   ✅ Card: ****{card_last_4}")
    else:
        card_last_4 = "****"
    
    overall_confidence = sum(confidence_scores) / len(confidence_scores)
    
    transaction: TransactionData = {
        "email_id": email["id"],
        "date": date_str,
        "amount": amount,
        "currency": currency,
        "merchant": merchant,
        "card_last_4": card_last_4,
        "transaction_type": transaction_type,
        "confidence": round(overall_confidence, 2),
        "raw_text": subject[:200]
    }
    
    print(f"   ✅ SUCCESS: Parsed with confidence {transaction['confidence']}")
    
    return transaction

def main(emails: List[EmailMessage]) -> List[TransactionData]:
    """
    Parse transaction details from email bodies.
    
    Args:
        emails: List of EmailMessage dictionaries
    
    Returns:
        List of TransactionData dictionaries
    """
    print(f"🔍 Parsing {len(emails)} emails...")
    
    if not emails:
        print("⚠️ No emails to parse")
        return []
    
    transactions = []
    
    for email in emails:
        try:
            transaction = parse_transaction(email)
            if transaction:
                transactions.append(transaction)
        except Exception as e:
            print(f"❌ Error parsing email {email.get('id', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n✅ Successfully parsed {len(transactions)} transactions out of {len(emails)} emails")
    
    return transactions
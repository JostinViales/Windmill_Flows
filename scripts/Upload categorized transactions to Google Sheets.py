import requests
from typing import TypedDict, List
from datetime import datetime

class gsheets(TypedDict):
    token: str

class TransactionData(TypedDict):
    email_id: str
    date: str
    amount: float
    merchant: str
    card_last_4: str
    transaction_type: str
    confidence: float
    raw_text: str

def get_or_create_headers(token: str, spreadsheet_id: str, sheet_name: str) -> bool:
    """
    Check if headers exist, create them if not.
    
    Returns:
        True if headers were created, False if they already existed
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Get first row to check for headers
    range_name = f"{sheet_name}!A1:H1"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    # If no values or first row is empty, create headers
    if "values" not in data or not data["values"]:
        header_row = [
            "Processed Date",
            "Transaction Date",
            "Merchant",
            "Amount",
            "Type",
            "Card Last 4",
            "Confidence",
            "Description"
        ]
        
        body = {
            "values": [header_row]
        }
        
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}?valueInputOption=RAW"
        response = requests.put(url, headers=headers, json=body)
        response.raise_for_status()
        
        return True
    
    return False

def append_transactions(token: str, spreadsheet_id: str, sheet_name: str, transactions: List[TransactionData]) -> dict:
    """
    Append transactions to Google Sheets.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Prepare rows
    rows = []
    email_ids = []
    processed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for transaction in transactions:
        row = [
            processed_date,
            transaction["date"],
            transaction["merchant"],
            transaction["amount"],
            transaction["transaction_type"],
            transaction["card_last_4"],
            transaction["confidence"],
            transaction["raw_text"]
        ]
        rows.append(row)
        email_ids.append(transaction["email_id"])
    
    if not rows:
        return {
            "success": True,
            "rows_added": 0,
            "email_ids": []
        }
    
    # Append to sheet
    range_name = f"{sheet_name}!A:H"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}:append?valueInputOption=RAW"
    
    body = {
        "values": rows
    }
    
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    
    result = response.json()
    
    return {
        "success": True,
        "rows_added": len(rows),
        "email_ids": email_ids,
        "updated_range": result.get("updates", {}).get("updatedRange", "")
    }

def main(
    gsheets_resource: gsheets,
    spreadsheet_id: str,
    sheet_name: str,
    transactions: List[TransactionData]
) -> dict:
    """
    Upload transactions to Google Sheets.
    
    Args:
        gsheets_resource: Google Sheets OAuth token
        spreadsheet_id: Google Sheets spreadsheet ID
        sheet_name: Name of the sheet/tab to write to
        transactions: List of parsed transactions
    
    Returns:
        Dictionary with success status, rows added, and email IDs
    """
    token = gsheets_resource["token"]
    
    # Ensure headers exist
    headers_created = get_or_create_headers(token, spreadsheet_id, sheet_name)
    
    # Append transactions
    result = append_transactions(token, spreadsheet_id, sheet_name, transactions)
    
    result["headers_created"] = headers_created
    
    return result
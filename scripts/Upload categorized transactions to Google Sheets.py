"""
Upload categorized transactions to Google Sheets.

This script appends transaction records to a Google Sheets spreadsheet
using Windmill's Google Sheets OAuth resource.
"""

import requests
from typing import TypedDict
from datetime import datetime


class gsheets(TypedDict):
    """Windmill gsheets resource type. Class name must match the resource type."""
    token: str


class CategorizedTransaction(TypedDict):
    """Input categorized transaction structure."""
    email_id: str
    date: str
    amount: float
    merchant: str
    card_last_four: str
    transaction_type: str
    raw_description: str
    parsing_confidence: float
    category: str
    category_emoji: str
    category_confidence: float


def ensure_headers(
    api_headers: dict,
    spreadsheet_id: str,
    sheet_name: str
) -> bool:
    """
    Ensure the spreadsheet has the correct headers.
    Creates headers if the sheet is empty.
    """
    base_url = "https://sheets.googleapis.com/v4/spreadsheets"
    range_spec = f"{sheet_name}!A1:I1"

    # Check if headers exist
    response = requests.get(
        f"{base_url}/{spreadsheet_id}/values/{range_spec}",
        headers=api_headers
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("values"):
            print("Headers already exist")
            return True

    # Create headers
    header_values = [
        [
            "Processed Date",
            "Transaction Date",
            "Merchant",
            "Amount",
            "Category",
            "Type",
            "Card (Last 4)",
            "Confidence",
            "Description"
        ]
    ]

    update_response = requests.put(
        f"{base_url}/{spreadsheet_id}/values/{range_spec}",
        headers=api_headers,
        params={"valueInputOption": "USER_ENTERED"},
        json={"values": header_values}
    )

    if update_response.status_code == 200:
        print("Headers created successfully")
        return True
    else:
        print(f"Failed to create headers: {update_response.status_code} - {update_response.text}")
        return False


def main(
    gsheets_resource: gsheets,
    transactions: list,
    spreadsheet_id: str,
    sheet_name: str = "Expenses"
) -> dict:
    """
    Upload categorized transactions to Google Sheets.

    Args:
        gsheets_resource: Windmill Google Sheets OAuth resource
        transactions: List of categorized transactions to upload
        spreadsheet_id: ID of the Google Sheets spreadsheet
        sheet_name: Name of the sheet/tab within the spreadsheet

    Returns:
        Dictionary with upload results
    """
    print(f"Upload script received {len(transactions) if transactions else 0} transaction(s)")

    if not transactions:
        return {"success": True, "rows_added": 0, "message": "No transactions to upload", "email_ids": []}

    # Debug: print first transaction structure
    print(f"First transaction keys: {list(transactions[0].keys()) if isinstance(transactions[0], dict) else type(transactions[0])}")

    # Build API headers
    api_headers = {
        "Authorization": f"Bearer {gsheets_resource['token']}",
        "Content-Type": "application/json"
    }

    base_url = "https://sheets.googleapis.com/v4/spreadsheets"

    # Ensure headers exist
    print("Checking spreadsheet headers...")
    ensure_headers(api_headers, spreadsheet_id, sheet_name)

    # Prepare rows to append
    rows = []
    processed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for txn in transactions:
        try:
            # Safely access fields with defaults for resilience
            amount = txn.get("amount", 0)
            merchant = txn.get("merchant", "Unknown")
            date = txn.get("date", "")
            category = txn.get("category", "Uncategorized")
            category_emoji = txn.get("category_emoji", "❓")
            transaction_type = txn.get("transaction_type", "DEBIT")
            card_last_four = txn.get("card_last_4", txn.get("card_last_four", ""))
            raw_description = txn.get("raw_text", txn.get("raw_description", ""))

            # Safely format confidence — handle both float and string
            parsing_confidence = txn.get("confidence", txn.get("parsing_confidence", 0))
            try:
                confidence_str = f"{float(parsing_confidence):.0%}"
            except (ValueError, TypeError):
                confidence_str = str(parsing_confidence)

            row = [
                processed_time,
                str(date),
                str(merchant),
                float(amount) if amount else 0,
                f"{category_emoji} {category}",
                str(transaction_type),
                str(card_last_four),
                confidence_str,
                str(raw_description)[:100]
            ]
            rows.append(row)
            print(f"  Prepared row: ${amount} at {merchant}")

        except Exception as e:
            print(f"  Error preparing row: {e} — transaction: {txn}")
            continue

    if not rows:
        return {"success": False, "rows_added": 0, "message": "All transactions failed to prepare", "email_ids": []}

    print(f"Appending {len(rows)} row(s) to {sheet_name}...")

    # Use the :append endpoint — this is the correct Google Sheets API method
    # for adding rows. PUT/update requires exact range and can silently fail.
    append_url = f"{base_url}/{spreadsheet_id}/values/{sheet_name}!A1:I1:append"

    response = requests.post(
        append_url,
        headers=api_headers,
        params={
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS"
        },
        json={"values": rows}
    )

    print(f"Sheets API response: {response.status_code}")
    print(f"Response body: {response.text[:500]}")

    if response.status_code == 200:
        result = response.json()
        updated_range = result.get("updates", {}).get("updatedRange", "unknown")
        updated_rows = result.get("updates", {}).get("updatedRows", 0)
        print(f"Successfully appended {updated_rows} row(s) to {updated_range}")

        return {
            "success": True,
            "rows_added": len(rows),
            "message": f"Added {len(rows)} transactions to {sheet_name}",
            "email_ids": [txn.get("email_id", "") for txn in transactions]
        }
    else:
        error_msg = f"Failed to upload: {response.status_code} - {response.text}"
        print(error_msg)
        return {
            "success": False,
            "rows_added": 0,
            "message": error_msg,
            "email_ids": []
        }
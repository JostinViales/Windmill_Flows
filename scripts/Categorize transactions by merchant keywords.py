from typing import TypedDict, List

class TransactionData(TypedDict):
    email_id: str
    date: str
    amount: float
    merchant: str
    card_last_4: str
    transaction_type: str
    confidence: float
    raw_text: str

class CategorizedTransaction(TypedDict):
    email_id: str
    date: str
    amount: float
    merchant: str
    card_last_4: str
    transaction_type: str
    category: str
    category_emoji: str
    confidence: float
    raw_text: str

# Category definitions with keywords
CATEGORIES = {
    "Food & Dining": {
        "emoji": "🍽️",
        "keywords": [
            "restaurant", "cafe", "coffee", "starbucks", "mcdonald", "burger",
            "pizza", "subway", "chipotle", "panera", "dining", "food",
            "doordash", "ubereats", "grubhub", "postmates", "delivery",
            "soda", "sabrosera", "restaurante", "comida", "pollo", "asados",
            "pupuseria", "marisqueria", "panaderia", "bakery"
        ]
    },
    "Groceries": {
        "emoji": "🛒",
        "keywords": [
            "grocery", "supermarket", "walmart", "target", "costco", "safeway",
            "kroger", "whole foods", "trader joe", "aldi", "market", "food lion",
            "supermercado", "automercado", "masxmenos", "mas x menos",
            "pali", "megasuper", "pricesmart", "small world"
        ]
    },
    "Transportation": {
        "emoji": "🚗",
        "keywords": [
            "uber", "lyft", "taxi", "gas", "fuel", "shell", "chevron", "exxon",
            "bp", "parking", "transit", "metro", "train", "bus", "airline",
            "gasolinera", "gasolina", "peaje", "parqueo", "estacionamiento"
        ]
    },
    "Housing": {
        "emoji": "🏠",
        "keywords": [
            "rent", "mortgage", "property", "home depot", "lowes", "ikea",
            "furniture", "utilities", "electric", "water", "internet", "cable",
            "alquiler", "hipoteca", "kolbi", "ice", "aya", "cnfl", "jasec"
        ]
    },
    "Entertainment": {
        "emoji": "🎬",
        "keywords": [
            "netflix", "spotify", "hulu", "disney", "amazon prime", "youtube",
            "movie", "theater", "cinema", "concert", "ticket", "entertainment",
            "game", "steam", "playstation", "xbox", "nintendo",
            "google", "temporary hold"
        ]
    },
    "Shopping": {
        "emoji": "🛍️",
        "keywords": [
            "amazon", "ebay", "etsy", "shop", "store", "retail", "mall",
            "clothing", "fashion", "shoes", "apparel", "best buy", "apple store",
            "tienda", "centro comercial", "epa", "construplaza"
        ]
    },
    "Healthcare": {
        "emoji": "⚕️",
        "keywords": [
            "pharmacy", "cvs", "walgreens", "hospital", "clinic", "doctor",
            "medical", "health", "dental", "vision", "insurance", "prescription",
            "farmacia", "clinica", "consultorio", "laboratorio"
        ]
    },
    "Travel": {
        "emoji": "✈️",
        "keywords": [
            "hotel", "airbnb", "booking", "expedia", "airline", "flight",
            "travel", "vacation", "resort", "marriott", "hilton", "hyatt",
            "avianca", "volaris", "copa airlines"
        ]
    },
    "Bills & Utilities": {
        "emoji": "📄",
        "keywords": [
            "bill", "utility", "electric", "gas", "water", "phone", "mobile",
            "verizon", "att", "t-mobile", "comcast", "spectrum", "insurance",
            "seguro", "ins", "ccss", "caja"
        ]
    },
    "Transfers": {
        "emoji": "💸",
        "keywords": [
            "transfer", "venmo", "paypal", "zelle", "cashapp", "payment",
            "withdrawal", "deposit", "atm",
            "sinpe", "transferencia", "cajero", "cajero automatico", "retiro"
        ]
    }
}

def categorize_transaction(transaction: TransactionData) -> CategorizedTransaction:
    """
    Categorize a single transaction based on merchant keywords.
    """
    merchant_lower = transaction["merchant"].lower()
    raw_text_lower = transaction["raw_text"].lower()
    
    best_category = "Other"
    best_emoji = "❓"
    best_match_count = 0
    
    # Check each category
    for category_name, category_data in CATEGORIES.items():
        match_count = 0
        
        for keyword in category_data["keywords"]:
            if keyword in merchant_lower or keyword in raw_text_lower:
                match_count += 1
        
        if match_count > best_match_count:
            best_match_count = match_count
            best_category = category_name
            best_emoji = category_data["emoji"]
    
    return {
        "email_id": transaction["email_id"],
        "date": transaction["date"],
        "amount": transaction["amount"],
        "merchant": transaction["merchant"],
        "card_last_4": transaction["card_last_4"],
        "transaction_type": transaction["transaction_type"],
        "category": best_category,
        "category_emoji": best_emoji,
        "confidence": transaction["confidence"],
        "raw_text": transaction["raw_text"]
    }

def main(transactions: List[TransactionData]) -> List[CategorizedTransaction]:
    """
    Categorize transactions by merchant keywords.
    
    Args:
        transactions: List of TransactionData dictionaries
    
    Returns:
        List of CategorizedTransaction dictionaries
    """
    categorized = []
    
    for transaction in transactions:
        try:
            categorized_transaction = categorize_transaction(transaction)
            categorized.append(categorized_transaction)
        except Exception as e:
            print(f"Error categorizing transaction: {e}")
            # Add with default category
            categorized.append({
                **transaction,
                "category": "Other",
                "category_emoji": "❓"
            })
    
    return categorized
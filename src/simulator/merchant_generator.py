"""
CasePilot — Merchant Generator
================================
Generates 50 merchants across diverse business categories.
Each merchant has a risk classification based on their category.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from faker import Faker

from src.config.settings import SIMULATION, MERCHANT_CATEGORIES, INDIAN_CITIES
from src.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)
fake = Faker("en_IN")

# Merchant name templates by category
MERCHANT_NAMES = {
    "GROCERY": [
        "Big Bazaar", "D-Mart", "Reliance Fresh", "More Supermarket",
        "Spencer's Retail", "Star Bazaar", "Nilgiris", "Nature's Basket",
    ],
    "ELECTRONICS": [
        "Croma", "Reliance Digital", "Vijay Sales", "Poorvika Mobiles",
        "Samsung Store", "Apple Store", "Bajaj Electronics",
    ],
    "TRAVEL": [
        "MakeMyTrip", "Goibibo", "Yatra", "IRCTC", "Cleartrip",
        "EaseMyTrip", "Thomas Cook", "Cox & Kings",
    ],
    "FUEL": [
        "Indian Oil", "Bharat Petroleum", "Hindustan Petroleum",
        "Shell", "Nayara Energy", "Reliance Petroleum",
    ],
    "RESTAURANT": [
        "Swiggy Partner", "Zomato Partner", "Domino's Pizza",
        "McDonald's", "KFC", "Pizza Hut", "Haldiram's", "Barbeque Nation",
    ],
    "ENTERTAINMENT": [
        "PVR Cinemas", "INOX", "BookMyShow", "Netflix India",
        "Amazon Prime", "Hotstar", "Spotify India",
    ],
    "HEALTHCARE": [
        "Apollo Pharmacy", "Medplus", "1mg", "PharmEasy",
        "Netmeds", "Fortis Healthcare", "Max Healthcare",
    ],
    "EDUCATION": [
        "BYJU's", "Unacademy", "Coursera India", "Udemy India",
        "Vedantu", "UpGrad", "Simplilearn",
    ],
    "FASHION": [
        "Myntra", "Ajio", "Westside", "Zara India", "H&M India",
        "Fabindia", "Allen Solly", "Van Heusen",
    ],
    "JEWELRY": [
        "Tanishq", "Kalyan Jewellers", "Malabar Gold", "PC Jeweller",
        "Senco Gold", "CaratLane", "BlueStone",
    ],
    "ONLINE_GAMING": [
        "Dream11", "MPL", "WinZO", "Paytm First Games",
        "RummyCircle", "PokerStars India",
    ],
    "CRYPTOCURRENCY": [
        "WazirX", "CoinDCX", "ZebPay", "CoinSwitch Kuber",
        "Unocoin", "BuyUcoin",
    ],
    "FOREIGN_EXCHANGE": [
        "Thomas Cook Forex", "BookMyForex", "ExTravelMoney",
        "Centrum Forex", "Weizmann Forex",
    ],
    "LUXURY_GOODS": [
        "Louis Vuitton", "Gucci India", "Rolex India", "Tiffany & Co",
        "Burberry India", "DLF Emporio",
    ],
    "TELECOM": [
        "Jio", "Airtel", "Vi (Vodafone Idea)", "BSNL",
        "Jio Fiber", "ACT Fibernet",
    ],
}


def generate_merchants(count: int = None) -> List[Dict[str, Any]]:
    """
    Generate merchant records across diverse categories.

    Args:
        count: Number of merchants to generate. Defaults to SIMULATION config.

    Returns:
        List of merchant dictionaries.
    """
    count = count or SIMULATION["num_merchants"]
    random.seed(SIMULATION["random_seed"] + 1)

    merchants = []
    categories_used = {}

    for i in range(count):
        # Cycle through categories to ensure diversity
        cat_info = MERCHANT_CATEGORIES[i % len(MERCHANT_CATEGORIES)]
        category = cat_info["category"]
        categories_used[category] = categories_used.get(category, 0) + 1

        # Pick a merchant name from the category
        names = MERCHANT_NAMES.get(category, [f"{category} Store"])
        idx = categories_used[category] - 1
        if idx < len(names):
            merchant_name = names[idx]
        else:
            merchant_name = f"{random.choice(names)} - Branch {idx + 1}"

        city_info = random.choice(INDIAN_CITIES)
        registered_at = datetime.now() - timedelta(days=random.randint(180, 1825))

        merchants.append({
            "MERCHANT_ID": generate_uuid(),
            "MERCHANT_NAME": merchant_name,
            "CATEGORY": category,
            "MCC_CODE": cat_info["mcc"],
            "CITY": city_info["city"],
            "STATE": city_info["state"],
            "COUNTRY": "India",
            "RISK_LEVEL": cat_info["risk"],
            "IS_ACTIVE": True,
            "REGISTERED_AT": registered_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Log summary
    risk_counts = {}
    for m in merchants:
        r = m["RISK_LEVEL"]
        risk_counts[r] = risk_counts.get(r, 0) + 1
    logger.info(f"Generated {len(merchants)} merchants. Risk levels: {risk_counts}")

    return merchants


def insert_merchants_to_snowflake(merchants: List[Dict[str, Any]], connection) -> int:
    """Insert generated merchants into Snowflake RAW.MERCHANT table."""
    connection.use_schema("RAW")

    insert_query = """
        INSERT INTO MERCHANT (
            MERCHANT_ID, MERCHANT_NAME, CATEGORY, MCC_CODE,
            CITY, STATE, COUNTRY, RISK_LEVEL, IS_ACTIVE, REGISTERED_AT
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    data = [
        (
            m["MERCHANT_ID"], m["MERCHANT_NAME"], m["CATEGORY"], m["MCC_CODE"],
            m["CITY"], m["STATE"], m["COUNTRY"], m["RISK_LEVEL"],
            m["IS_ACTIVE"], m["REGISTERED_AT"],
        )
        for m in merchants
    ]

    rows = connection.execute_many(insert_query, data)
    logger.info(f"Inserted {rows} merchants into Snowflake.")
    return rows

"""
CasePilot 2.0 — Transaction Generator
========================================
Generates realistic banking transactions with persona-driven behavior and
ground truth fraud labels (95% legitimate, 5% fraudulent).

Fraud Types:
  - ACCOUNT_TAKEOVER
  - NEW_DEVICE_FRAUD
  - VELOCITY_FRAUD
  - MONEY_MULE
  - CARD_FRAUD
  - BENEFICIARY_FRAUD
  - GEO_ANOMALY
  - LARGE_AMOUNT_ANOMALY
"""

import random
import logging
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from src.config.settings import (
    SIMULATION, PERSONAS, CHANNELS, TXN_TYPES,
    INDIAN_CITIES, FOREIGN_CITIES, FRAUD_TYPES, FRAUD_CONFIG
)
from src.utils.helpers import generate_uuid, weighted_choice, random_timestamp

logger = logging.getLogger(__name__)

# Transaction description templates
TXN_DESCRIPTIONS = {
    "UPI": [
        "UPI payment to {merchant}", "UPI transfer - {merchant}",
        "PhonePe payment - {merchant}", "GPay to {merchant}",
        "Paytm - {merchant}", "BHIM UPI - {merchant}",
    ],
    "IMPS": [
        "IMPS transfer to {merchant}", "IMPS txn - {merchant}",
        "Instant transfer {merchant}",
    ],
    "NEFT": [
        "NEFT transfer to {merchant}", "NEFT out - {merchant}",
    ],
    "RTGS": [
        "RTGS transfer to {merchant}", "RTGS payment - {merchant}",
    ],
    "POS": [
        "POS purchase at {merchant}", "Card payment - {merchant}",
        "Contactless swipe at {merchant}",
    ],
    "ATM": [
        "ATM cash withdrawal", "Cash withdrawal - ATM",
        "ATM cash - {city}",
    ],
    "ONLINE_BANKING": [
        "Net banking transfer to {merchant}", "Online transfer - {merchant}",
        "Bill payment via NetBanking - {merchant}",
    ],
}


def _generate_transaction_time(base_date: datetime, is_fraud: bool = False) -> datetime:
    """Generate realistic transaction timestamp. Fraud/anomalous txns can cluster at odd hours."""
    if is_fraud and random.random() < 0.4:
        # Odd-hour activity
        hour = random.randint(0, 3)
        minute = random.randint(0, 59)
    else:
        # Normal hour distribution (business hours)
        hour_weights = [
            0.5, 0.3, 0.2, 0.2, 0.3, 0.5,     # 0-5 AM
            1.0, 2.0, 4.0, 5.0, 6.0, 7.0,     # 6-11 AM
            8.0, 7.0, 6.0, 5.0, 5.0, 6.0,     # 12-5 PM
            7.0, 8.0, 7.0, 5.0, 3.0, 1.0,     # 6-11 PM
        ]
        hour = random.choices(range(24), weights=hour_weights, k=1)[0]
        minute = random.randint(0, 59)

    second = random.randint(0, 59)
    return base_date.replace(hour=hour, minute=minute, second=second)


def _calculate_amount(persona: str, channel: str, is_fraud: bool = False, fraud_type: str = "") -> float:
    """Calculate transaction amount based on persona and fraud ground truth."""
    config = PERSONAS[persona]
    min_amt, max_amt = config["avg_txn_amount"]

    if is_fraud:
        if fraud_type == "LARGE_AMOUNT_ANOMALY":
            # 5x to 15x normal maximum amount
            amount = random.uniform(max_amt * 5, max_amt * 15)
        elif fraud_type == "VELOCITY_FRAUD" or fraud_type == "MONEY_MULE":
            # Multiple moderate-to-high transactions
            amount = random.uniform(min_amt * 2, max_amt * 2)
        else:
            # General fraud high amounts
            amount = random.uniform(max_amt * 1.5, max_amt * 4)
    else:
        # Normal distribution around persona baseline
        mean = (min_amt + max_amt) / 2
        std = (max_amt - min_amt) / 4
        amount = max(10.0, random.gauss(mean, std))

    if channel == "ATM":
        amount = round(amount / 500) * 500
        amount = max(500.0, amount)

    return round(amount, 2)


def generate_transactions(
    customers: List[Dict], accounts: List[Dict],
    merchants: List[Dict], devices: List[Dict],
    count: int = None,
) -> List[Dict[str, Any]]:
    """Generate scaled transactions with ground truth fraud annotations."""
    count = count or SIMULATION["num_transactions"]
    random.seed(SIMULATION["random_seed"] + 3)

    fraud_count = int(count * FRAUD_CONFIG["fraud_ratio"])
    normal_count = count - fraud_count

    # Build lookup maps
    customer_map = {c["CUSTOMER_ID"]: c for c in customers}
    acct_by_customer = {}
    for a in accounts:
        cid = a["CUSTOMER_ID"]
        acct_by_customer.setdefault(cid, []).append(a)

    device_by_customer = {}
    for d in devices:
        cid = d["CUSTOMER_ID"]
        device_by_customer.setdefault(cid, []).append(d)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=SIMULATION["transaction_days"])

    transactions = []

    # 1. --- NORMAL (LEGITIMATE) TRANSACTIONS ---
    logger.info("Generating legitimate transactions...")
    for _ in range(normal_count):
        customer = random.choice(customers)
        cid = customer["CUSTOMER_ID"]
        persona = customer["PERSONA"]

        cust_accounts = acct_by_customer.get(cid, [])
        if not cust_accounts:
            continue
        account = random.choice(cust_accounts)

        cust_devices = device_by_customer.get(cid, [])
        device = random.choice(cust_devices) if cust_devices else random.choice(devices)

        merchant = random.choice(merchants)
        channel = weighted_choice(CHANNELS)
        txn_type = weighted_choice(TXN_TYPES)

        base_date = start_date + timedelta(days=random.randint(0, SIMULATION["transaction_days"] - 1))
        txn_time = _generate_transaction_time(base_date, is_fraud=False)
        amount = _calculate_amount(persona, channel, is_fraud=False)

        desc_template = random.choice(TXN_DESCRIPTIONS.get(channel, ["Transaction"]))
        description = desc_template.format(merchant=merchant["MERCHANT_NAME"], city=merchant["CITY"])

        transactions.append({
            "TXN_ID": generate_uuid(),
            "ACCOUNT_ID": account["ACCOUNT_ID"],
            "CUSTOMER_ID": cid,
            "MERCHANT_ID": merchant["MERCHANT_ID"],
            "DEVICE_ID": device["DEVICE_ID"],
            "AMOUNT": amount,
            "CURRENCY": "INR",
            "TXN_TYPE": txn_type,
            "CHANNEL": channel,
            "STATUS": random.choices(["COMPLETED", "PENDING", "FAILED"], weights=[0.95, 0.03, 0.02], k=1)[0],
            "TXN_TIMESTAMP": txn_time.strftime("%Y-%m-%d %H:%M:%S"),
            "DESCRIPTION": description,
            "MERCHANT_CITY": merchant["CITY"],
            "MERCHANT_COUNTRY": "India",
            "LATITUDE": None,
            "LONGITUDE": None,
            "IS_INTERNATIONAL": False,
            "IS_FRAUD": False,
            "FRAUD_TYPE": None,
            "FRAUD_REASON": None,
            "FRAUD_CONFIDENCE": 0.0,
            "FRAUD_SCORE": 0.0,
            "CLASSIFICATION": "LEGITIMATE",
        })

    # 2. --- FRAUDULENT TRANSACTIONS ---
    logger.info("Generating fraudulent transactions...")
    for _ in range(fraud_count):
        fraud_type = random.choice(FRAUD_TYPES)
        customer = random.choice(customers)
        cid = customer["CUSTOMER_ID"]
        persona = customer["PERSONA"]

        cust_accounts = acct_by_customer.get(cid, [])
        if not cust_accounts:
            continue
        account = random.choice(cust_accounts)
        cust_devices = device_by_customer.get(cid, [])

        base_date = start_date + timedelta(days=random.randint(0, SIMULATION["transaction_days"] - 1))
        channel = weighted_choice(CHANNELS)
        is_intl = False
        m_country = "India"
        merchant = random.choice(merchants)
        m_city = merchant["CITY"]

        # Adjust parameters based on fraud type
        if fraud_type == "NEW_DEVICE_FRAUD":
            # Untrusted device not belonging to this customer
            untrusted = [d for d in devices if d["CUSTOMER_ID"] != cid]
            device = random.choice(untrusted) if untrusted else random.choice(devices)
            reason = "Transaction initiated from newly associated untrusted device"

        elif fraud_type == "GEO_ANOMALY":
            device = random.choice(cust_devices) if cust_devices else random.choice(devices)
            foreign_loc = random.choice(FOREIGN_CITIES)
            m_city = foreign_loc["city"]
            m_country = foreign_loc["country"]
            is_intl = True
            channel = "CARD"
            reason = f"Cross-border transaction originating from {m_city}, {m_country}"

        elif fraud_type == "LARGE_AMOUNT_ANOMALY":
            device = random.choice(cust_devices) if cust_devices else random.choice(devices)
            reason = f"Transaction amount significantly exceeds customer normal profile limit"

        elif fraud_type == "VELOCITY_FRAUD":
            device = random.choice(cust_devices) if cust_devices else random.choice(devices)
            reason = "Multiple high-frequency transactions executed in short time window"

        elif fraud_type == "ACCOUNT_TAKEOVER":
            # Untrusted device + high amount
            untrusted = [d for d in devices if d["CUSTOMER_ID"] != cid]
            device = random.choice(untrusted) if untrusted else random.choice(devices)
            reason = "Suspected credentials compromise, device and location match ATO pattern"

        elif fraud_type == "CARD_FRAUD":
            device = random.choice(cust_devices) if cust_devices else random.choice(devices)
            channel = "POS"
            reason = "Card cloning signature or physical card skimming fraud detected"

        elif fraud_type == "BENEFICIARY_FRAUD":
            device = random.choice(cust_devices) if cust_devices else random.choice(devices)
            channel = "ONLINE_BANKING"
            reason = "Transfer sent to newly added high-risk beneficiary account"

        else: # MONEY_MULE
            device = random.choice(cust_devices) if cust_devices else random.choice(devices)
            reason = "Rapid cash-in and cash-out routing pattern matching money mule behavior"

        txn_time = _generate_transaction_time(base_date, is_fraud=True)
        amount = _calculate_amount(persona, channel, is_fraud=True, fraud_type=fraud_type)
        confidence = round(random.uniform(*FRAUD_CONFIG["confidence_range"]), 4)

        desc_template = random.choice(TXN_DESCRIPTIONS.get(channel, ["Transaction"]))
        description = desc_template.format(merchant=merchant["MERCHANT_NAME"], city=m_city)

        transactions.append({
            "TXN_ID": generate_uuid(),
            "ACCOUNT_ID": account["ACCOUNT_ID"],
            "CUSTOMER_ID": cid,
            "MERCHANT_ID": merchant["MERCHANT_ID"],
            "DEVICE_ID": device["DEVICE_ID"],
            "AMOUNT": amount,
            "CURRENCY": "INR" if not is_intl else random.choice(["USD", "AED", "GBP", "SGD"]),
            "TXN_TYPE": "DEBIT",
            "CHANNEL": channel,
            "STATUS": "COMPLETED",
            "TXN_TIMESTAMP": txn_time.strftime("%Y-%m-%d %H:%M:%S"),
            "DESCRIPTION": description,
            "MERCHANT_CITY": m_city,
            "MERCHANT_COUNTRY": m_country,
            "LATITUDE": None,
            "LONGITUDE": None,
            "IS_INTERNATIONAL": is_intl,
            "IS_FRAUD": True,
            "FRAUD_TYPE": fraud_type,
            "FRAUD_REASON": reason,
            "FRAUD_CONFIDENCE": confidence,
            "FRAUD_SCORE": 0.0,
            "CLASSIFICATION": "LEGITIMATE",
        })

    # Sort transactions chronologically
    transactions.sort(key=lambda x: x["TXN_TIMESTAMP"])
    logger.info(f"Successfully generated {len(transactions)} transactions.")
    return transactions


def insert_transactions_to_snowflake(transactions: List[Dict[str, Any]], connection) -> int:
    """Insert generated transactions with ground truth fraud labels into Snowflake using direct SQL batches."""
    connection.use_schema("RAW")
    cursor = connection.get_connection().cursor()
    total_rows = 0
    try:
        batch_size = 5000
        for i in range(0, len(transactions), batch_size):
            chunk = transactions[i:i+batch_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
            query = f"""
                INSERT INTO TRANSACTION (
                    TXN_ID, ACCOUNT_ID, CUSTOMER_ID, MERCHANT_ID, DEVICE_ID,
                    AMOUNT, CURRENCY, TXN_TYPE, CHANNEL, STATUS,
                    TXN_TIMESTAMP, DESCRIPTION, MERCHANT_CITY, MERCHANT_COUNTRY,
                    LATITUDE, LONGITUDE, IS_INTERNATIONAL,
                    IS_FRAUD, FRAUD_TYPE, FRAUD_REASON, FRAUD_CONFIDENCE,
                    FRAUD_SCORE, CLASSIFICATION
                ) VALUES {placeholders}
            """
            params = []
            for t in chunk:
                params.extend([
                    t["TXN_ID"], t["ACCOUNT_ID"], t["CUSTOMER_ID"],
                    t.get("MERCHANT_ID"), t.get("DEVICE_ID"), t["AMOUNT"],
                    t["CURRENCY"], t["TXN_TYPE"], t["CHANNEL"], t["STATUS"],
                    t["TXN_TIMESTAMP"], t["DESCRIPTION"], t.get("MERCHANT_CITY"),
                    t.get("MERCHANT_COUNTRY"), t.get("LATITUDE"), t.get("LONGITUDE"),
                    t.get("IS_INTERNATIONAL", False),
                    t.get("IS_FRAUD", False), t.get("FRAUD_TYPE"), t.get("FRAUD_REASON"),
                    t.get("FRAUD_CONFIDENCE", 0.0), t.get("FRAUD_SCORE", 0.0),
                    t.get("CLASSIFICATION", "LEGITIMATE")
                ])
            cursor.execute(query, params)
            total_rows += len(chunk)
            logger.info(f"Uploaded {total_rows:,}/{len(transactions):,} transactions...")
        connection.get_connection().commit()
    finally:
        cursor.close()
    return total_rows



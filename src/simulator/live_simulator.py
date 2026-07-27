"""
CasePilot — Live Transaction Simulator
=========================================
Continuously generates and inserts new transactions into Snowflake
every few seconds, simulating a real-time banking data feed.

This script is the "data source" that feeds the entire CasePilot pipeline:

    Live Simulator → RAW.TRANSACTION → TRANSACTION_STREAM
        → ALERT_CREATION_TASK → ALERTS.ALERT → ALERT_STREAM
        → CASE_CREATION_TASK → INVESTIGATION.INVESTIGATION_CASE

Usage:
    python -m src.simulator.live_simulator

    Options (via environment or defaults):
        LIVE_BATCH_SIZE=5       Transactions per batch
        LIVE_INTERVAL_SEC=10    Seconds between batches
        LIVE_SUSPICIOUS_RATE=0.15  Higher suspicious rate for demo
"""

import os
import sys
import time
import random
import logging
from datetime import datetime, timedelta

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.snowflake_connection import SnowflakeConnection
from src.config.settings import (
    SIMULATION, PERSONAS, CHANNELS, INDIAN_CITIES, FOREIGN_CITIES,
    MERCHANT_CATEGORIES,
)
from src.utils.helpers import (
    generate_uuid, weighted_choice, generate_phone_number,
    generate_ip_address, setup_logging, format_currency,
)

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
BATCH_SIZE = int(os.getenv("LIVE_BATCH_SIZE", "5"))
INTERVAL_SEC = int(os.getenv("LIVE_INTERVAL_SEC", "10"))
SUSPICIOUS_RATE = float(os.getenv("LIVE_SUSPICIOUS_RATE", "0.15"))


# ── Transaction Description Templates ────────────────────────────────────────
TXN_DESCRIPTIONS = {
    "UPI": ["UPI payment to {merchant}", "GPay to {merchant}", "PhonePe - {merchant}"],
    "CARD": ["POS purchase at {merchant}", "Card payment - {merchant}"],
    "ATM": ["ATM withdrawal", "Cash withdrawal - ATM"],
    "WEB": ["Online purchase - {merchant}", "Net banking - {merchant}"],
    "MOBILE_APP": ["Mobile payment - {merchant}", "App purchase - {merchant}"],
}


def _fetch_existing_entities(conn):
    """
    Fetch existing customers, accounts, merchants, devices from Snowflake
    so the live simulator can create realistic transactions linked to them.
    """
    logger.info("Fetching existing entities from Snowflake...")

    customers = conn.execute_query(
        "SELECT CUSTOMER_ID, PERSONA, CITY FROM CASEPILOT_DB.RAW.CUSTOMER"
    )
    accounts = conn.execute_query(
        "SELECT ACCOUNT_ID, CUSTOMER_ID FROM CASEPILOT_DB.RAW.ACCOUNT"
    )
    merchants = conn.execute_query(
        "SELECT MERCHANT_ID, MERCHANT_NAME, CITY, COUNTRY FROM CASEPILOT_DB.RAW.MERCHANT"
    )
    devices = conn.execute_query(
        "SELECT DEVICE_ID, CUSTOMER_ID, IS_TRUSTED FROM CASEPILOT_DB.RAW.DEVICE"
    )

    # Convert to dicts for easier use
    cust_list = [{"CUSTOMER_ID": r[0], "PERSONA": r[1], "CITY": r[2]} for r in customers]
    acct_list = [{"ACCOUNT_ID": r[0], "CUSTOMER_ID": r[1]} for r in accounts]
    merch_list = [{"MERCHANT_ID": r[0], "MERCHANT_NAME": r[1], "CITY": r[2], "COUNTRY": r[3]} for r in merchants]
    dev_list = [{"DEVICE_ID": r[0], "CUSTOMER_ID": r[1], "IS_TRUSTED": r[2]} for r in devices]

    # Build lookup: customer_id -> accounts
    acct_by_cust = {}
    for a in acct_list:
        acct_by_cust.setdefault(a["CUSTOMER_ID"], []).append(a)

    # Build lookup: customer_id -> devices
    dev_by_cust = {}
    for d in dev_list:
        dev_by_cust.setdefault(d["CUSTOMER_ID"], []).append(d)

    logger.info(
        f"Loaded {len(cust_list)} customers, {len(acct_list)} accounts, "
        f"{len(merch_list)} merchants, {len(dev_list)} devices"
    )

    return cust_list, acct_by_cust, merch_list, dev_by_cust


def _generate_live_transaction(customer, acct_by_cust, merchants, dev_by_cust, is_suspicious=False):
    """Generate a single live transaction."""
    cid = customer["CUSTOMER_ID"]
    persona = customer["PERSONA"]

    # Get account
    cust_accounts = acct_by_cust.get(cid, [])
    if not cust_accounts:
        return None
    account = random.choice(cust_accounts)

    # Get device
    cust_devices = dev_by_cust.get(cid, [])
    device = random.choice(cust_devices) if cust_devices else None

    merchant = random.choice(merchants)
    channel = weighted_choice(CHANNELS)
    now = datetime.now()

    if is_suspicious:
        # Pick a suspicious pattern
        pattern = random.choice(["HIGH_VALUE", "ODD_HOUR", "NEW_DEVICE", "FOREIGN"])

        if pattern == "HIGH_VALUE":
            amount = round(random.uniform(30000, 200000), 2)
            txn_time = now
            m_city = merchant["CITY"]
            m_country = merchant["COUNTRY"] or "India"
            is_intl = False

        elif pattern == "ODD_HOUR":
            amount = round(random.uniform(500, 15000), 2)
            # Force odd hour timestamp
            txn_time = now.replace(hour=random.randint(0, 3), minute=random.randint(0, 59))
            m_city = merchant["CITY"]
            m_country = merchant["COUNTRY"] or "India"
            is_intl = False

        elif pattern == "NEW_DEVICE":
            amount = round(random.uniform(1000, 25000), 2)
            txn_time = now
            # Use untrusted device if available
            untrusted = [d for d in (cust_devices or []) if not d.get("IS_TRUSTED", True)]
            if untrusted:
                device = random.choice(untrusted)
            m_city = merchant["CITY"]
            m_country = merchant["COUNTRY"] or "India"
            is_intl = False

        else:  # FOREIGN
            amount = round(random.uniform(5000, 100000), 2)
            txn_time = now
            foreign = random.choice(FOREIGN_CITIES)
            m_city = foreign["city"]
            m_country = foreign["country"]
            is_intl = True
            channel = random.choice(["CARD", "WEB"])
    else:
        # Normal transaction
        persona_config = PERSONAS.get(persona, PERSONAS["SALARY_EMPLOYEE"])
        min_amt, max_amt = persona_config["avg_txn_amount"]
        amount = round(random.uniform(min_amt, max_amt), 2)
        txn_time = now
        m_city = merchant["CITY"]
        m_country = merchant["COUNTRY"] or "India"
        is_intl = False

    desc_templates = TXN_DESCRIPTIONS.get(channel, ["Transaction - {merchant}"])
    description = random.choice(desc_templates).format(
        merchant=merchant["MERCHANT_NAME"], city=m_city
    )

    txn_type = random.choices(["DEBIT", "CREDIT", "TRANSFER"], weights=[0.65, 0.30, 0.05], k=1)[0]

    return (
        generate_uuid(),                              # TXN_ID
        account["ACCOUNT_ID"],                        # ACCOUNT_ID
        cid,                                          # CUSTOMER_ID
        merchant["MERCHANT_ID"],                      # MERCHANT_ID
        device["DEVICE_ID"] if device else None,      # DEVICE_ID
        amount,                                       # AMOUNT
        "INR" if not is_intl else random.choice(["USD", "AED", "GBP"]),  # CURRENCY
        txn_type,                                     # TXN_TYPE
        channel,                                      # CHANNEL
        "COMPLETED",                                  # STATUS
        txn_time.strftime("%Y-%m-%d %H:%M:%S"),       # TXN_TIMESTAMP
        description,                                  # DESCRIPTION
        m_city,                                       # MERCHANT_CITY
        m_country,                                    # MERCHANT_COUNTRY
        None,                                         # LATITUDE
        None,                                         # LONGITUDE
        is_intl,                                      # IS_INTERNATIONAL
    )


def _insert_batch(conn, batch):
    """Insert a batch of transactions into Snowflake."""
    insert_sql = """
        INSERT INTO CASEPILOT_DB.RAW.TRANSACTION (
            TXN_ID, ACCOUNT_ID, CUSTOMER_ID, MERCHANT_ID, DEVICE_ID,
            AMOUNT, CURRENCY, TXN_TYPE, CHANNEL, STATUS,
            TXN_TIMESTAMP, DESCRIPTION, MERCHANT_CITY, MERCHANT_COUNTRY,
            LATITUDE, LONGITUDE, IS_INTERNATIONAL
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    conn.execute_many(insert_sql, batch)


def run_live_simulator():
    """
    Main loop: continuously generate and insert transactions.

    Press Ctrl+C to stop.
    """
    setup_logging()
    logger.info("=" * 60)
    logger.info("🚀 CasePilot Live Simulator Starting")
    logger.info(f"   Batch size:      {BATCH_SIZE} transactions")
    logger.info(f"   Interval:        {INTERVAL_SEC} seconds")
    logger.info(f"   Suspicious rate: {SUSPICIOUS_RATE:.0%}")
    logger.info("=" * 60)

    conn = SnowflakeConnection()
    conn.connect()

    try:
        # Load existing entities once
        customers, acct_by_cust, merchants, dev_by_cust = _fetch_existing_entities(conn)

        if not customers:
            logger.error("No customers found in Snowflake. Run the initial data load first.")
            return

        batch_num = 0
        total_inserted = 0

        while True:
            batch_num += 1
            batch = []
            suspicious_in_batch = 0

            for _ in range(BATCH_SIZE):
                customer = random.choice(customers)
                is_suspicious = random.random() < SUSPICIOUS_RATE

                txn = _generate_live_transaction(
                    customer, acct_by_cust, merchants, dev_by_cust, is_suspicious
                )
                if txn:
                    batch.append(txn)
                    if is_suspicious:
                        suspicious_in_batch += 1

            if batch:
                _insert_batch(conn, batch)
                total_inserted += len(batch)

                # Log batch summary
                amounts = [t[5] for t in batch]  # AMOUNT is index 5
                logger.info(
                    f"📦 Batch #{batch_num}: Inserted {len(batch)} transactions "
                    f"({suspicious_in_batch} suspicious) | "
                    f"Amounts: {format_currency(min(amounts))} – {format_currency(max(amounts))} | "
                    f"Total: {total_inserted:,}"
                )

            logger.info(f"⏳ Waiting {INTERVAL_SEC}s for next batch...")
            time.sleep(INTERVAL_SEC)

    except KeyboardInterrupt:
        logger.info(f"\n🛑 Simulator stopped. Total transactions inserted: {total_inserted:,}")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    run_live_simulator()

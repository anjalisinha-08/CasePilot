"""
CasePilot — Alert Engine
==========================
Evaluates transactions against 5 alert rules and generates alerts.

Alert Rules:
    1. HIGH_VALUE_TXN    — Amount > ₹25,000
    2. ODD_HOUR_ACTIVITY — Transaction between 00:00–04:00
    3. NEW_DEVICE_USED   — Transaction from untrusted device
    4. RAPID_TXN_BURST   — 5+ transactions within 10 minutes
    5. FOREIGN_ACTIVITY  — Transaction outside India

This engine can run in two modes:
    - Batch mode: Process all transactions at once (initial load)
    - Stream mode: Called by Snowflake Tasks on new stream data
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

from src.config.settings import ALERT_RULES, TABLES
from src.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)


def _determine_severity(rule: str, amount: float = 0) -> str:
    """
    Determine alert severity based on rule type and transaction amount.

    Args:
        rule: Alert rule name.
        amount: Transaction amount.

    Returns:
        Severity level: LOW, MEDIUM, HIGH, or CRITICAL.
    """
    rule_config = ALERT_RULES.get(rule, {})

    if rule == "HIGH_VALUE_TXN":
        severity_map = rule_config.get("severity_map", {})
        severity = "MEDIUM"
        for threshold, sev in sorted(severity_map.items()):
            if amount >= threshold:
                severity = sev
        return severity

    return rule_config.get("default_severity", "MEDIUM")


def check_high_value_txn(
    transaction: Dict[str, Any],
    customer_persona: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Rule 1: HIGH_VALUE_TXN
    Triggers when transaction amount exceeds the threshold.

    Args:
        transaction: Transaction record.
        customer_persona: The customer's persona for context-aware thresholding.

    Returns:
        Alert dict if rule triggers, None otherwise.
    """
    rule_config = ALERT_RULES["HIGH_VALUE_TXN"]
    threshold = rule_config["threshold"]
    
    # Apply persona-specific threshold if available
    persona_thresholds = rule_config.get("persona_thresholds", {})
    if customer_persona and customer_persona in persona_thresholds:
        threshold = persona_thresholds[customer_persona]
        
    amount = transaction["AMOUNT"]

    if amount > threshold:
        severity = _determine_severity("HIGH_VALUE_TXN", amount)
        return {
            "ALERT_ID": generate_uuid(),
            "TXN_ID": transaction["TXN_ID"],
            "ACCOUNT_ID": transaction["ACCOUNT_ID"],
            "CUSTOMER_ID": transaction["CUSTOMER_ID"],
            "ALERT_TYPE": "HIGH_VALUE_TXN",
            "ALERT_DESCRIPTION": (
                f"High-value transaction of ₹{amount:,.2f} detected. "
                f"Threshold: ₹{threshold:,.2f}. "
                f"Channel: {transaction['CHANNEL']}. "
                f"Merchant: {transaction.get('DESCRIPTION', 'N/A')}."
            ),
            "SEVERITY": severity,
            "RULE_VERSION": "1.0",
            "TRIGGERED_AMOUNT": amount,
            "TRIGGERED_THRESHOLD": threshold,
            "STATUS": "NEW",
            "CREATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "UPDATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    return None


def check_odd_hour_activity(transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Rule 2: ODD_HOUR_ACTIVITY
    Triggers when transaction occurs between 00:00 and 04:00.

    Args:
        transaction: Transaction record.

    Returns:
        Alert dict if rule triggers, None otherwise.
    """
    config = ALERT_RULES["ODD_HOUR_ACTIVITY"]
    txn_time = datetime.strptime(transaction["TXN_TIMESTAMP"], "%Y-%m-%d %H:%M:%S")
    hour = txn_time.hour

    if config["start_hour"] <= hour < config["end_hour"]:
        return {
            "ALERT_ID": generate_uuid(),
            "TXN_ID": transaction["TXN_ID"],
            "ACCOUNT_ID": transaction["ACCOUNT_ID"],
            "CUSTOMER_ID": transaction["CUSTOMER_ID"],
            "ALERT_TYPE": "ODD_HOUR_ACTIVITY",
            "ALERT_DESCRIPTION": (
                f"Transaction at {txn_time.strftime('%H:%M:%S')} (odd hours: "
                f"{config['start_hour']:02d}:00–{config['end_hour']:02d}:00). "
                f"Amount: ₹{transaction['AMOUNT']:,.2f}. "
                f"Channel: {transaction['CHANNEL']}."
            ),
            "SEVERITY": config["default_severity"],
            "RULE_VERSION": "1.0",
            "TRIGGERED_AMOUNT": transaction["AMOUNT"],
            "TRIGGERED_THRESHOLD": None,
            "STATUS": "NEW",
            "CREATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "UPDATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    return None


def check_new_device(
    transaction: Dict[str, Any],
    devices: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Rule 3: NEW_DEVICE_USED
    Triggers when a transaction uses an untrusted device.

    Args:
        transaction: Transaction record.
        devices: All device records.

    Returns:
        Alert dict if rule triggers, None otherwise.
    """
    device_id = transaction.get("DEVICE_ID")
    if not device_id:
        return None

    # Find the device
    device = None
    for d in devices:
        if d["DEVICE_ID"] == device_id:
            device = d
            break

    if device and not device["IS_TRUSTED"]:
        config = ALERT_RULES["NEW_DEVICE_USED"]
        personal_only = config.get("personal_only", False)
        min_amount = config.get("min_amount", 0)

        # Exclude shared commercial devices (ATM/POS) from new device alerts
        if personal_only and device.get("DEVICE_TYPE") not in ["MOBILE", "LAPTOP", "TABLET"]:
            return None

        # Check minimum transaction amount
        if transaction["AMOUNT"] < min_amount:
            return None

        return {
            "ALERT_ID": generate_uuid(),
            "TXN_ID": transaction["TXN_ID"],
            "ACCOUNT_ID": transaction["ACCOUNT_ID"],
            "CUSTOMER_ID": transaction["CUSTOMER_ID"],
            "ALERT_TYPE": "NEW_DEVICE_USED",
            "ALERT_DESCRIPTION": (
                f"Transaction from untrusted device: "
                f"{device.get('DEVICE_NAME', 'Unknown')} "
                f"({device.get('DEVICE_TYPE', 'Unknown')}). "
                f"IP: {device.get('IP_ADDRESS', 'N/A')}. "
                f"Amount: ₹{transaction['AMOUNT']:,.2f}."
            ),
            "SEVERITY": config["default_severity"],
            "RULE_VERSION": "1.0",
            "TRIGGERED_AMOUNT": transaction["AMOUNT"],
            "TRIGGERED_THRESHOLD": None,
            "STATUS": "NEW",
            "CREATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "UPDATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    return None


def check_rapid_burst(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Rule 4: RAPID_TXN_BURST
    Triggers when a customer has 5+ transactions within 10 minutes.

    Args:
        transactions: All transactions sorted by timestamp.

    Returns:
        List of alert dicts for burst detections.
    """
    config = ALERT_RULES["RAPID_TXN_BURST"]
    max_txns = config["max_txns"]
    window = timedelta(minutes=config["window_minutes"])

    # Group by customer
    by_customer = defaultdict(list)
    for txn in transactions:
        by_customer[txn["CUSTOMER_ID"]].append(txn)

    alerts = []
    seen_windows = set()  # Dedup: (customer_id, window_start_str)

    for cust_id, cust_txns in by_customer.items():
        # Sort by timestamp
        sorted_txns = sorted(
            cust_txns,
            key=lambda x: datetime.strptime(x["TXN_TIMESTAMP"], "%Y-%m-%d %H:%M:%S")
        )

        for i, txn in enumerate(sorted_txns):
            txn_time = datetime.strptime(txn["TXN_TIMESTAMP"], "%Y-%m-%d %H:%M:%S")
            window_end = txn_time + window

            # Count transactions in window
            burst = [
                t for t in sorted_txns[i:]
                if datetime.strptime(t["TXN_TIMESTAMP"], "%Y-%m-%d %H:%M:%S") <= window_end
            ]

            if len(burst) > max_txns:
                dedup_key = (cust_id, txn_time.strftime("%Y-%m-%d %H:%M"))
                if dedup_key not in seen_windows:
                    seen_windows.add(dedup_key)
                    total_amount = sum(t["AMOUNT"] for t in burst)

                    alerts.append({
                        "ALERT_ID": generate_uuid(),
                        "TXN_ID": burst[0]["TXN_ID"],  # Reference first txn
                        "ACCOUNT_ID": burst[0]["ACCOUNT_ID"],
                        "CUSTOMER_ID": cust_id,
                        "ALERT_TYPE": "RAPID_TXN_BURST",
                        "ALERT_DESCRIPTION": (
                            f"Rapid transaction burst detected: {len(burst)} transactions "
                            f"within {config['window_minutes']} minutes. "
                            f"Total amount: ₹{total_amount:,.2f}. "
                            f"Window: {txn_time.strftime('%H:%M')} - "
                            f"{window_end.strftime('%H:%M')}."
                        ),
                        "SEVERITY": config["default_severity"],
                        "RULE_VERSION": "1.0",
                        "TRIGGERED_AMOUNT": total_amount,
                        "TRIGGERED_THRESHOLD": max_txns,
                        "STATUS": "NEW",
                        "CREATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "UPDATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })

    return alerts


def check_foreign_activity(transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Rule 5: FOREIGN_ACTIVITY
    Triggers when transaction originates outside India.

    Args:
        transaction: Transaction record.

    Returns:
        Alert dict if rule triggers, None otherwise.
    """
    config = ALERT_RULES["FOREIGN_ACTIVITY"]
    merchant_country = transaction.get("MERCHANT_COUNTRY", "India")

    if merchant_country != config["home_country"] and transaction.get("IS_INTERNATIONAL"):
        return {
            "ALERT_ID": generate_uuid(),
            "TXN_ID": transaction["TXN_ID"],
            "ACCOUNT_ID": transaction["ACCOUNT_ID"],
            "CUSTOMER_ID": transaction["CUSTOMER_ID"],
            "ALERT_TYPE": "FOREIGN_ACTIVITY",
            "ALERT_DESCRIPTION": (
                f"Foreign transaction detected in {transaction.get('MERCHANT_CITY', 'Unknown')}, "
                f"{merchant_country}. Amount: ₹{transaction['AMOUNT']:,.2f}. "
                f"Channel: {transaction['CHANNEL']}."
            ),
            "SEVERITY": config["default_severity"],
            "RULE_VERSION": "1.0",
            "TRIGGERED_AMOUNT": transaction["AMOUNT"],
            "TRIGGERED_THRESHOLD": None,
            "STATUS": "NEW",
            "CREATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "UPDATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    return None


def run_alert_engine(
    transactions: List[Dict[str, Any]],
    devices: List[Dict[str, Any]],
    customers: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute all alert rules against a batch of transactions.

    Args:
        transactions: List of transaction records.
        devices: List of device records (for NEW_DEVICE_USED rule).
        customers: Optional list of customer records for context-aware scoring.

    Returns:
        List of generated alerts (deduplicated).
    """
    logger.info(f"Running alert engine on {len(transactions)} transactions...")
    alerts = []
    seen_txn_rules = set()  # Dedup: (txn_id, alert_type)

    customer_map = {}
    if customers:
        customer_map = {c["CUSTOMER_ID"]: c for c in customers}

    # Device lookup for faster access
    device_map = {d["DEVICE_ID"]: d for d in devices}

    # Rule 1: HIGH_VALUE_TXN
    for txn in transactions:
        cust = customer_map.get(txn["CUSTOMER_ID"]) if customer_map else None
        persona = cust["PERSONA"] if cust else None
        alert = check_high_value_txn(txn, customer_persona=persona)
        if alert:
            key = (alert["TXN_ID"], alert["ALERT_TYPE"])
            if key not in seen_txn_rules:
                seen_txn_rules.add(key)
                alerts.append(alert)

    # Rule 2: ODD_HOUR_ACTIVITY
    for txn in transactions:
        alert = check_odd_hour_activity(txn)
        if alert:
            key = (alert["TXN_ID"], alert["ALERT_TYPE"])
            if key not in seen_txn_rules:
                seen_txn_rules.add(key)
                alerts.append(alert)

    # Rule 3: NEW_DEVICE_USED
    for txn in transactions:
        alert = check_new_device(txn, devices)
        if alert:
            key = (alert["TXN_ID"], alert["ALERT_TYPE"])
            if key not in seen_txn_rules:
                seen_txn_rules.add(key)
                alerts.append(alert)

    # Rule 4: RAPID_TXN_BURST
    burst_alerts = check_rapid_burst(transactions)
    for alert in burst_alerts:
        key = (alert["TXN_ID"], alert["ALERT_TYPE"])
        if key not in seen_txn_rules:
            seen_txn_rules.add(key)
            alerts.append(alert)

    # Rule 5: FOREIGN_ACTIVITY
    for txn in transactions:
        alert = check_foreign_activity(txn)
        if alert:
            key = (alert["TXN_ID"], alert["ALERT_TYPE"])
            if key not in seen_txn_rules:
                seen_txn_rules.add(key)
                alerts.append(alert)

    # Log summary
    type_counts = {}
    for a in alerts:
        t = a["ALERT_TYPE"]
        type_counts[t] = type_counts.get(t, 0) + 1
    logger.info(f"Alert engine generated {len(alerts)} alerts. Types: {type_counts}")

    return alerts


def insert_alerts_to_snowflake(alerts: List[Dict[str, Any]], connection) -> int:
    """Insert generated alerts into Snowflake ALERTS.ALERT table."""
    connection.use_schema("ALERTS")

    insert_query = """
        INSERT INTO ALERT (
            ALERT_ID, TXN_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE,
            ALERT_DESCRIPTION, SEVERITY, RULE_VERSION,
            TRIGGERED_AMOUNT, TRIGGERED_THRESHOLD, STATUS,
            CREATED_AT, UPDATED_AT
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    data = [
        (
            a["ALERT_ID"], a["TXN_ID"], a["ACCOUNT_ID"], a["CUSTOMER_ID"],
            a["ALERT_TYPE"], a["ALERT_DESCRIPTION"], a["SEVERITY"],
            a["RULE_VERSION"], a["TRIGGERED_AMOUNT"], a["TRIGGERED_THRESHOLD"],
            a["STATUS"], a["CREATED_AT"], a["UPDATED_AT"],
        )
        for a in alerts
    ]

    from src.utils.helpers import chunk_list
    total = 0
    for chunk in chunk_list(data, 500):
        total += connection.execute_many(insert_query, chunk)

    logger.info(f"Inserted {total} alerts into Snowflake.")
    return total

"""
CasePilot — Case Enrichment
==============================
Gathers comprehensive context for each investigation case:
  - Customer profile
  - Account profile
  - Transaction history (last 90 days)
  - Merchant interaction history
  - Device usage history
  - Previous alerts
  - Historical statistics (averages, frequencies)

All enrichment data is stored as VARIANT (JSON) in the CASE_ENRICHMENT table,
enabling flexible and schema-less investigation context.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict

from src.utils.helpers import generate_uuid, safe_divide

logger = logging.getLogger(__name__)


def _build_customer_profile(
    customer_id: str,
    customers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build customer profile JSON from customer data."""
    customer = next((c for c in customers if c["CUSTOMER_ID"] == customer_id), None)
    if not customer:
        return {"error": "Customer not found"}

    return {
        "customer_id": customer["CUSTOMER_ID"],
        "name": f"{customer['FIRST_NAME']} {customer['LAST_NAME']}",
        "email": customer["EMAIL"],
        "phone": customer["PHONE"],
        "persona": customer["PERSONA"],
        "city": customer["CITY"],
        "state": customer["STATE"],
        "country": customer["COUNTRY"],
        "occupation": customer["OCCUPATION"],
        "annual_income": customer["ANNUAL_INCOME"],
        "kyc_status": customer["KYC_STATUS"],
        "risk_rating": customer["RISK_RATING"],
        "account_age_days": (
            datetime.now() - datetime.strptime(customer["CREATED_AT"], "%Y-%m-%d %H:%M:%S")
        ).days,
        "is_active": customer["IS_ACTIVE"],
    }


def _build_account_profile(
    customer_id: str,
    accounts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build account profiles for a customer."""
    cust_accounts = [a for a in accounts if a["CUSTOMER_ID"] == customer_id]
    profiles = []

    for acct in cust_accounts:
        profiles.append({
            "account_id": acct["ACCOUNT_ID"],
            "account_type": acct["ACCOUNT_TYPE"],
            "account_number": acct["ACCOUNT_NUMBER"][-4:].rjust(len(acct["ACCOUNT_NUMBER"]), "*"),
            "balance": acct["BALANCE"],
            "currency": acct["CURRENCY"],
            "status": acct["ACCOUNT_STATUS"],
            "ifsc": acct["IFSC_CODE"],
            "opened_at": acct["OPENED_AT"],
        })

    return profiles


def _build_txn_history(
    customer_id: str,
    transactions: List[Dict[str, Any]],
    days: int = 90,
) -> Dict[str, Any]:
    """Build transaction history summary for last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    cust_txns = [
        t for t in transactions
        if t["CUSTOMER_ID"] == customer_id
        and datetime.strptime(t["TXN_TIMESTAMP"], "%Y-%m-%d %H:%M:%S") >= cutoff
    ]

    if not cust_txns:
        return {"total_transactions": 0, "recent_transactions": []}

    amounts = [t["AMOUNT"] for t in cust_txns]
    channels = defaultdict(int)
    for t in cust_txns:
        channels[t["CHANNEL"]] += 1

    # Last 10 transactions for the timeline
    sorted_txns = sorted(cust_txns, key=lambda x: x["TXN_TIMESTAMP"], reverse=True)
    recent = [
        {
            "txn_id": t["TXN_ID"],
            "amount": t["AMOUNT"],
            "channel": t["CHANNEL"],
            "timestamp": t["TXN_TIMESTAMP"],
            "description": t["DESCRIPTION"],
            "merchant_city": t.get("MERCHANT_CITY"),
            "is_international": t.get("IS_INTERNATIONAL", False),
        }
        for t in sorted_txns[:10]
    ]

    return {
        "period_days": days,
        "total_transactions": len(cust_txns),
        "total_amount": round(sum(amounts), 2),
        "avg_amount": round(safe_divide(sum(amounts), len(amounts)), 2),
        "max_amount": round(max(amounts), 2),
        "min_amount": round(min(amounts), 2),
        "channel_distribution": dict(channels),
        "recent_transactions": recent,
    }


def _build_merchant_history(
    customer_id: str,
    transactions: List[Dict[str, Any]],
    merchants: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build merchant interaction history."""
    merchant_map = {m["MERCHANT_ID"]: m for m in merchants}
    cust_txns = [t for t in transactions if t["CUSTOMER_ID"] == customer_id]

    merchant_stats = defaultdict(lambda: {"count": 0, "total": 0, "last_txn": None})
    for txn in cust_txns:
        mid = txn.get("MERCHANT_ID")
        if mid:
            merchant_stats[mid]["count"] += 1
            merchant_stats[mid]["total"] += txn["AMOUNT"]
            merchant_stats[mid]["last_txn"] = txn["TXN_TIMESTAMP"]

    result = []
    for mid, stats in sorted(merchant_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
        merchant = merchant_map.get(mid, {})
        result.append({
            "merchant_id": mid,
            "merchant_name": merchant.get("MERCHANT_NAME", "Unknown"),
            "category": merchant.get("CATEGORY", "Unknown"),
            "risk_level": merchant.get("RISK_LEVEL", "Unknown"),
            "transaction_count": stats["count"],
            "total_amount": round(stats["total"], 2),
            "last_transaction": stats["last_txn"],
        })

    return result


def _build_device_history(
    customer_id: str,
    devices: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build device usage history."""
    cust_devices = [d for d in devices if d["CUSTOMER_ID"] == customer_id]

    return [
        {
            "device_id": d["DEVICE_ID"],
            "device_type": d["DEVICE_TYPE"],
            "device_name": d.get("DEVICE_NAME"),
            "os": d.get("OS"),
            "ip_address": d.get("IP_ADDRESS"),
            "city": d.get("CITY"),
            "is_trusted": d["IS_TRUSTED"],
            "first_seen": d["FIRST_SEEN"],
            "last_seen": d["LAST_SEEN"],
        }
        for d in cust_devices
    ]


def _build_previous_alerts(
    customer_id: str,
    alerts: List[Dict[str, Any]],
    current_alert_id: str,
) -> List[Dict[str, Any]]:
    """Build history of previous alerts for this customer."""
    prev = [
        a for a in alerts
        if a["CUSTOMER_ID"] == customer_id and a["ALERT_ID"] != current_alert_id
    ]

    return [
        {
            "alert_id": a["ALERT_ID"],
            "alert_type": a["ALERT_TYPE"],
            "severity": a["SEVERITY"],
            "status": a["STATUS"],
            "description": a["ALERT_DESCRIPTION"][:200],
            "created_at": a["CREATED_AT"],
        }
        for a in sorted(prev, key=lambda x: x["CREATED_AT"], reverse=True)[:20]
    ]


def _build_historical_stats(
    customer_id: str,
    transactions: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute historical statistics for risk assessment."""
    cust_txns = [t for t in transactions if t["CUSTOMER_ID"] == customer_id]
    cust_alerts = [a for a in alerts if a["CUSTOMER_ID"] == customer_id]

    amounts = [t["AMOUNT"] for t in cust_txns] if cust_txns else [0]
    mean_amt = safe_divide(sum(amounts), len(amounts))

    # Standard deviation
    if len(amounts) > 1:
        variance = sum((a - mean_amt) ** 2 for a in amounts) / len(amounts)
        std_dev = variance ** 0.5
    else:
        std_dev = 0

    # Transactions per day
    if cust_txns:
        timestamps = [
            datetime.strptime(t["TXN_TIMESTAMP"], "%Y-%m-%d %H:%M:%S")
            for t in cust_txns
        ]
        date_range = (max(timestamps) - min(timestamps)).days or 1
        txn_per_day = len(cust_txns) / date_range
    else:
        txn_per_day = 0

    # International transaction ratio
    intl_count = sum(1 for t in cust_txns if t.get("IS_INTERNATIONAL", False))

    return {
        "total_transactions": len(cust_txns),
        "avg_transaction_amount": round(mean_amt, 2),
        "std_dev_amount": round(std_dev, 2),
        "max_transaction_amount": round(max(amounts), 2),
        "transactions_per_day": round(txn_per_day, 2),
        "total_alerts": len(cust_alerts),
        "international_txn_ratio": round(safe_divide(intl_count, len(cust_txns)), 4),
        "unique_merchants": len(set(t.get("MERCHANT_ID") for t in cust_txns if t.get("MERCHANT_ID"))),
        "unique_devices": len(set(t.get("DEVICE_ID") for t in cust_txns if t.get("DEVICE_ID"))),
    }


def enrich_cases(
    cases: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    customers: List[Dict[str, Any]],
    accounts: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    merchants: List[Dict[str, Any]],
    devices: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Enrich investigation cases with comprehensive context.

    For each case, gathers customer profile, account info, transaction
    history, merchant patterns, device info, previous alerts, and
    historical statistics.

    Args:
        cases: Investigation case records.
        alerts: All alert records.
        customers: All customer records.
        accounts: All account records.
        transactions: All transaction records.
        merchants: All merchant records.
        devices: All device records.

    Returns:
        List of case enrichment dictionaries.
    """
    logger.info(f"Enriching {len(cases)} cases...")
    enrichments = []

    # Find alert for each case
    alert_map = {a["ALERT_ID"]: a for a in alerts}

    for case in cases:
        alert = alert_map.get(case["ALERT_ID"], {})
        customer_id = case["CUSTOMER_ID"]

        enrichment = {
            "ENRICHMENT_ID": generate_uuid(),
            "CASE_ID": case["CASE_ID"],
            "CUSTOMER_PROFILE": _build_customer_profile(customer_id, customers),
            "ACCOUNT_PROFILE": _build_account_profile(customer_id, accounts),
            "TXN_HISTORY": _build_txn_history(customer_id, transactions),
            "MERCHANT_HISTORY": _build_merchant_history(customer_id, transactions, merchants),
            "DEVICE_HISTORY": _build_device_history(customer_id, devices),
            "PREVIOUS_ALERTS": _build_previous_alerts(customer_id, alerts, case.get("ALERT_ID", "")),
            "HISTORICAL_STATS": _build_historical_stats(customer_id, transactions, alerts),
            "ENRICHED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        enrichments.append(enrichment)

    logger.info(f"Enriched {len(enrichments)} cases successfully.")
    return enrichments


def insert_enrichments_to_snowflake(enrichments: List[Dict[str, Any]], connection) -> int:
    """Insert enrichments into Snowflake INVESTIGATION.CASE_ENRICHMENT table."""
    connection.use_schema("INVESTIGATION")

    data = [
        (
            e["ENRICHMENT_ID"],
            e["CASE_ID"],
            json.dumps(e["CUSTOMER_PROFILE"]),
            json.dumps(e["ACCOUNT_PROFILE"]),
            json.dumps(e["TXN_HISTORY"]),
            json.dumps(e["MERCHANT_HISTORY"]),
            json.dumps(e["DEVICE_HISTORY"]),
            json.dumps(e["PREVIOUS_ALERTS"]),
            json.dumps(e["HISTORICAL_STATS"]),
            e["ENRICHED_AT"],
        )
        for e in enrichments
    ]

    insert_query = """
    INSERT INTO CASE_ENRICHMENT (
        ENRICHMENT_ID,
        CASE_ID,
        CUSTOMER_PROFILE,
        ACCOUNT_PROFILE,
        TXN_HISTORY,
        MERCHANT_HISTORY,
        DEVICE_HISTORY,
        PREVIOUS_ALERTS,
        HISTORICAL_STATS,
        ENRICHED_AT
    )
    SELECT
        %s,
        %s,
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        %s
    """

    total = 0

    cursor = connection.get_connection().cursor()

    try:
        for row in data:
            cursor.execute(insert_query, row)
            total += 1

        connection.get_connection().commit()

    finally:
        cursor.close()

    logger.info(f"Inserted {total} enrichments into Snowflake.")
    return total

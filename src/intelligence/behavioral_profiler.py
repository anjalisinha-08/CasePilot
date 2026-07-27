"""
CasePilot 2.0 — Behavioral Profiler
======================================
Builds customer-specific behavioral baselines from transaction history.

Key Insight: A ₹50L transaction is NORMAL for a business owner doing ₹1Cr/day,
but HIGHLY ANOMALOUS for a student spending ₹50K/day.

Profiles are stored in ANALYTICS.CUSTOMER_BEHAVIOR_PROFILE.
"""

import json
import logging
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict, Counter

from src.utils.helpers import generate_uuid, safe_divide

logger = logging.getLogger(__name__)


def build_customer_profile(
    customer_id: str,
    transactions: List[Dict[str, Any]],
    days: int = 180,
) -> Dict[str, Any]:
    """
    Build a behavioral profile for a single customer.

    Args:
        customer_id: Target customer.
        transactions: All transactions (pre-filtered or full list).
        days: Lookback period in days.

    Returns:
        Profile dictionary with statistical baselines.
    """
    cutoff = datetime.now() - timedelta(days=days)
    cust_txns = [
        t for t in transactions
        if t.get("CUSTOMER_ID") == customer_id
        and datetime.strptime(str(t["TXN_TIMESTAMP"])[:19], "%Y-%m-%d %H:%M:%S") >= cutoff
    ]

    if not cust_txns:
        return _empty_profile(customer_id, days)

    amounts = [float(t["AMOUNT"]) for t in cust_txns]
    n = len(amounts)
    mean_amt = sum(amounts) / n
    std_dev = math.sqrt(sum((a - mean_amt) ** 2 for a in amounts) / n) if n > 1 else 0

    # Daily spending
    daily_spend = defaultdict(float)
    for t in cust_txns:
        day_key = str(t["TXN_TIMESTAMP"])[:10]
        daily_spend[day_key] += float(t["AMOUNT"])

    active_days = len(daily_spend) or 1
    avg_daily = sum(daily_spend.values()) / active_days
    avg_monthly = avg_daily * 30

    # Channel preferences
    channel_counts = Counter(t.get("CHANNEL", "UPI") for t in cust_txns)
    top_channels = [ch for ch, _ in channel_counts.most_common(3)]

    # Device preferences
    device_counts = Counter(t.get("DEVICE_ID", "") for t in cust_txns if t.get("DEVICE_ID"))
    top_devices = [d for d, _ in device_counts.most_common(2)]

    # Location preferences
    location_counts = Counter(t.get("MERCHANT_CITY", "") for t in cust_txns if t.get("MERCHANT_CITY"))
    top_locations = [loc for loc, _ in location_counts.most_common(3)]

    # Merchant category preferences
    merchant_counts = Counter(t.get("MERCHANT_ID", "") for t in cust_txns if t.get("MERCHANT_ID"))
    top_merchants = [m for m, _ in merchant_counts.most_common(5)]

    # Frequency
    txn_per_day = n / active_days

    return {
        "PROFILE_ID": generate_uuid(),
        "CUSTOMER_ID": customer_id,
        "AVG_TXN_AMOUNT": round(mean_amt, 2),
        "MAX_TXN_AMOUNT": round(max(amounts), 2),
        "STD_DEV_AMOUNT": round(std_dev, 2),
        "AVG_DAILY_SPEND": round(avg_daily, 2),
        "AVG_MONTHLY_SPEND": round(avg_monthly, 2),
        "TXN_FREQUENCY_DAILY": round(txn_per_day, 4),
        "PREFERRED_CHANNELS": top_channels,
        "PREFERRED_DEVICES": top_devices,
        "TYPICAL_LOCATIONS": top_locations,
        "MERCHANT_PREFERENCES": top_merchants,
        "TOTAL_TRANSACTIONS": n,
        "PROFILE_PERIOD_DAYS": days,
        "COMPUTED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _empty_profile(customer_id: str, days: int) -> Dict[str, Any]:
    """Return an empty profile for customers with no transaction history."""
    return {
        "PROFILE_ID": generate_uuid(),
        "CUSTOMER_ID": customer_id,
        "AVG_TXN_AMOUNT": 0, "MAX_TXN_AMOUNT": 0, "STD_DEV_AMOUNT": 0,
        "AVG_DAILY_SPEND": 0, "AVG_MONTHLY_SPEND": 0, "TXN_FREQUENCY_DAILY": 0,
        "PREFERRED_CHANNELS": [], "PREFERRED_DEVICES": [],
        "TYPICAL_LOCATIONS": [], "MERCHANT_PREFERENCES": [],
        "TOTAL_TRANSACTIONS": 0, "PROFILE_PERIOD_DAYS": days,
        "COMPUTED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def compute_amount_zscore(amount: float, profile: Dict[str, Any]) -> float:
    """
    Calculate how anomalous a transaction amount is for this customer.

    Business owner scenario:
      Customer A: avg_daily=1Cr, std=20L → ₹50L → z=1.5 → LOW
      Customer B: avg_daily=50K, std=10K → ₹50L → z=49.5 → CRITICAL
    """
    avg = profile.get("AVG_TXN_AMOUNT", 0)
    std = profile.get("STD_DEV_AMOUNT", 1)
    if std == 0:
        std = max(avg * 0.1, 1)  # Use 10% of mean as fallback
    return abs(amount - avg) / std


def compute_velocity_zscore(
    customer_id: str,
    recent_txns: List[Dict[str, Any]],
    profile: Dict[str, Any],
    window_hours: int = 1,
) -> float:
    """Calculate how anomalous the current transaction velocity is."""
    now = datetime.now()
    window_start = now - timedelta(hours=window_hours)

    recent_count = sum(
        1 for t in recent_txns
        if t.get("CUSTOMER_ID") == customer_id
        and datetime.strptime(str(t["TXN_TIMESTAMP"])[:19], "%Y-%m-%d %H:%M:%S") >= window_start
    )

    expected_hourly = profile.get("TXN_FREQUENCY_DAILY", 1) / 24
    if expected_hourly < 0.01:
        expected_hourly = 0.01

    return recent_count / expected_hourly


def build_all_profiles(
    customers: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    days: int = 180,
) -> List[Dict[str, Any]]:
    """Build behavioral profiles for all customers."""
    logger.info(f"Building behavioral profiles for {len(customers)} customers...")

    # Pre-group transactions by customer for performance
    txn_by_cust = defaultdict(list)
    for t in transactions:
        txn_by_cust[t.get("CUSTOMER_ID", "")].append(t)

    profiles = []
    for cust in customers:
        cid = cust["CUSTOMER_ID"]
        cust_txns = txn_by_cust.get(cid, [])
        profile = build_customer_profile(cid, cust_txns, days)
        profiles.append(profile)

    logger.info(f"Built {len(profiles)} behavioral profiles.")
    return profiles


def insert_profiles_to_snowflake(profiles: List[Dict[str, Any]], connection) -> int:
    """Insert profiles into Snowflake ANALYTICS.CUSTOMER_BEHAVIOR_PROFILE."""
    insert_sql = """
        INSERT INTO CASEPILOT_DB.ANALYTICS.CUSTOMER_BEHAVIOR_PROFILE (
            PROFILE_ID, CUSTOMER_ID, AVG_TXN_AMOUNT, MAX_TXN_AMOUNT,
            STD_DEV_AMOUNT, AVG_DAILY_SPEND, AVG_MONTHLY_SPEND,
            TXN_FREQUENCY_DAILY, PREFERRED_CHANNELS, PREFERRED_DEVICES,
            TYPICAL_LOCATIONS, MERCHANT_PREFERENCES, TOTAL_TRANSACTIONS,
            PROFILE_PERIOD_DAYS, COMPUTED_AT
        )
        SELECT %s, %s, %s, %s, %s, %s, %s, %s,
               PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s),
               %s, %s, %s
    """
    cursor = connection.get_connection().cursor()
    total = 0
    try:
        for p in profiles:
            cursor.execute(insert_sql, (
                p["PROFILE_ID"], p["CUSTOMER_ID"],
                p["AVG_TXN_AMOUNT"], p["MAX_TXN_AMOUNT"], p["STD_DEV_AMOUNT"],
                p["AVG_DAILY_SPEND"], p["AVG_MONTHLY_SPEND"], p["TXN_FREQUENCY_DAILY"],
                json.dumps(p["PREFERRED_CHANNELS"]), json.dumps(p["PREFERRED_DEVICES"]),
                json.dumps(p["TYPICAL_LOCATIONS"]), json.dumps(p["MERCHANT_PREFERENCES"]),
                p["TOTAL_TRANSACTIONS"], p["PROFILE_PERIOD_DAYS"], p["COMPUTED_AT"],
            ))
            total += 1
    finally:
        cursor.close()

    logger.info(f"Inserted {total} behavioral profiles into Snowflake.")
    return total

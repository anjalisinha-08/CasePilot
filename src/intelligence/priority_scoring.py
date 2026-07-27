"""
CasePilot 2.0 — Priority Scoring Engine
==========================================
Calculates a priority score (0-100) for each case using the upgraded
10-dimension risk weights.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

from src.config.settings import SCORING_WEIGHTS, RISK_BANDS, SEVERITY_SCORES
from src.utils.helpers import clamp, safe_divide

logger = logging.getLogger(__name__)


def _score_alert_severity(alert: Dict[str, Any]) -> float:
    severity = alert.get("SEVERITY", "MEDIUM")
    return SEVERITY_SCORES.get(severity, 50)


def _score_amount_deviation(alert: Dict[str, Any], historical_stats: Dict[str, Any]) -> float:
    amount = float(alert.get("TRIGGERED_AMOUNT", 0) or 0.0)
    avg = float(historical_stats.get("avg_transaction_amount", 0) or 0.0)
    std = float(historical_stats.get("std_dev_amount", 1) or 1.0)
    if std == 0:
        std = max(avg * 0.1, 1.0)
    z_score = abs(amount - avg) / std
    return clamp(z_score * 20, 0, 100)


def _score_customer_risk(customer_profile: Dict[str, Any]) -> float:
    risk_rating = customer_profile.get("risk_rating", "LOW")
    base_score = {"LOW": 15, "MEDIUM": 45, "HIGH": 75, "CRITICAL": 95}.get(risk_rating, 30)

    kyc_status = customer_profile.get("kyc_status", "VERIFIED")
    if kyc_status == "EXPIRED":
        base_score += 20
    elif kyc_status == "PENDING":
        base_score += 10

    account_age = customer_profile.get("account_age_days", 365)
    if account_age < 30:
        base_score += 15
    elif account_age < 90:
        base_score += 8

    return clamp(base_score)


def _score_previous_alerts(previous_alerts: List[Dict[str, Any]]) -> float:
    count = len(previous_alerts)
    if count == 0:
        return 10
    weighted_sum = sum(
        {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(a.get("severity", "MEDIUM"), 2)
        for a in previous_alerts
    )
    return clamp(weighted_sum / 20 * 100, 0, 100)


def _score_device_trust(device_history: List[Dict[str, Any]]) -> float:
    if not device_history:
        return 40
    untrusted_count = sum(1 for d in device_history if not d.get("is_trusted", True))
    untrusted_ratio = safe_divide(untrusted_count, len(device_history))
    return clamp(untrusted_ratio * 80 + 10)


def _score_time_anomaly(alert: Dict[str, Any]) -> float:
    alert_type = alert.get("ALERT_TYPE", "")
    if alert_type == "ODD_HOUR_ACTIVITY":
        return 90
    created_at = alert.get("CREATED_AT", "")
    try:
        dt = datetime.strptime(str(created_at)[:19], "%Y-%m-%d %H:%M:%S")
        hour = dt.hour
        if 0 <= hour < 4:
            return 80
        elif 4 <= hour < 6:
            return 45
        else:
            return 10
    except Exception:
        return 20


def _score_geo_anomaly(alert: Dict[str, Any], txn_history: Dict[str, Any]) -> float:
    alert_type = alert.get("ALERT_TYPE", "")
    if alert_type == "FOREIGN_ACTIVITY":
        return 90
    
    intl_ratio = float(txn_history.get("international_txn_ratio", 0.0) if isinstance(txn_history, dict) else 0.0)
    if intl_ratio > 0.3:
        return 50
    elif intl_ratio > 0:
        return 30
    return 5


def _score_velocity_risk(txn_history: Dict[str, Any]) -> float:
    recent = txn_history.get("recent_transactions", []) if isinstance(txn_history, dict) else []
    # If customer has a high volume of transactions recently
    if len(recent) >= 8:
        return 85
    elif len(recent) >= 5:
        return 60
    elif len(recent) >= 3:
        return 30
    return 10


def _score_channel_anomaly(alert: Dict[str, Any], txn_history: Dict[str, Any]) -> float:
    # If the alert is from a channel not normally used
    if not isinstance(txn_history, dict):
        return 20
    dist = txn_history.get("channel_distribution", {})
    if not dist:
        return 10
    
    # Simple check: find the description and see the channel of the trigger
    desc = alert.get("ALERT_DESCRIPTION", "")
    channel_detected = "UPI"
    for ch in ["UPI", "IMPS", "NEFT", "RTGS", "POS", "ATM", "ONLINE_BANKING"]:
        if ch in desc:
            channel_detected = ch
            break
            
    if channel_detected not in dist:
        return 75
    return 10


def _score_merchant_risk(enrichment: Dict[str, Any]) -> float:
    m_history = enrichment.get("MERCHANT_HISTORY", [])
    if not m_history:
        return 15
    # Check if they have interacted with high-risk merchants
    high_risk_interactions = sum(1 for m in m_history if m.get("risk_level") == "HIGH")
    if high_risk_interactions >= 2:
        return 90
    elif high_risk_interactions == 1:
        return 50
    return 5


def calculate_priority_score(
    alert: Dict[str, Any],
    enrichment: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate the composite 10-dimension priority score."""
    customer_profile = enrichment.get("CUSTOMER_PROFILE", {})
    txn_history = enrichment.get("TXN_HISTORY", {})
    device_history = enrichment.get("DEVICE_HISTORY", [])
    previous_alerts = enrichment.get("PREVIOUS_ALERTS", [])
    historical_stats = enrichment.get("HISTORICAL_STATS", {})

    factors = {
        "alert_severity": _score_alert_severity(alert),
        "amount_deviation": _score_amount_deviation(alert, historical_stats),
        "customer_risk": _score_customer_risk(customer_profile),
        "previous_alerts": _score_previous_alerts(previous_alerts),
        "device_trust": _score_device_trust(device_history),
        "time_anomaly": _score_time_anomaly(alert),
        "geo_anomaly": _score_geo_anomaly(alert, historical_stats),
        "velocity_risk": _score_velocity_risk(txn_history),
        "channel_anomaly": _score_channel_anomaly(alert, txn_history),
        "merchant_risk": _score_merchant_risk(enrichment),
    }

    composite = sum(
        factors[factor] * weight
        for factor, weight in SCORING_WEIGHTS.items()
    )
    priority_score = round(clamp(composite), 2)

    risk_band = "LOW"
    for band, (low, high) in RISK_BANDS.items():
        if low <= priority_score <= high:
            risk_band = band
            break

    return {
        "priority_score": priority_score,
        "risk_band": risk_band,
        "factor_scores": factors,
        "weights": SCORING_WEIGHTS,
    }


def score_all_cases(
    cases: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    enrichments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    alert_map = {a["ALERT_ID"]: a for a in alerts}
    enrichment_map = {e["CASE_ID"]: e for e in enrichments}

    results = []
    for case in cases:
        alert = alert_map.get(case["ALERT_ID"], {})
        enrichment = enrichment_map.get(case["CASE_ID"], {})

        score_result = calculate_priority_score(alert, enrichment)
        score_result["CASE_ID"] = case["CASE_ID"]
        score_result["ALERT_ID"] = case["ALERT_ID"]
        results.append(score_result)

    band_counts = {}
    for r in results:
        b = r["risk_band"]
        band_counts[b] = band_counts.get(b, 0) + 1
    logger.info(f"Scored {len(results)} cases with 10-dimension model. Risk bands: {band_counts}")

    return results

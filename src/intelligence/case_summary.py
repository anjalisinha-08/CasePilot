"""
CasePilot — Case Summary & Intelligence Generator
=====================================================
Generates investigation-ready intelligence for each case:
  - Investigation summary (narrative text)
  - Recommendations (actionable next steps)
  - Timeline (chronological event sequence)
  - Key findings

All outputs are stored in ANALYTICS.CASE_INTELLIGENCE.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any

from src.utils.helpers import generate_uuid, format_currency

logger = logging.getLogger(__name__)


# ===========================================================================
# RECOMMENDATION TEMPLATES
# ===========================================================================

RECOMMENDATIONS_BY_TYPE = {
    "HIGH_VALUE_TXN": [
        "Verify transaction authorization with the account holder via registered phone",
        "Cross-check merchant legitimacy and transaction history",
        "Review account balance changes in the past 24 hours",
        "Check if the customer has a pattern of high-value transactions",
        "Verify source of funds for transactions above ₹50,000",
    ],
    "ODD_HOUR_ACTIVITY": [
        "Contact customer to confirm awareness of the transaction",
        "Check if the device used matches the customer's known devices",
        "Review IP address and geolocation for anomalies",
        "Compare transaction pattern with customer's typical activity hours",
        "Check for any concurrent login sessions from different locations",
    ],
    "NEW_DEVICE_USED": [
        "Verify device ownership with the customer",
        "Check if the device IP matches known customer locations",
        "Review if other accounts have been accessed from this device",
        "Implement step-up authentication for future transactions",
        "Flag device for monitoring over the next 30 days",
    ],
    "RAPID_TXN_BURST": [
        "Review all transactions in the burst window for patterns",
        "Check if transactions target the same or related merchants",
        "Verify if the customer initiated the transactions",
        "Assess if this is consistent with the customer's business profile",
        "Monitor account for additional burst activity in the next 48 hours",
    ],
    "FOREIGN_ACTIVITY": [
        "Verify customer's travel plans or international business activity",
        "Cross-reference transaction location with customer's known travel history",
        "Check if the customer informed the bank about international travel",
        "Review the merchant's risk profile in the foreign jurisdiction",
        "Monitor for additional foreign transactions in the next 72 hours",
    ],
}

RECOMMENDATIONS_BY_BAND = {
    "CRITICAL": [
        "URGENT: Escalate to senior investigation team immediately",
        "Consider temporary account hold pending investigation",
        "Initiate SAR (Suspicious Activity Report) preparation",
    ],
    "HIGH": [
        "Prioritize for same-day investigation",
        "Request additional documentation from customer",
        "Set up enhanced monitoring on the account",
    ],
    "MEDIUM": [
        "Schedule for investigation within 48 hours",
        "Review with standard investigation checklist",
    ],
    "LOW": [
        "Queue for routine review",
        "Monitor for repeat patterns before escalating",
    ],
}


def _generate_summary(
    alert: Dict[str, Any],
    enrichment: Dict[str, Any],
    score_result: Dict[str, Any],
) -> str:
    """
    Generate a human-readable investigation summary.

    Combines alert details, customer context, and scoring into
    a narrative that helps investigators quickly understand the case.
    """
    customer = enrichment.get("CUSTOMER_PROFILE", {})
    stats = enrichment.get("HISTORICAL_STATS", {})
    prev_alerts = enrichment.get("PREVIOUS_ALERTS", [])

    alert_type = alert.get("ALERT_TYPE", "UNKNOWN")
    severity = alert.get("SEVERITY", "MEDIUM")
    amount = alert.get("TRIGGERED_AMOUNT", 0) or 0
    risk_band = score_result.get("risk_band", "MEDIUM")
    score = score_result.get("priority_score", 50)

    cust_name = customer.get("name", "Unknown Customer")
    persona = customer.get("persona", "Unknown")
    city = customer.get("city", "Unknown")
    income = customer.get("annual_income", 0)
    kyc = customer.get("kyc_status", "Unknown")
    account_age = customer.get("account_age_days", 0)
    avg_txn = stats.get("avg_transaction_amount", 0)
    total_txns = stats.get("total_transactions", 0)

    # Build narrative
    summary_parts = []

    # Opening
    summary_parts.append(
        f"INVESTIGATION SUMMARY — {risk_band} PRIORITY (Score: {score}/100)"
    )
    summary_parts.append("")

    # Alert description
    summary_parts.append(
        f"Alert Type: {alert_type.replace('_', ' ').title()} | Severity: {severity}"
    )
    summary_parts.append(f"Triggered Amount: {format_currency(amount)}")
    summary_parts.append("")

    # Customer context
    summary_parts.append(f"Customer: {cust_name} ({persona.replace('_', ' ').title()})")
    summary_parts.append(f"Location: {city} | Annual Income: {format_currency(income)}")
    summary_parts.append(f"KYC Status: {kyc} | Account Age: {account_age} days")
    summary_parts.append("")

    # Behavioral analysis
    summary_parts.append("BEHAVIORAL ANALYSIS:")
    summary_parts.append(f"• Average transaction amount: {format_currency(avg_txn)}")
    if amount > 0 and avg_txn > 0:
        deviation = ((amount - avg_txn) / avg_txn) * 100
        summary_parts.append(f"• Current transaction deviates {deviation:+.1f}% from average")
    summary_parts.append(f"• Total transactions on record: {total_txns}")
    summary_parts.append(f"• Previous alerts: {len(prev_alerts)}")

    if prev_alerts:
        prev_types = set(a.get("alert_type", "") for a in prev_alerts)
        summary_parts.append(f"• Previous alert types: {', '.join(prev_types)}")

    summary_parts.append("")

    # Risk assessment
    factors = score_result.get("factor_scores", {})
    top_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)[:3]
    summary_parts.append("TOP RISK FACTORS:")
    for factor, score_val in top_factors:
        summary_parts.append(f"• {factor.replace('_', ' ').title()}: {score_val:.0f}/100")

    return "\n".join(summary_parts)


def _generate_recommendations(
    alert: Dict[str, Any],
    score_result: Dict[str, Any],
) -> List[str]:
    """Generate actionable recommendations based on alert type and risk band."""
    alert_type = alert.get("ALERT_TYPE", "HIGH_VALUE_TXN")
    risk_band = score_result.get("risk_band", "MEDIUM")

    recommendations = []

    # Type-specific recommendations
    type_recs = RECOMMENDATIONS_BY_TYPE.get(alert_type, [])
    recommendations.extend(type_recs[:3])

    # Band-specific recommendations
    band_recs = RECOMMENDATIONS_BY_BAND.get(risk_band, [])
    recommendations.extend(band_recs)

    return recommendations


def _generate_timeline(
    alert: Dict[str, Any],
    enrichment: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build a chronological timeline of events related to the case."""
    timeline = []
    customer = enrichment.get("CUSTOMER_PROFILE", {})
    txn_history = enrichment.get("TXN_HISTORY", {})
    prev_alerts = enrichment.get("PREVIOUS_ALERTS", [])

    # Account creation
    account_age = customer.get("account_age_days", 0)
    if account_age > 0:
        timeline.append({
            "timestamp": f"-{account_age} days",
            "event": "Account Created",
            "description": f"Customer {customer.get('name', 'Unknown')} account opened",
            "type": "ACCOUNT",
        })

    # Previous alerts (last 5)
    for prev in sorted(prev_alerts, key=lambda x: x.get("created_at", ""))[-5:]:
        timeline.append({
            "timestamp": prev.get("created_at", "Unknown"),
            "event": f"Previous Alert: {prev.get('alert_type', 'Unknown')}",
            "description": prev.get("description", "")[:150],
            "type": "ALERT",
        })

    # Recent transactions (last 5)
    recent_txns = txn_history.get("recent_transactions", [])[-5:]
    for txn in recent_txns:
        timeline.append({
            "timestamp": txn.get("timestamp", "Unknown"),
            "event": f"Transaction: {format_currency(txn.get('amount', 0))}",
            "description": f"{txn.get('channel', '')} - {txn.get('description', '')}",
            "type": "TRANSACTION",
        })

    # Current alert
    timeline.append({
        "timestamp": alert.get("CREATED_AT", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "event": f"ALERT TRIGGERED: {alert.get('ALERT_TYPE', 'Unknown')}",
        "description": alert.get("ALERT_DESCRIPTION", "")[:200],
        "type": "CURRENT_ALERT",
    })

    # Case created
    timeline.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": "Investigation Case Created",
        "description": "Automated case creation by CasePilot",
        "type": "CASE",
    })

    # Sort by timestamp where possible
    return timeline


def _generate_key_findings(
    alert: Dict[str, Any],
    enrichment: Dict[str, Any],
    score_result: Dict[str, Any],
) -> List[str]:
    """Generate key findings that summarize the most important observations."""
    findings = []
    customer = enrichment.get("CUSTOMER_PROFILE", {})
    stats = enrichment.get("HISTORICAL_STATS", {})
    prev_alerts = enrichment.get("PREVIOUS_ALERTS", [])
    amount = alert.get("TRIGGERED_AMOUNT", 0) or 0
    avg = stats.get("avg_transaction_amount", 0)

    if amount > 0 and avg > 0 and amount > avg * 3:
        findings.append(f"Transaction amount is {amount/avg:.1f}x the customer's average")

    if len(prev_alerts) > 3:
        findings.append(f"Customer has {len(prev_alerts)} previous alerts — repeat offender pattern")

    if customer.get("kyc_status") != "VERIFIED":
        findings.append(f"KYC status is {customer.get('kyc_status', 'Unknown')} — requires verification")

    if customer.get("account_age_days", 365) < 90:
        findings.append("Account is less than 90 days old — new account risk")

    if stats.get("international_txn_ratio", 0) > 0.2:
        findings.append("High international transaction ratio detected")

    if alert.get("ALERT_TYPE") == "RAPID_TXN_BURST":
        findings.append("Multiple transactions in rapid succession — potential automated activity")

    if not findings:
        findings.append("No exceptional patterns detected beyond the triggering alert")

    return findings


def generate_intelligence(
    cases: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    enrichments: List[Dict[str, Any]],
    score_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Generate complete case intelligence for all cases.

    Combines priority scoring with narrative summaries, recommendations,
    timelines, and key findings to create investigation-ready intelligence.

    Args:
        cases: Investigation case records.
        alerts: Alert records.
        enrichments: Case enrichment records.
        score_results: Priority scoring results.

    Returns:
        List of case intelligence dictionaries.
    """
    logger.info(f"Generating intelligence for {len(cases)} cases...")

    alert_map = {a["ALERT_ID"]: a for a in alerts}
    enrichment_map = {e["CASE_ID"]: e for e in enrichments}
    score_map = {s["CASE_ID"]: s for s in score_results}

    intelligence_records = []

    for case in cases:
        alert = alert_map.get(case["ALERT_ID"], {})
        enrichment = enrichment_map.get(case["CASE_ID"], {})
        score_result = score_map.get(case["CASE_ID"], {
            "priority_score": 50, "risk_band": "MEDIUM", "factor_scores": {}
        })

        summary = _generate_summary(alert, enrichment, score_result)
        recommendations = _generate_recommendations(alert, score_result)
        timeline = _generate_timeline(alert, enrichment)
        key_findings = _generate_key_findings(alert, enrichment, score_result)

        intelligence_records.append({
            "INTELLIGENCE_ID": generate_uuid(),
            "CASE_ID": case["CASE_ID"],
            "ALERT_ID": case["ALERT_ID"],
            "PRIORITY_SCORE": score_result["priority_score"],
            "RISK_BAND": score_result["risk_band"],
            "INVESTIGATION_SUMMARY": summary,
            "RECOMMENDATIONS": recommendations,
            "TIMELINE": timeline,
            "KEY_FINDINGS": key_findings,
            "MODEL_VERSION": "1.0",
            "GENERATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Log distribution
    band_counts = {}
    for i in intelligence_records:
        b = i["RISK_BAND"]
        band_counts[b] = band_counts.get(b, 0) + 1
    logger.info(f"Generated intelligence for {len(intelligence_records)} cases. Bands: {band_counts}")

    return intelligence_records


def insert_intelligence_to_snowflake(intelligence: List[Dict[str, Any]], connection) -> int:
    """Insert intelligence into Snowflake ANALYTICS.CASE_INTELLIGENCE table."""
    connection.use_schema("ANALYTICS")

    insert_query = """
    INSERT INTO CASE_INTELLIGENCE (
        INTELLIGENCE_ID,
        CASE_ID,
        ALERT_ID,
        PRIORITY_SCORE,
        RISK_BAND,
        INVESTIGATION_SUMMARY,
        RECOMMENDATIONS,
        TIMELINE,
        KEY_FINDINGS,
        MODEL_VERSION,
        GENERATED_AT
    )
    SELECT
        %s,
        %s,
        %s,
        %s,
        %s,
        %s,
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        PARSE_JSON(%s),
        %s,
        %s
    """

    data = [
        (
            i["INTELLIGENCE_ID"],
            i["CASE_ID"],
            i["ALERT_ID"],
            i["PRIORITY_SCORE"],
            i["RISK_BAND"],
            i["INVESTIGATION_SUMMARY"],
            json.dumps(i["RECOMMENDATIONS"]),
            json.dumps(i["TIMELINE"]),
            json.dumps(i["KEY_FINDINGS"]),
            i["MODEL_VERSION"],
            i["GENERATED_AT"],
        )
        for i in intelligence
    ]

    conn = connection.get_connection()
    cursor = conn.cursor()

    total = 0

    try:
        for row in data:
            cursor.execute(insert_query, row)
            total += 1

        conn.commit()

    finally:
        cursor.close()

    logger.info(f"Inserted {total} intelligence records into Snowflake.")
    return total
    data = [
        (
            i["INTELLIGENCE_ID"], i["CASE_ID"], i["ALERT_ID"],
            i["PRIORITY_SCORE"], i["RISK_BAND"], i["INVESTIGATION_SUMMARY"],
            json.dumps(i["RECOMMENDATIONS"]), json.dumps(i["TIMELINE"]),
            json.dumps(i["KEY_FINDINGS"]), i["MODEL_VERSION"],
            i["GENERATED_AT"],
        )
        for i in intelligence
    ]

    from src.utils.helpers import chunk_list
    total = 0
    for chunk in chunk_list(data, 500):
        total += connection.execute_many(insert_query, chunk)

    logger.info(f"Inserted {total} intelligence records into Snowflake.")
    return total

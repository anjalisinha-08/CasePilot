"""
CasePilot — Case Generator
=============================
Automatically creates investigation cases for every alert.
Each case gets a unique case number, status tracking, and team assignment.

This module works in batch mode (processing all alerts at once)
or can be called incrementally as new alerts arrive.
"""

import random
import logging
from datetime import datetime
from typing import List, Dict, Any

from src.config.settings import INVESTIGATION_TEAMS, ALERTS_REQUIRING_REVIEW
from src.utils.helpers import generate_uuid, generate_case_number

logger = logging.getLogger(__name__)


def _assign_team(alert_type: str) -> tuple:
    """
    Assign an investigation team and analyst based on alert type.

    Args:
        alert_type: Type of alert (e.g., HIGH_VALUE_TXN).

    Returns:
        Tuple of (team_name, analyst_name).
    """
    # Route alerts to specialized teams
    team_routing = {
        "HIGH_VALUE_TXN": "TEAM_ALPHA",
        "ODD_HOUR_ACTIVITY": "TEAM_ALPHA",
        "NEW_DEVICE_USED": "TEAM_BETA",
        "RAPID_TXN_BURST": "TEAM_BETA",
        "FOREIGN_ACTIVITY": "TEAM_GAMMA",
    }

    team_name = team_routing.get(alert_type, "TEAM_ALPHA")
    team_config = INVESTIGATION_TEAMS.get(team_name, INVESTIGATION_TEAMS["TEAM_ALPHA"])
    analyst = random.choice(team_config["analysts"])

    return team_name, analyst


def _determine_initial_priority(severity: str) -> str:
    """Map alert severity to initial case priority."""
    return severity  # Initially mirrors alert severity; refined by priority scoring later


def generate_cases(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Create investigation cases from alerts.

    Only alerts with severity in ALERTS_REQUIRING_REVIEW generate cases.
    Cases are assigned to investigation teams based on alert type specialization.

    Args:
        alerts: List of alert records.

    Returns:
        List of investigation case dictionaries.
    """
    cases = []
    case_numbers_used = set()

    for alert in alerts:
        # Check if the alert requires manual review
        severity = alert.get("SEVERITY", "MEDIUM")
        if severity not in ALERTS_REQUIRING_REVIEW:
            continue

        # Generate unique case number
        case_number = generate_case_number()
        while case_number in case_numbers_used:
            case_number = generate_case_number()
        case_numbers_used.add(case_number)

        team_name, analyst = _assign_team(alert["ALERT_TYPE"])
        priority = _determine_initial_priority(severity)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cases.append({
            "CASE_ID": generate_uuid(),
            "ALERT_ID": alert["ALERT_ID"],
            "CUSTOMER_ID": alert["CUSTOMER_ID"],
            "ACCOUNT_ID": alert["ACCOUNT_ID"],
            "CASE_NUMBER": case_number,
            "CASE_STATUS": "NEW",  # Start with status NEW as requested
            "ASSIGNED_TO": analyst,
            "ASSIGNED_TEAM": team_name,
            "PRIORITY": priority,
            "CREATED_AT": now,
            "UPDATED_AT": now,
            "CLOSED_AT": None,
            "CLOSURE_REASON": None,
        })

    # Log summary
    team_counts = {}
    for c in cases:
        t = c["ASSIGNED_TEAM"]
        team_counts[t] = team_counts.get(t, 0) + 1
    logger.info(f"Generated {len(cases)} investigation cases. Teams: {team_counts}")

    return cases


def insert_cases_to_snowflake(cases: List[Dict[str, Any]], connection) -> int:
    """Insert cases into Snowflake INVESTIGATION.INVESTIGATION_CASE table."""
    connection.use_schema("INVESTIGATION")

    insert_query = """
        INSERT INTO INVESTIGATION_CASE (
            CASE_ID, ALERT_ID, CUSTOMER_ID, ACCOUNT_ID, CASE_NUMBER,
            CASE_STATUS, ASSIGNED_TO, ASSIGNED_TEAM, PRIORITY,
            CREATED_AT, UPDATED_AT, CLOSED_AT, CLOSURE_REASON
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    data = [
        (
            c["CASE_ID"], c["ALERT_ID"], c["CUSTOMER_ID"], c["ACCOUNT_ID"],
            c["CASE_NUMBER"], c["CASE_STATUS"], c["ASSIGNED_TO"],
            c["ASSIGNED_TEAM"], c["PRIORITY"], c["CREATED_AT"],
            c["UPDATED_AT"], c["CLOSED_AT"], c["CLOSURE_REASON"],
        )
        for c in cases
    ]

    from src.utils.helpers import chunk_list
    total = 0
    for chunk in chunk_list(data, 500):
        total += connection.execute_many(insert_query, chunk)

    logger.info(f"Inserted {total} cases into Snowflake.")
    return total

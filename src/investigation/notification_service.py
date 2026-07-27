"""
CasePilot 2.0 — Customer Notification Service
=================================================
Manages customer notification workflows for suspicious/fraudulent alerts.
Sends simulated PUSH, SMS, or EMAIL and updates alert scores/case status
based on simulated customer response (YES = fraud, NO = legitimate).
"""

import logging
import random
from datetime import datetime
from typing import Dict, Any, List

from src.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)


def create_notification(
    customer_profile: Dict[str, Any],
    alert: Dict[str, Any],
    case_id: str = None,
) -> Dict[str, Any]:
    """
    Create a simulated customer notification payload.

    Args:
        customer_profile: Enriched profile of the customer.
        alert: Generated alert.
        case_id: Associated case ID.

    Returns:
        Notification dict.
    """
    notif_id = generate_uuid()
    channels = ["PUSH", "SMS", "EMAIL"]
    channel = random.choices(channels, weights=[0.60, 0.30, 0.10], k=1)[0]

    cust_name = customer_profile.get("name", "Customer")
    amount = float(alert.get("TRIGGERED_AMOUNT") or 0.0)

    # Contextual message
    message = (
        f"Hi {cust_name}, did you authorize a transaction of Rs. {amount:,.2f} "
        f"via {alert.get('ALERT_TYPE', 'transaction')}? Reply YES to confirm "
        f"it was you, or NO if this is unauthorized/fraud."
    )

    return {
        "NOTIFICATION_ID": notif_id,
        "CUSTOMER_ID": alert["CUSTOMER_ID"],
        "ALERT_ID": alert["ALERT_ID"],
        "CASE_ID": case_id,
        "MESSAGE": message,
        "CHANNEL": channel,
        "STATUS": "SENT",
        "CUSTOMER_RESPONSE": None,
        "SENT_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "RESPONDED_AT": None,
        "RESPONSE_ACTION": None,
    }


def simulate_customer_response(
    notification: Dict[str, Any],
    ground_truth_is_fraud: bool,
) -> Dict[str, Any]:
    """
    Simulate a customer response.
    - If the transaction is genuinely fraud, the customer is highly likely to respond 'NO' (not authorized).
    - If legitimate, the customer is highly likely to respond 'YES' (authorized).
    - Some customers might ignore the notification (remain unanswered/SENT status).
    """
    response_chance = random.random()
    notif = notification.copy()

    if response_chance < 0.15:
        # 15% chance: No response
        notif["STATUS"] = "SENT"
        notif["CUSTOMER_RESPONSE"] = None
        return notif

    # Customer responds
    notif["STATUS"] = "RESPONDED"
    notif["RESPONDED_AT"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # If it is fraud (ground truth), response should be NO (unauthorized)
    # If not fraud, response should be YES (authorized)
    # Give a small 5% margin for error (customer confusion/misclick)
    if ground_truth_is_fraud:
        response = "NO" if random.random() < 0.95 else "YES"
    else:
        response = "YES" if random.random() < 0.95 else "NO"

    notif["CUSTOMER_RESPONSE"] = response

    # Action based on response
    if response == "YES":
        # Authorized! Clean, reduce risk
        notif["RESPONSE_ACTION"] = "REDUCE_RISK_CLOSE_CASE"
    else:
        # Fraud! Escalation required
        notif["RESPONSE_ACTION"] = "INCREASE_RISK_ESCALATE"

    return notif


def process_response_action(
    notif: Dict[str, Any],
    connection,
) -> bool:
    """
    Update tables in Snowflake based on customer response.
    Follows AML Banking Workflow lifecycle.
    """
    action = notif.get("RESPONSE_ACTION")
    case_id = notif.get("CASE_ID")
    alert_id = notif.get("ALERT_ID")

    if not action or not case_id or not alert_id:
        return False

    cursor = connection.get_connection().cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if action == "REDUCE_RISK_CLOSE_CASE":
            # 1. Update Case to CUSTOMER_VERIFIED
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'CUSTOMER_VERIFIED',
                    PRIORITY = 'LOW',
                    UPDATED_AT = '{now_str}'
                WHERE CASE_ID = '{case_id}'
            """)
            # 2. Transition Case to FALSE_POSITIVE and close it
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'FALSE_POSITIVE',
                    CLOSED_AT = '{now_str}',
                    CLOSURE_REASON = 'Customer confirmed transaction was authorized.'
                WHERE CASE_ID = '{case_id}'
            """)
            # Update Alert
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.ALERTS.ALERT
                SET STATUS = 'RESOLVED',
                    UPDATED_AT = '{now_str}'
                WHERE ALERT_ID = '{alert_id}'
            """)
            # Update Intelligence
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE
                SET PRIORITY_SCORE = 5.0,
                    RISK_BAND = 'LOW',
                    GENERATED_AT = '{now_str}'
                WHERE CASE_ID = '{case_id}'
            """)
            logger.info(f"Resolved Case {case_id[:8]} (False Positive - customer verified).")

        elif action == "INCREASE_RISK_ESCALATE":
            # 1. Update Case to FRAUD_CONFIRMED
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'FRAUD_CONFIRMED',
                    PRIORITY = 'CRITICAL',
                    UPDATED_AT = '{now_str}'
                WHERE CASE_ID = '{case_id}'
            """)
            # Update Alert
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.ALERTS.ALERT
                SET STATUS = 'ESCALATED',
                    UPDATED_AT = '{now_str}'
                WHERE ALERT_ID = '{alert_id}'
            """)
            # Update Intelligence
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE
                SET PRIORITY_SCORE = 100.0,
                    RISK_BAND = 'CRITICAL',
                    GENERATED_AT = '{now_str}'
                WHERE CASE_ID = '{case_id}'
            """)
            
            # 2. Freeze Account: Transition Case to ACCOUNT_FROZEN & Update RAW.ACCOUNT
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.RAW.ACCOUNT
                SET ACCOUNT_STATUS = 'FROZEN',
                    UPDATED_AT = '{now_str}'
                WHERE ACCOUNT_ID = (
                    SELECT ACCOUNT_ID FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE WHERE CASE_ID = '{case_id}'
                )
            """)
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'ACCOUNT_FROZEN',
                    UPDATED_AT = '{now_str}'
                WHERE CASE_ID = '{case_id}'
            """)
            logger.info(f"Frozen Account for Case {case_id[:8]} (Fraud confirmed).")

            # 3. Create Fraud Recovery record & check status
            cursor.execute(f"""
                SELECT CUSTOMER_ID, TRIGGERED_AMOUNT 
                FROM CASEPILOT_DB.ALERTS.ALERT 
                WHERE ALERT_ID = '{alert_id}'
            """)
            row = cursor.fetchone()
            if row:
                cust_id, fraud_amt = row[0], float(row[1])
                rec = create_fraud_recovery(case_id, cust_id, fraud_amt, connection)
                
                # 4. If recovered amount > 0, transition to MONEY_RECOVERED
                if rec.get("RECOVERED_AMOUNT", 0.0) > 0.0:
                    cursor.execute(f"""
                        UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                        SET CASE_STATUS = 'MONEY_RECOVERED',
                            UPDATED_AT = '{now_str}'
                        WHERE CASE_ID = '{case_id}'
                    """)
            
            # 5. Final transition to CLOSED
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'CLOSED',
                    CLOSED_AT = '{now_str}',
                    CLOSURE_REASON = 'Fraud investigation complete. Account frozen and recovery processed.'
                WHERE CASE_ID = '{case_id}'
            """)
            logger.info(f"Closed Case {case_id[:8]} after full workflow execution.")

        connection.get_connection().commit()
        return True
    except Exception as e:
        logger.error(f"Error processing response action for case {case_id}: {e}")
        return False
    finally:
        cursor.close()


def insert_notification_to_snowflake(notif: Dict[str, Any], connection) -> int:
    """Insert notification log record into INVESTIGATION.NOTIFICATION_LOG."""
    insert_sql = """
        INSERT INTO CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG (
            NOTIFICATION_ID, CUSTOMER_ID, ALERT_ID, CASE_ID, MESSAGE,
            CHANNEL, STATUS, CUSTOMER_RESPONSE, SENT_AT, RESPONDED_AT, RESPONSE_ACTION
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor = connection.get_connection().cursor()
    try:
        cursor.execute(insert_sql, (
            notif["NOTIFICATION_ID"], notif["CUSTOMER_ID"],
            notif["ALERT_ID"], notif["CASE_ID"], notif["MESSAGE"],
            notif["CHANNEL"], notif["STATUS"], notif["CUSTOMER_RESPONSE"],
            notif["SENT_AT"], notif["RESPONDED_AT"], notif["RESPONSE_ACTION"]
        ))
        connection.get_connection().commit()
    finally:
        cursor.close()
    return 1


def create_fraud_recovery(case_id: str, customer_id: str, fraud_amount: float, connection) -> Dict[str, Any]:
    """Create and insert a fraud recovery record in Snowflake."""
    import random
    from src.utils.helpers import generate_uuid
    
    # 70% chance of partial or complete recovery, 30% chance of 0 recovery/failed/pending
    recovery_chance = random.random()
    if recovery_chance < 0.30:
        recovered_amount = 0.00
        status = "FAILED" if random.random() < 0.5 else "PENDING"
    elif recovery_chance < 0.85:
        # Partial recovery (between 10% and 90%)
        recovered_amount = round(fraud_amount * random.uniform(0.10, 0.90), 2)
        status = "PARTIAL"
    else:
        # Full recovery!
        recovered_amount = fraud_amount
        status = "COMPLETED"
        
    recovery_methods = ["CHARGEBACK", "INSURANCE_CLAIM", "ACCOUNT_REVERSAL", "FUNDS_FREEZE"]
    method = random.choice(recovery_methods) if recovered_amount > 0 else None
    
    rec_id = generate_uuid()
    insert_sql = """
        INSERT INTO CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY (
            RECOVERY_ID, CASE_ID, CUSTOMER_ID, FRAUD_AMOUNT, RECOVERED_AMOUNT,
            RECOVERY_STATUS, RECOVERY_METHOD, UPDATED_AT
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
    """
    
    cursor = connection.get_connection().cursor()
    try:
        cursor.execute(insert_sql, (
            rec_id, case_id, customer_id, fraud_amount, recovered_amount, status, method
        ))
        connection.get_connection().commit()
    finally:
        cursor.close()
        
    return {
        "RECOVERY_ID": rec_id,
        "CASE_ID": case_id,
        "CUSTOMER_ID": customer_id,
        "FRAUD_AMOUNT": fraud_amount,
        "RECOVERED_AMOUNT": recovered_amount,
        "RECOVERY_STATUS": status,
        "RECOVERY_METHOD": method,
    }


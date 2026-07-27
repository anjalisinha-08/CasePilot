"""
CasePilot 2.0 — Real-Time Data Simulator & Pipeline Runner
=============================================================
Runs continuously to:
  1. Generate 1-10 new transactions every 60 seconds (with 15% fraud probability)
  2. Insert into RAW.TRANSACTION
  3. Run fraud scorer and trigger alert rules
  4. Create investigation cases, enrichments, and intelligence
  5. Generate customer notifications, simulate customer replies, and act on responses
  6. Compute and store model metrics in Snowflake
"""

import os
import sys
import time
import json
import random
import logging
from datetime import datetime, timedelta

# Add root folder to sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.snowflake_connection import SnowflakeConnection
from src.config.settings import FRAUD_CONFIG, SIMULATION
from src.utils.helpers import setup_logging, generate_uuid
from src.simulator.transaction_generator import generate_transactions, insert_transactions_to_snowflake
from src.alerts.alert_engine import run_alert_engine, insert_alerts_to_snowflake
from src.investigation.case_generator import generate_cases, insert_cases_to_snowflake
from src.investigation.case_enrichment import enrich_cases, insert_enrichments_to_snowflake
from src.intelligence.priority_scoring import calculate_priority_score
from src.intelligence.case_summary import generate_intelligence, insert_intelligence_to_snowflake
from src.intelligence.behavioral_profiler import build_customer_profile
from src.intelligence.fraud_scorer import score_transaction
from src.intelligence.model_evaluator import evaluate_model, insert_metrics_to_snowflake
from src.investigation.notification_service import create_notification, simulate_customer_response, process_response_action, insert_notification_to_snowflake

logger = logging.getLogger(__name__)


def _fetch_active_entities(conn) -> tuple:
    """Fetch active customers, accounts, merchants, and devices from Snowflake."""
    # Fetch Customers in pages of 200
    cust_rows = []
    limit = 200
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT CUSTOMER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE, PERSONA, CITY, STATE, COUNTRY, OCCUPATION, ANNUAL_INCOME, RISK_RATING, KYC_STATUS, CREATED_AT, IS_ACTIVE 
            FROM RAW.CUSTOMER 
            WHERE IS_ACTIVE=TRUE
            ORDER BY CUSTOMER_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        cust_rows.extend(rows)
        offset += limit

    # Fetch Accounts in pages of 200
    acct_rows = []
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_TYPE, BALANCE, CURRENCY, ACCOUNT_STATUS, OPENED_AT, ACCOUNT_NUMBER, IFSC_CODE 
            FROM RAW.ACCOUNT 
            WHERE ACCOUNT_STATUS='ACTIVE'
            ORDER BY ACCOUNT_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        acct_rows.extend(rows)
        offset += limit

    # Fetch Merchants in pages of 200
    merch_rows = []
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT MERCHANT_ID, MERCHANT_NAME, CATEGORY, RISK_LEVEL, CITY, COUNTRY 
            FROM RAW.MERCHANT 
            WHERE IS_ACTIVE=TRUE
            ORDER BY MERCHANT_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        merch_rows.extend(rows)
        offset += limit

    # Fetch Devices in pages of 200
    dev_rows = []
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT DEVICE_ID, CUSTOMER_ID, DEVICE_TYPE, DEVICE_NAME, OS, BROWSER, IP_ADDRESS, CITY, COUNTRY, IS_TRUSTED, FIRST_SEEN, LAST_SEEN 
            FROM RAW.DEVICE
            ORDER BY DEVICE_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        dev_rows.extend(rows)
        offset += limit

    customers = [
        {
            "CUSTOMER_ID": r[0], "FIRST_NAME": r[1], "LAST_NAME": r[2], "EMAIL": r[3], "PHONE": r[4], 
            "PERSONA": r[5], "CITY": r[6], "STATE": r[7], "COUNTRY": r[8], "OCCUPATION": r[9], 
            "ANNUAL_INCOME": float(r[10]), "RISK_RATING": r[11], "KYC_STATUS": r[12], 
            "CREATED_AT": r[13].strftime("%Y-%m-%d %H:%M:%S") if hasattr(r[13], "strftime") else str(r[13]), 
            "IS_ACTIVE": r[14]
        }
        for r in cust_rows
    ]
    accounts = [
        {"ACCOUNT_ID": r[0], "CUSTOMER_ID": r[1], "ACCOUNT_TYPE": r[2], "BALANCE": float(r[3]), "CURRENCY": r[4],
         "ACCOUNT_STATUS": r[5], "OPENED_AT": str(r[6]), "ACCOUNT_NUMBER": r[7], "IFSC_CODE": r[8]}
        for r in acct_rows
    ]
    merchants = [
        {"MERCHANT_ID": r[0], "MERCHANT_NAME": r[1], "CATEGORY": r[2], "RISK_LEVEL": r[3], "CITY": r[4], "COUNTRY": r[5]}
        for r in merch_rows
    ]
    devices = [
        {"DEVICE_ID": r[0], "CUSTOMER_ID": r[1], "DEVICE_TYPE": r[2], "DEVICE_NAME": r[3], "OS": r[4], "BROWSER": r[5], 
         "IP_ADDRESS": r[6], "CITY": r[7], "COUNTRY": r[8], "IS_TRUSTED": bool(r[9]), "FIRST_SEEN": str(r[10]), "LAST_SEEN": str(r[11])}
        for r in dev_rows
    ]

    return customers, accounts, merchants, devices


def _fetch_behavioral_profiles(conn) -> dict:
    """Fetch customer behavioral profiles from Snowflake and index by CUSTOMER_ID."""
    rows = conn.execute_query("""
        SELECT CUSTOMER_ID, AVG_TXN_AMOUNT, MAX_TXN_AMOUNT, STD_DEV_AMOUNT, 
               AVG_DAILY_SPEND, AVG_MONTHLY_SPEND, TXN_FREQUENCY_DAILY, 
               PREFERRED_CHANNELS, PREFERRED_DEVICES, TYPICAL_LOCATIONS, 
               MERCHANT_PREFERENCES, TOTAL_TRANSACTIONS, PROFILE_PERIOD_DAYS
        FROM CASEPILOT_DB.ANALYTICS.CUSTOMER_BEHAVIOR_PROFILE
    """)
    profiles = {}
    for r in rows:
        cid = r[0]
        def parse_json_field(val):
            if val is None:
                return []
            if isinstance(val, (list, dict)):
                return val
            try:
                return json.loads(val)
            except Exception:
                return []

        profiles[cid] = {
            "CUSTOMER_ID": cid,
            "AVG_TXN_AMOUNT": float(r[1]) if r[1] is not None else 0.0,
            "MAX_TXN_AMOUNT": float(r[2]) if r[2] is not None else 0.0,
            "STD_DEV_AMOUNT": float(r[3]) if r[3] is not None else 1.0,
            "AVG_DAILY_SPEND": float(r[4]) if r[4] is not None else 0.0,
            "AVG_MONTHLY_SPEND": float(r[5]) if r[5] is not None else 0.0,
            "TXN_FREQUENCY_DAILY": float(r[6]) if r[6] is not None else 0.0,
            "PREFERRED_CHANNELS": parse_json_field(r[7]),
            "PREFERRED_DEVICES": parse_json_field(r[8]),
            "TYPICAL_LOCATIONS": parse_json_field(r[9]),
            "MERCHANT_PREFERENCES": parse_json_field(r[10]),
            "TOTAL_TRANSACTIONS": int(r[11]) if r[11] is not None else 0,
            "PROFILE_PERIOD_DAYS": int(r[12]) if r[12] is not None else 180
        }
    return profiles


def run_one_iteration(conn, customers, accounts, merchants, devices, all_txns_cache, profile_map, alert_counts, cust_risk_map, device_map, merchant_map):
    """Run a single iteration of real-time simulation (transactions -> alerts -> cases -> notification)."""
    # 1. Generate 1-10 transactions
    txn_count = random.randint(1, 10)
    # 15% chance of containing fraud
    is_fraud_batch = random.random() < FRAUD_CONFIG["fraud_probability"]
    
    # Temporarily override configuration for batch generation
    prev_ratio = SIMULATION["suspicious_ratio"]
    SIMULATION["suspicious_ratio"] = 0.40 if is_fraud_batch else 0.0
    
    logger.info(f"Generating {txn_count} new transactions (Fraud batch: {is_fraud_batch})...")
    txns = generate_transactions(customers, accounts, merchants, devices, count=txn_count)
    
    # Restore original ratio
    SIMULATION["suspicious_ratio"] = prev_ratio

    # Score and classify transactions in memory using the behavioral fraud engine
    for t in txns:
        cid = t["CUSTOMER_ID"]
        did = t.get("DEVICE_ID")
        mid = t.get("MERCHANT_ID")
        
        prof = profile_map.get(cid, {})
        dev = device_map.get(did) if did else None
        merch = merchant_map.get(mid) if mid else None
        risk = cust_risk_map.get(cid, "LOW")
        
        scored = score_transaction(
            transaction=t,
            profile=prof,
            device=dev,
            merchant=merch,
            recent_txns=None,
            alert_history_count=alert_counts.get(cid, 0),
            customer_risk_rating=risk
        )
        t["FRAUD_SCORE"] = float(scored["fraud_score"])
        t["CLASSIFICATION"] = scored["classification"]
        t["FRAUD_CONFIDENCE"] = float(scored["fraud_confidence"])
    
    # 2. Insert into Snowflake
    insert_transactions_to_snowflake(txns, conn)
    all_txns_cache.extend(txns)

    # 3. Score transactions and run Alert Engine
    logger.info("Evaluating transaction alerts & scoring...")
    raw_alerts = run_alert_engine(txns, devices, customers)
    
    # Filter alerts: only keep alerts for transactions classified as FRAUD_ALERT
    fraud_alert_txns = [t for t in txns if t["CLASSIFICATION"] == "FRAUD_ALERT"]
    fraud_alert_txn_ids = {t["TXN_ID"] for t in fraud_alert_txns}
    alerts = [a for a in raw_alerts if a["TXN_ID"] in fraud_alert_txn_ids]
    
    # For any transaction classified as FRAUD_ALERT that didn't trigger any rules, generate a default alert
    triggered_txn_ids = {a["TXN_ID"] for a in alerts}
    for t in fraud_alert_txns:
        if t["TXN_ID"] not in triggered_txn_ids:
            score = t["FRAUD_SCORE"]
            severity = "CRITICAL" if score >= 90 else ("HIGH" if score >= 80 else "MEDIUM")
            alert_type = t.get("FRAUD_TYPE", "BEHAVIORAL_FRAUD")
            if not alert_type or alert_type == "LEGITIMATE":
                alert_type = "BEHAVIORAL_FRAUD"
            desc = t.get("FRAUD_REASON", "High risk score based on behavioral anomaly patterns.")
            if not desc:
                desc = f"Behavioral fraud score of {score:.1f} exceeds alert threshold."
                
            default_alert = {
                "ALERT_ID": generate_uuid(),
                "TXN_ID": t["TXN_ID"],
                "ACCOUNT_ID": t["ACCOUNT_ID"],
                "CUSTOMER_ID": t["CUSTOMER_ID"],
                "ALERT_TYPE": alert_type,
                "ALERT_DESCRIPTION": desc,
                "SEVERITY": severity,
                "RULE_VERSION": "2.0",
                "TRIGGERED_AMOUNT": t["AMOUNT"],
                "TRIGGERED_THRESHOLD": 80.0,
                "STATUS": "NEW",
                "CREATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "UPDATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            alerts.append(default_alert)
            
    if not alerts:
        logger.info("No alerts triggered for this batch.")
        return

    # 4. Insert Alerts to Snowflake
    insert_alerts_to_snowflake(alerts, conn)
    for a in alerts:
        cid = a["CUSTOMER_ID"]
        alert_counts[cid] = alert_counts.get(cid, 0) + 1

    # 5. Generate Cases
    cases = generate_cases(alerts)
    insert_cases_to_snowflake(cases, conn)

    # 6. Enrich Cases
    enrichments = enrich_cases(cases, alerts, customers, accounts, all_txns_cache, merchants, devices)
    insert_enrichments_to_snowflake(enrichments, conn)

    # 7. Priority Scoring & Intelligence Narrative Generation
    score_results = []
    for c in cases:
        # Find matches
        matching_alert = next(a for a in alerts if a["ALERT_ID"] == c["ALERT_ID"])
        matching_enrichment = next(e for e in enrichments if e["CASE_ID"] == c["CASE_ID"])
        
        # Calculate composite score
        scr = calculate_priority_score(matching_alert, matching_enrichment)
        scr["CASE_ID"] = c["CASE_ID"]
        scr["ALERT_ID"] = c["ALERT_ID"]
        score_results.append(scr)

    intel = generate_intelligence(cases, alerts, enrichments, score_results)
    insert_intelligence_to_snowflake(intel, conn)

    # 8. Customer Notification loop (Initialize and contact customer)
    logger.info("Initializing customer notifications for new cases...")
    for c, a, e in zip(cases, alerts, enrichments):
        # Create notification
        notif = create_notification(e["CUSTOMER_PROFILE"], a, case_id=c["CASE_ID"])
        # Initially notification is SENT (pending customer response)
        insert_notification_to_snowflake(notif, conn)
        # Update case status to CUSTOMER_CONTACTED
        cursor = conn.get_connection().cursor()
        try:
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'CUSTOMER_CONTACTED',
                    UPDATED_AT = CURRENT_TIMESTAMP()
                WHERE CASE_ID = '{c["CASE_ID"]}'
            """)
            conn.get_connection().commit()
        finally:
            cursor.close()

    # 9. Simulate customer replies for older pending notifications
    logger.info("Simulating customer replies for older pending notifications...")
    cursor = conn.get_connection().cursor()
    try:
        # Fetch up to 3 notifications that are still pending response (STATUS = 'SENT')
        cursor.execute("""
            SELECT 
                n.NOTIFICATION_ID, n.CUSTOMER_ID, n.ALERT_ID, n.CASE_ID, n.MESSAGE, 
                n.CHANNEL, n.STATUS, t.IS_FRAUD
            FROM CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG n
            JOIN CASEPILOT_DB.ALERTS.ALERT a ON n.ALERT_ID = a.ALERT_ID
            JOIN CASEPILOT_DB.RAW.TRANSACTION t ON a.TXN_ID = t.TXN_ID
            WHERE n.STATUS = 'SENT'
            ORDER BY n.SENT_AT ASC
            LIMIT 3
        """)
        rows = cursor.fetchall()
        for r in rows:
            notif = {
                "NOTIFICATION_ID": r[0],
                "CUSTOMER_ID": r[1],
                "ALERT_ID": r[2],
                "CASE_ID": r[3],
                "MESSAGE": r[4],
                "CHANNEL": r[5],
                "STATUS": r[6],
                "CUSTOMER_RESPONSE": None,
                "SENT_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "RESPONDED_AT": None,
                "RESPONSE_ACTION": None,
            }
            is_fraud = bool(r[7])
            # Simulate reply
            notif_response = simulate_customer_response(notif, is_fraud)
            if notif_response["STATUS"] == "RESPONDED":
                # Update notification status in Snowflake
                cursor.execute("""
                    UPDATE CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG
                    SET STATUS = %s,
                        CUSTOMER_RESPONSE = %s,
                        RESPONDED_AT = %s,
                        RESPONSE_ACTION = %s
                    WHERE NOTIFICATION_ID = %s
                """, (
                    notif_response["STATUS"],
                    notif_response["CUSTOMER_RESPONSE"],
                    notif_response["RESPONDED_AT"],
                    notif_response["RESPONSE_ACTION"],
                    notif_response["NOTIFICATION_ID"]
                ))
                conn.get_connection().commit()
                # Process the response actions (update case status, freeze account, create recovery record, close case)
                process_response_action(notif_response, conn)
    except Exception as ex:
        logger.error(f"Error simulating pending responses: {ex}")
    finally:
        cursor.close()


def run_evaluation_metrics(conn, all_txns_cache, profile_map, device_map, merchant_map):
    """Run model evaluation against all accumulated transactions and log metrics."""
    logger.info("Running overall model performance evaluation...")
    if not all_txns_cache:
        return
        
    predictions = []
    
    # Evaluate latest 1,000 transactions for performance metrics
    eval_txns = all_txns_cache[-1000:]
    for t in eval_txns:
        cid = t["CUSTOMER_ID"]
        prof = profile_map.get(cid, {})
        dev = device_map.get(t.get("DEVICE_ID"), None)
        merch = merchant_map.get(t.get("MERCHANT_ID"), None)

        score_res = score_transaction(t, prof, device=dev, merchant=merch)
        predictions.append({
            "is_fraud": t.get("IS_FRAUD", False),
            "is_predicted_fraud": score_res["is_predicted_fraud"]
        })

    eval_result = evaluate_model(predictions)
    insert_metrics_to_snowflake(eval_result, conn)


def main():
    setup_logging(level=logging.INFO)
    logger.info("=" * 60)
    logger.info("🛡️ CasePilot 2.0 Real-Time Pipeline Simulator Started")
    logger.info("=" * 60)

    conn = SnowflakeConnection()
    conn.connect()

    # Load initial active entities
    logger.info("Fetching master metadata from Snowflake...")
    customers, accounts, merchants, devices = _fetch_active_entities(conn)
    logger.info(f"Loaded: {len(customers):,} Customers, {len(accounts):,} Accounts, {len(merchants):,} Merchants, {len(devices):,} Devices.")

    # Cache transaction history in memory to speed up simulation runs
    logger.info("Loading recent transactions for context baseline...")
    all_txns_cache = []
    limit = 100
    for offset in range(0, 1000, limit):
        rows = conn.execute_query(f"""
            SELECT TXN_ID, ACCOUNT_ID, CUSTOMER_ID, MERCHANT_ID, DEVICE_ID, AMOUNT,
                   CURRENCY, TXN_TYPE, CHANNEL, STATUS, TXN_TIMESTAMP, DESCRIPTION,
                   MERCHANT_CITY, MERCHANT_COUNTRY, IS_INTERNATIONAL, IS_FRAUD, FRAUD_TYPE,
                   FRAUD_REASON, FRAUD_CONFIDENCE
            FROM RAW.TRANSACTION
            ORDER BY TXN_TIMESTAMP DESC
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        all_txns_cache.extend([
            {
                "TXN_ID": r[0], "ACCOUNT_ID": r[1], "CUSTOMER_ID": r[2], "MERCHANT_ID": r[3], "DEVICE_ID": r[4],
                "AMOUNT": float(r[5]), "CURRENCY": r[6], "TXN_TYPE": r[7], "CHANNEL": r[8], "STATUS": r[9],
                "TXN_TIMESTAMP": str(r[10]), "DESCRIPTION": r[11], "MERCHANT_CITY": r[12], "MERCHANT_COUNTRY": r[13],
                "IS_INTERNATIONAL": bool(r[14]), "IS_FRAUD": bool(r[15]), "FRAUD_TYPE": r[16],
                "FRAUD_REASON": r[17], "FRAUD_CONFIDENCE": float(r[18]) if r[18] else 0.0
            }
            for r in rows
        ])
    # Reverse to keep chronological
    all_txns_cache.reverse()
    logger.info(f"Cached {len(all_txns_cache):,} historical transactions.")

    # Build maps for in-memory scoring
    device_map = {d["DEVICE_ID"]: d for d in devices}
    merchant_map = {m["MERCHANT_ID"]: m for m in merchants}
    cust_risk_map = {c["CUSTOMER_ID"]: c.get("RISK_RATING", "LOW") for c in customers}

    # Fetch initial customer alert history count
    logger.info("Fetching alert history counts...")
    alert_counts = {c["CUSTOMER_ID"]: 0 for c in customers}
    rows = conn.execute_query("SELECT CUSTOMER_ID, COUNT(*) FROM CASEPILOT_DB.ALERTS.ALERT GROUP BY CUSTOMER_ID")
    if rows:
        for r in rows:
            if r[0] in alert_counts:
                alert_counts[r[0]] = int(r[1])

    # Fetch customer behavioral profiles from Snowflake
    logger.info("Loading customer behavioral profiles...")
    profile_map = _fetch_behavioral_profiles(conn)

    # For any customers without profile, create a default base profile
    for c in customers:
        cid = c["CUSTOMER_ID"]
        if cid not in profile_map:
            profile_map[cid] = {
                "CUSTOMER_ID": cid,
                "AVG_TXN_AMOUNT": 0.0,
                "MAX_TXN_AMOUNT": 0.0,
                "STD_DEV_AMOUNT": 1.0,
                "AVG_DAILY_SPEND": 0.0,
                "AVG_MONTHLY_SPEND": 0.0,
                "TXN_FREQUENCY_DAILY": 0.0,
                "PREFERRED_CHANNELS": ["UPI", "IMPS"],
                "PREFERRED_DEVICES": [d["DEVICE_ID"] for d in devices if d["CUSTOMER_ID"] == cid][:2],
                "TYPICAL_LOCATIONS": [c["CITY"]],
                "MERCHANT_PREFERENCES": [],
                "TOTAL_TRANSACTIONS": 0,
                "PROFILE_PERIOD_DAYS": 180
            }

    iter_count = 0
    try:
        while True:
            iter_count += 1
            logger.info(f"\n--- Iteration #{iter_count} starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
            
            # Execute transactional flow
            run_one_iteration(
                conn, customers, accounts, merchants, devices, all_txns_cache,
                profile_map, alert_counts, cust_risk_map, device_map, merchant_map
            )

            # Periodically evaluate performance metrics (every 5 runs)
            if iter_count % 5 == 1:
                run_evaluation_metrics(conn, all_txns_cache, profile_map, device_map, merchant_map)

            logger.info("Iteration complete. Sleeping for 60 seconds...")
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("\n🛑 Real-Time Pipeline Runner stopped by user.")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()

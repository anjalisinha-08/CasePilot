import logging
import sys
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

PROJECT_ROOT = "/Users/anjali.sinha/Documents/GitHub/CasePilot"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.snowflake_connection import SnowflakeConnection
from src.config.settings import SIMULATION, ALERT_RULES
from src.simulator.customer_generator import generate_customers, insert_customers_to_snowflake
from src.simulator.account_generator import generate_accounts, insert_accounts_to_snowflake
from src.simulator.merchant_generator import generate_merchants, insert_merchants_to_snowflake
from src.simulator.device_generator import generate_devices, insert_devices_to_snowflake
from src.simulator.transaction_generator import generate_transactions
from src.intelligence.behavioral_profiler import build_all_profiles
from src.intelligence.fraud_scorer import score_transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Fast Direct SQL Insertion Helpers ---

def fast_insert_profiles(profiles: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("ANALYTICS")
    cursor = connection.get_connection().cursor()
    try:
        batch_size = 100
        for i in range(0, len(profiles), batch_size):
            chunk = profiles[i:i+batch_size]
            select_parts = []
            params = []
            for p in chunk:
                select_parts.append("""
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s,
                           PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s),
                           %s, %s, %s
                """)
                params.extend([
                    p["PROFILE_ID"], p["CUSTOMER_ID"],
                    p["AVG_TXN_AMOUNT"], p["MAX_TXN_AMOUNT"], p["STD_DEV_AMOUNT"],
                    p["AVG_DAILY_SPEND"], p["AVG_MONTHLY_SPEND"], p["TXN_FREQUENCY_DAILY"],
                    json.dumps(p["PREFERRED_CHANNELS"]), json.dumps(p["PREFERRED_DEVICES"]),
                    json.dumps(p["TYPICAL_LOCATIONS"]), json.dumps(p["MERCHANT_PREFERENCES"]),
                    p["TOTAL_TRANSACTIONS"], p["PROFILE_PERIOD_DAYS"], p["COMPUTED_AT"]
                ])
            query = f"""
                INSERT INTO CUSTOMER_BEHAVIOR_PROFILE (
                    PROFILE_ID, CUSTOMER_ID, AVG_TXN_AMOUNT, MAX_TXN_AMOUNT,
                    STD_DEV_AMOUNT, AVG_DAILY_SPEND, AVG_MONTHLY_SPEND,
                    TXN_FREQUENCY_DAILY, PREFERRED_CHANNELS, PREFERRED_DEVICES,
                    TYPICAL_LOCATIONS, MERCHANT_PREFERENCES, TOTAL_TRANSACTIONS,
                    PROFILE_PERIOD_DAYS, COMPUTED_AT
                ) {" UNION ALL ".join(select_parts)}
            """
            cursor.execute(query, params)
        connection.get_connection().commit()
    finally:
        cursor.close()
    return len(profiles)

def fast_insert_transactions(transactions: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("RAW")
    cursor = connection.get_connection().cursor()
    total_rows = 0
    try:
        batch_size = 2000
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
            if total_rows % 50000 == 0 or total_rows == len(transactions):
                logger.info(f"Uploaded {total_rows:,}/{len(transactions):,} transactions...")
        connection.get_connection().commit()
    finally:
        cursor.close()
    return total_rows

def fast_insert_alerts(alerts: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("ALERTS")
    cursor = connection.get_connection().cursor()
    try:
        batch_size = 2000
        for i in range(0, len(alerts), batch_size):
            chunk = alerts[i:i+batch_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
            query = f"""
                INSERT INTO ALERT (
                    ALERT_ID, TXN_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE,
                    ALERT_DESCRIPTION, SEVERITY, RULE_VERSION, TRIGGERED_AMOUNT,
                    TRIGGERED_THRESHOLD, STATUS, CREATED_AT, UPDATED_AT
                ) VALUES {placeholders}
            """
            params = []
            for a in chunk:
                params.extend([
                    a["ALERT_ID"], a["TXN_ID"], a["ACCOUNT_ID"], a["CUSTOMER_ID"],
                    a["ALERT_TYPE"], a["ALERT_DESCRIPTION"], a["SEVERITY"],
                    a["RULE_VERSION"], a["TRIGGERED_AMOUNT"], a["TRIGGERED_THRESHOLD"],
                    a["STATUS"], a["CREATED_AT"], a["UPDATED_AT"]
                ])
            cursor.execute(query, params)
        connection.get_connection().commit()
    finally:
        cursor.close()
    return len(alerts)

def fast_insert_cases(cases: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("INVESTIGATION")
    cursor = connection.get_connection().cursor()
    try:
        batch_size = 2000
        for i in range(0, len(cases), batch_size):
            chunk = cases[i:i+batch_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
            query = f"""
                INSERT INTO INVESTIGATION_CASE (
                    CASE_ID, ALERT_ID, CUSTOMER_ID, ACCOUNT_ID, CASE_NUMBER,
                    CASE_STATUS, ASSIGNED_TO, ASSIGNED_TEAM, PRIORITY,
                    CREATED_AT, UPDATED_AT, CLOSED_AT, CLOSURE_REASON
                ) VALUES {placeholders}
            """
            params = []
            for c in chunk:
                params.extend([
                    c["CASE_ID"], c["ALERT_ID"], c["CUSTOMER_ID"], c["ACCOUNT_ID"],
                    c["CASE_NUMBER"], c["CASE_STATUS"], c["ASSIGNED_TO"],
                    c["ASSIGNED_TEAM"], c["PRIORITY"], c["CREATED_AT"],
                    c["UPDATED_AT"], c["CLOSED_AT"], c["CLOSURE_REASON"]
                ])
            cursor.execute(query, params)
        connection.get_connection().commit()
    finally:
        cursor.close()
    return len(cases)

def fast_insert_notifications(notifications: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("INVESTIGATION")
    cursor = connection.get_connection().cursor()
    try:
        batch_size = 2000
        for i in range(0, len(notifications), batch_size):
            chunk = notifications[i:i+batch_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
            query = f"""
                INSERT INTO NOTIFICATION_LOG (
                    NOTIFICATION_ID, CUSTOMER_ID, ALERT_ID, CASE_ID, MESSAGE,
                    CHANNEL, STATUS, CUSTOMER_RESPONSE, SENT_AT, RESPONDED_AT, RESPONSE_ACTION
                ) VALUES {placeholders}
            """
            params = []
            for n in chunk:
                params.extend([
                    n["NOTIFICATION_ID"], n["CUSTOMER_ID"], n["ALERT_ID"], n["CASE_ID"],
                    n["MESSAGE"], n["CHANNEL"], n["STATUS"], n["CUSTOMER_RESPONSE"],
                    n["SENT_AT"], n["RESPONDED_AT"], n["RESPONSE_ACTION"]
                ])
            cursor.execute(query, params)
        connection.get_connection().commit()
    finally:
        cursor.close()
    return len(notifications)

def fast_insert_recoveries(recoveries: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("INVESTIGATION")
    cursor = connection.get_connection().cursor()
    try:
        batch_size = 2000
        for i in range(0, len(recoveries), batch_size):
            chunk = recoveries[i:i+batch_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())"] * len(chunk))
            query = f"""
                INSERT INTO FRAUD_RECOVERY (
                    RECOVERY_ID, CASE_ID, CUSTOMER_ID, FRAUD_AMOUNT, RECOVERED_AMOUNT,
                    RECOVERY_STATUS, RECOVERY_METHOD, UPDATED_AT
                ) VALUES {placeholders}
            """
            params = []
            for r in chunk:
                params.extend([
                    r["RECOVERY_ID"], r["CASE_ID"], r["CUSTOMER_ID"],
                    r["FRAUD_AMOUNT"], r["RECOVERED_AMOUNT"], r["RECOVERY_STATUS"],
                    r["RECOVERY_METHOD"]
                ])
            cursor.execute(query, params)
        connection.get_connection().commit()
    finally:
        cursor.close()
    return len(recoveries)

def fast_insert_enrichments(enrichments: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("INVESTIGATION")
    cursor = connection.get_connection().cursor()
    try:
        batch_size = 2000
        for i in range(0, len(enrichments), batch_size):
            chunk = enrichments[i:i+batch_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
            query = f"""
                INSERT INTO CASE_ENRICHMENT (
                    ENRICHMENT_ID, CASE_ID, CUSTOMER_PROFILE, ACCOUNT_PROFILE,
                    TXN_HISTORY, MERCHANT_HISTORY, DEVICE_HISTORY, PREVIOUS_ALERTS,
                    HISTORICAL_STATS, ENRICHED_AT
                )
                SELECT
                    column1, column2, PARSE_JSON(column3), PARSE_JSON(column4), PARSE_JSON(column5),
                    PARSE_JSON(column6), PARSE_JSON(column7), PARSE_JSON(column8), PARSE_JSON(column9), column10
                FROM VALUES {placeholders}
            """
            params = []
            for e in chunk:
                params.extend([
                    e["ENRICHMENT_ID"], e["CASE_ID"],
                    e["CUSTOMER_PROFILE"], e["ACCOUNT_PROFILE"], e["TXN_HISTORY"],
                    e["MERCHANT_HISTORY"], e["DEVICE_HISTORY"], e["PREVIOUS_ALERTS"],
                    e["HISTORICAL_STATS"], e["ENRICHED_AT"]
                ])
            cursor.execute(query, params)
        connection.get_connection().commit()
    finally:
        cursor.close()
    return len(enrichments)

def fast_insert_intelligence(intelligence: List[Dict[str, Any]], connection) -> int:
    connection.use_schema("ANALYTICS")
    cursor = connection.get_connection().cursor()
    try:
        batch_size = 2000
        for i in range(0, len(intelligence), batch_size):
            chunk = intelligence[i:i+batch_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
            query = f"""
                INSERT INTO CASE_INTELLIGENCE (
                    INTELLIGENCE_ID, CASE_ID, ALERT_ID, PRIORITY_SCORE, RISK_BAND,
                    INVESTIGATION_SUMMARY, RECOMMENDATIONS, TIMELINE, KEY_FINDINGS,
                    MODEL_VERSION, GENERATED_AT
                )
                SELECT
                    column1, column2, column3, column4, column5, column6, PARSE_JSON(column7), PARSE_JSON(column8), PARSE_JSON(column9), column10, column11
                FROM VALUES {placeholders}
            """
            params = []
            for intel in chunk:
                params.extend([
                    intel["INTELLIGENCE_ID"], intel["CASE_ID"], intel["ALERT_ID"],
                    intel["PRIORITY_SCORE"], intel["RISK_BAND"], intel["INVESTIGATION_SUMMARY"],
                    intel["RECOMMENDATIONS"], intel["TIMELINE"], intel["KEY_FINDINGS"],
                    intel["MODEL_VERSION"], intel["GENERATED_AT"]
                ])
            cursor.execute(query, params)
        connection.get_connection().commit()
    finally:
        cursor.close()
    return len(intelligence)

def main():
    conn = SnowflakeConnection()
    conn.connect()
    
    try:
        # 1. Truncate all tables to start clean
        logger.info("Truncating all database tables for a clean rebuild...")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.ANALYTICS.MODEL_METRICS")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.ANALYTICS.CUSTOMER_BEHAVIOR_PROFILE")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.INVESTIGATION.CASE_ENRICHMENT")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.ALERTS.ALERT")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.RAW.TRANSACTION")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.RAW.DEVICE")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.RAW.MERCHANT")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.RAW.ACCOUNT")
        conn.execute_non_query("TRUNCATE TABLE CASEPILOT_DB.RAW.CUSTOMER")
        logger.info("All tables truncated successfully.")

        # 2. Generate and Insert Master Entities
        logger.info("Generating 5,000 customers...")
        customers = generate_customers()
        insert_customers_to_snowflake(customers, conn)
        
        logger.info("Generating 10,000 accounts...")
        accounts = generate_accounts(customers)
        insert_accounts_to_snowflake(accounts, conn)
        
        logger.info("Generating 2,000 merchants...")
        merchants = generate_merchants()
        insert_merchants_to_snowflake(merchants, conn)
        
        logger.info("Generating 15,000 devices...")
        devices = generate_devices(customers)
        insert_devices_to_snowflake(devices, conn)

        # 3. Generate Transactions (500,000+)
        logger.info("Generating 500,000 transactions...")
        txns = generate_transactions(customers, accounts, merchants, devices)

        # 4. Build Customer Behavioral Profiles in memory
        logger.info("Computing customer behavioral profiles from transactions in memory...")
        profiles = build_all_profiles(customers, txns)
        fast_insert_profiles(profiles, conn)
        logger.info(f"Successfully uploaded {len(profiles):,} behavioral profiles.")

        # 5. Score and Classify all Transactions in memory
        logger.info("Scoring and classifying 500,000 transactions in memory...")
        profile_map = {p["CUSTOMER_ID"]: p for p in profiles}
        device_map = {d["DEVICE_ID"]: d for d in devices}
        merchant_map = {m["MERCHANT_ID"]: m for m in merchants}
        cust_risk_map = {c["CUSTOMER_ID"]: c.get("RISK_RATING", "LOW") for c in customers}
        alert_counts = {c["CUSTOMER_ID"]: 0 for c in customers}
        
        for idx, t in enumerate(txns):
            cid = t["CUSTOMER_ID"]
            did = t.get("DEVICE_ID")
            mid = t.get("MERCHANT_ID")
            
            p = profile_map.get(cid, {})
            d = device_map.get(did) if did else None
            m = merchant_map.get(mid) if mid else None
            risk = cust_risk_map.get(cid, "LOW")
            
            scored = score_transaction(
                transaction=t,
                profile=p,
                device=d,
                merchant=m,
                recent_txns=None,
                alert_history_count=alert_counts.get(cid, 0),
                customer_risk_rating=risk
            )
            
            t["FRAUD_SCORE"] = scored["risk_score"]
            t["CLASSIFICATION"] = scored["classification"]
            
            if scored["classification"] == "FRAUD_ALERT":
                alert_counts[cid] = alert_counts.get(cid, 0) + 1
            
            if (idx + 1) % 100000 == 0:
                logger.info(f"Scored {idx+1}/{len(txns)} transactions...")

        # 6. Bulk upload Transactions to Snowflake via SQL execute_many
        logger.info("Uploading scored transactions to Snowflake...")
        fast_insert_transactions(txns, conn)

        # 7. Generate Downstream Lifecycle Data (Alerts, Cases, Notifications, Responses, Recoveries, Intelligence)
        logger.info("Generating downstream lifecycle data for FRAUD_ALERT transactions...")
        alert_txns = [t for t in txns if t["CLASSIFICATION"] == "FRAUD_ALERT"]
        logger.info(f"Found {len(alert_txns):,} alert transactions ({len(alert_txns)/len(txns):.2%} of total).")

        alerts = []
        cases = []
        notifications = []
        recoveries = []
        enrichments = []
        intelligence_records = []
        
        now_str = datetime.now().strftime("%Y%m%d")
        
        # Collect accounts to freeze
        frozen_account_ids = set()
        
        for idx, t in enumerate(alert_txns):
            alert_id = str(uuid.uuid4())
            case_id = str(uuid.uuid4())
            notif_id = str(uuid.uuid4())
            
            score = t["FRAUD_SCORE"]
            severity = "CRITICAL" if score >= 80 else ("HIGH" if score >= 65 else "MEDIUM")
            
            if t["IS_FRAUD"]:
                alert_type = t.get("FRAUD_TYPE", "HIGH_VALUE_TXN")
                desc = t.get("FRAUD_REASON", "Suspicious transaction patterns detected.")
            else:
                alert_type = "HIGH_VALUE_TXN"
                desc = "Transaction exceeds customer baseline value."
                
            alert = {
                "ALERT_ID": alert_id,
                "TXN_ID": t["TXN_ID"],
                "ACCOUNT_ID": t["ACCOUNT_ID"],
                "CUSTOMER_ID": t["CUSTOMER_ID"],
                "ALERT_TYPE": alert_type,
                "ALERT_DESCRIPTION": desc,
                "SEVERITY": severity,
                "RULE_VERSION": "2.0",
                "TRIGGERED_AMOUNT": t["AMOUNT"],
                "TRIGGERED_THRESHOLD": 50000.00,
                "STATUS": "NEW",
                "CREATED_AT": t["TXN_TIMESTAMP"],
                "UPDATED_AT": t["TXN_TIMESTAMP"],
            }
            alerts.append(alert)
            
            # Only create cases for alerts requiring review
            if severity not in ["HIGH", "CRITICAL"]:
                continue
            
            response_channel = random.choice(["PUSH", "SMS", "EMAIL"])
            
            if t["IS_FRAUD"]:
                status_roll = random.random()
                if status_roll < 0.10:
                    case_status = "NEW"
                    notif_status = "SENT"
                    cust_response = None
                    response_action = None
                    closed_at = None
                    closure_reason = None
                elif status_roll < 0.20:
                    case_status = "UNDER_REVIEW"
                    notif_status = "SENT"
                    cust_response = None
                    response_action = None
                    closed_at = None
                    closure_reason = None
                elif status_roll < 0.30:
                    case_status = "CUSTOMER_CONTACTED"
                    notif_status = "SENT"
                    cust_response = None
                    response_action = None
                    closed_at = None
                    closure_reason = None
                elif status_roll < 0.50:
                    case_status = "FRAUD_CONFIRMED"
                    notif_status = "RESPONDED"
                    cust_response = "NO"
                    response_action = "INCREASE_RISK_ESCALATE"
                    closed_at = None
                    closure_reason = "Customer confirmed transaction was unauthorized/fraud."
                elif status_roll < 0.65:
                    case_status = "ACCOUNT_FROZEN"
                    notif_status = "RESPONDED"
                    cust_response = "NO"
                    response_action = "INCREASE_RISK_ESCALATE"
                    closed_at = None
                    closure_reason = "Customer confirmed transaction was unauthorized/fraud. Account frozen."
                    frozen_account_ids.add(t["ACCOUNT_ID"])
                elif status_roll < 0.90:
                    case_status = "MONEY_RECOVERED"
                    notif_status = "RESPONDED"
                    cust_response = "NO"
                    response_action = "INCREASE_RISK_ESCALATE"
                    closed_at = t["TXN_TIMESTAMP"]
                    closure_reason = "Customer confirmed transaction was unauthorized/fraud. Funds recovered."
                    frozen_account_ids.add(t["ACCOUNT_ID"])
                else:
                    case_status = "CLOSED"
                    notif_status = "RESPONDED"
                    cust_response = "NO"
                    response_action = "INCREASE_RISK_ESCALATE"
                    closed_at = t["TXN_TIMESTAMP"]
                    closure_reason = "Investigation finalized and closed."
                    frozen_account_ids.add(t["ACCOUNT_ID"])
            else:
                status_roll = random.random()
                if status_roll < 0.15:
                    case_status = "CUSTOMER_CONTACTED"
                    notif_status = "SENT"
                    cust_response = None
                    response_action = None
                    closed_at = None
                    closure_reason = None
                elif status_roll < 0.30:
                    case_status = "CUSTOMER_VERIFIED"
                    notif_status = "RESPONDED"
                    cust_response = "YES"
                    response_action = "REDUCE_RISK_CLOSE_CASE"
                    closed_at = None
                    closure_reason = "Customer verified transaction was authorized."
                else:
                    case_status = "FALSE_POSITIVE"
                    notif_status = "RESPONDED"
                    cust_response = "YES"
                    response_action = "REDUCE_RISK_CLOSE_CASE"
                    closed_at = t["TXN_TIMESTAMP"]
                    closure_reason = "Customer verified transaction was authorized."
            
            case_num = f"CP-{now_str}-{str(idx).zfill(6)}"
            case = {
                "CASE_ID": case_id,
                "ALERT_ID": alert_id,
                "CUSTOMER_ID": t["CUSTOMER_ID"],
                "ACCOUNT_ID": t["ACCOUNT_ID"],
                "CASE_NUMBER": case_num,
                "CASE_STATUS": case_status,
                "ASSIGNED_TO": random.choice(["Priya Sharma", "Rahul Verma", "Vikram Singh", "Neha Gupta"]),
                "ASSIGNED_TEAM": random.choice(["TEAM_ALPHA", "TEAM_BETA"]),
                "PRIORITY": "CRITICAL" if case_status in ("FRAUD_CONFIRMED", "ACCOUNT_FROZEN", "MONEY_RECOVERED") else ("LOW" if case_status in ("FALSE_POSITIVE", "CUSTOMER_VERIFIED") else severity),
                "CREATED_AT": t["TXN_TIMESTAMP"],
                "UPDATED_AT": t["TXN_TIMESTAMP"],
                "CLOSED_AT": closed_at,
                "CLOSURE_REASON": closure_reason,
            }
            cases.append(case)
            
            notif_msg = f"Hi, did you authorize a transaction of Rs. {t['AMOUNT']:,.2f} at {t['DESCRIPTION']}? Reply YES/NO."
            notif = {
                "NOTIFICATION_ID": notif_id,
                "CUSTOMER_ID": t["CUSTOMER_ID"],
                "ALERT_ID": alert_id,
                "CASE_ID": case_id,
                "MESSAGE": notif_msg,
                "CHANNEL": response_channel,
                "STATUS": notif_status,
                "CUSTOMER_RESPONSE": cust_response,
                "SENT_AT": t["TXN_TIMESTAMP"],
                "RESPONDED_AT": t["TXN_TIMESTAMP"] if notif_status == "RESPONDED" else None,
                "RESPONSE_ACTION": response_action,
            }
            notifications.append(notif)
            
            if case_status in ("MONEY_RECOVERED", "CLOSED") and t["IS_FRAUD"]:
                rec_id = str(uuid.uuid4())
                rec_chance = random.random()
                if rec_chance < 0.30:
                    recovered = 0.00
                    rec_status = "FAILED" if random.random() < 0.5 else "PENDING"
                elif rec_chance < 0.85:
                    recovered = round(t["AMOUNT"] * random.uniform(0.10, 0.90), 2)
                    rec_status = "PARTIAL"
                else:
                    recovered = t["AMOUNT"]
                    rec_status = "COMPLETED"
                    
                recovery = {
                    "RECOVERY_ID": rec_id,
                    "CASE_ID": case_id,
                    "CUSTOMER_ID": t["CUSTOMER_ID"],
                    "FRAUD_AMOUNT": t["AMOUNT"],
                    "RECOVERED_AMOUNT": recovered,
                    "RECOVERY_STATUS": rec_status,
                    "RECOVERY_METHOD": random.choice(["CHARGEBACK", "INSURANCE_CLAIM", "ACCOUNT_REVERSAL"]) if recovered > 0 else None,
                }
                recoveries.append(recovery)

            enrichment = {
                "ENRICHMENT_ID": str(uuid.uuid4()),
                "CASE_ID": case_id,
                "CUSTOMER_PROFILE": json.dumps({"customer_id": t["CUSTOMER_ID"], "risk_rating": risk}),
                "ACCOUNT_PROFILE": json.dumps({"account_id": t["ACCOUNT_ID"], "balance": 50000.0}),
                "TXN_HISTORY": json.dumps({"total_transactions": 50}),
                "MERCHANT_HISTORY": json.dumps({"merchant_id": t["MERCHANT_ID"]}),
                "DEVICE_HISTORY": json.dumps({"device_id": t.get("DEVICE_ID")}),
                "PREVIOUS_ALERTS": json.dumps({"alert_count": alert_counts[t["CUSTOMER_ID"]]}),
                "HISTORICAL_STATS": json.dumps({"avg_amount": 5000.0}),
                "ENRICHED_AT": t["TXN_TIMESTAMP"]
            }
            enrichments.append(enrichment)
            
            intel = {
                "INTELLIGENCE_ID": str(uuid.uuid4()),
                "CASE_ID": case_id,
                "ALERT_ID": alert_id,
                "PRIORITY_SCORE": 100.0 if case_status in ("FRAUD_CONFIRMED", "ACCOUNT_FROZEN", "MONEY_RECOVERED") else (5.0 if case_status in ("FALSE_POSITIVE", "CUSTOMER_VERIFIED") else score),
                "RISK_BAND": "CRITICAL" if case_status in ("FRAUD_CONFIRMED", "ACCOUNT_FROZEN", "MONEY_RECOVERED") else ("LOW" if case_status in ("FALSE_POSITIVE", "CUSTOMER_VERIFIED") else severity),
                "INVESTIGATION_SUMMARY": f"AI narrative for transaction alert at merchant category MCC. Recommended resolution is to block device/account.",
                "RECOMMENDATIONS": json.dumps(["BLOCK_ACCOUNT", "CONTACT_CUSTOMER"]),
                "TIMELINE": json.dumps([{"event": "alert_triggered", "time": t["TXN_TIMESTAMP"]}]),
                "KEY_FINDINGS": json.dumps({"amount_deviation": score}),
                "MODEL_VERSION": "2.0",
                "GENERATED_AT": t["TXN_TIMESTAMP"]
            }
            intelligence_records.append(intel)
            
        logger.info("Uploading downstream lifecycle data frames to Snowflake...")
        fast_insert_alerts(alerts, conn)
        fast_insert_cases(cases, conn)
        fast_insert_notifications(notifications, conn)
        if recoveries:
            fast_insert_recoveries(recoveries, conn)
        fast_insert_enrichments(enrichments, conn)
        fast_insert_intelligence(intelligence_records, conn)

        # Freeze the accounts that were labeled frozen in baseline seeding
        if frozen_account_ids:
            logger.info(f"Freezing {len(frozen_account_ids)} accounts in RAW.ACCOUNT...")
            cursor = conn.get_connection().cursor()
            try:
                ids_list = list(frozen_account_ids)
                batch_size = 500
                for i in range(0, len(ids_list), batch_size):
                    chunk_ids = ids_list[i:i+batch_size]
                    placeholders = ",".join(["%s"] * len(chunk_ids))
                    cursor.execute(f"""
                        UPDATE CASEPILOT_DB.RAW.ACCOUNT
                        SET ACCOUNT_STATUS = 'FROZEN'
                        WHERE ACCOUNT_ID IN ({placeholders})
                    """, chunk_ids)
                conn.get_connection().commit()
                logger.info("Successfully updated account statuses in Snowflake.")
            finally:
                cursor.close()

        # 8. Compute Model Classification Metrics
        logger.info("Calculating model evaluation metrics...")
        
        tp = sum(1 for t in txns if t["IS_FRAUD"] and t["CLASSIFICATION"] == "FRAUD_ALERT")
        fp = sum(1 for t in txns if not t["IS_FRAUD"] and t["CLASSIFICATION"] == "FRAUD_ALERT")
        tn = sum(1 for t in txns if not t["IS_FRAUD"] and t["CLASSIFICATION"] != "FRAUD_ALERT")
        fn = sum(1 for t in txns if t["IS_FRAUD"] and t["CLASSIFICATION"] != "FRAUD_ALERT")
        
        total = len(txns)
        accuracy = (tp + tn) / total if total > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        
        metrics = {
            "METRIC_ID": str(uuid.uuid4()),
            "RUN_ID": str(uuid.uuid4()),
            "MODEL_VERSION": "2.0",
            "TOTAL_PREDICTIONS": total,
            "TRUE_POSITIVES": tp,
            "TRUE_NEGATIVES": tn,
            "FALSE_POSITIVES": fp,
            "FALSE_NEGATIVES": fn,
            "ACCURACY": round(accuracy, 6),
            "PRECISION_SCORE": round(precision, 6),
            "RECALL": round(recall, 6),
            "F1_SCORE": round(f1, 6),
            "FALSE_POSITIVE_RATE": round(fpr, 6),
            "FALSE_NEGATIVE_RATE": round(fnr, 6),
            "EVALUATION_DETAILS": json.dumps({"timestamp": datetime.now().isoformat()}),
            "EVALUATED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Insert Metrics directly
        conn.use_schema("ANALYTICS")
        metrics_sql = """
            INSERT INTO MODEL_METRICS (
                METRIC_ID, RUN_ID, MODEL_VERSION, TOTAL_PREDICTIONS,
                TRUE_POSITIVES, TRUE_NEGATIVES, FALSE_POSITIVES, FALSE_NEGATIVES,
                ACCURACY, PRECISION_SCORE, RECALL, F1_SCORE,
                FALSE_POSITIVE_RATE, FALSE_NEGATIVE_RATE, EVALUATION_DETAILS, EVALUATED_AT
            ) SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), %s
        """
        cursor = conn.get_connection().cursor()
        try:
            cursor.execute(metrics_sql, (
                metrics["METRIC_ID"], metrics["RUN_ID"], metrics["MODEL_VERSION"], metrics["TOTAL_PREDICTIONS"],
                metrics["TRUE_POSITIVES"], metrics["TRUE_NEGATIVES"], metrics["FALSE_POSITIVES"], metrics["FALSE_NEGATIVES"],
                metrics["ACCURACY"], metrics["PRECISION_SCORE"], metrics["RECALL"], metrics["F1_SCORE"],
                metrics["FALSE_POSITIVE_RATE"], metrics["FALSE_NEGATIVE_RATE"], metrics["EVALUATION_DETAILS"], metrics["EVALUATED_AT"]
            ))
            conn.get_connection().commit()
        finally:
            cursor.close()
        
        logger.info("=" * 60)
        logger.info("🎉 SUCCESS: Baseline loaded successfully!")
        logger.info(f"Total Transactions: {total:,}")
        logger.info(f"Alerts (Predicted Fraud): {len(alert_txns):,}")
        logger.info(f"Actual Fraud (Ground Truth): {tp+fn:,}")
        logger.info(f"TP: {tp} | FP: {fp} | TN: {tn} | FN: {fn}")
        logger.info(f"Accuracy: {accuracy:.4f} | Precision: {precision:.4f} | Recall: {recall:.4f} | F1 Score: {f1:.4f}")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("An error occurred during pipeline baseline load:")
        raise e
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()

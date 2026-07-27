"""
CasePilot Dashboard — Snowflake Query Service
================================================
All Snowflake queries used by the dashboard are centralized here.
Uses the existing SnowflakeConnection from src.config.snowflake_connection.
"""

import os
import sys
import logging
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# Add project root to path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.snowflake_connection import SnowflakeConnection
import snowflake.connector.errors



@st.cache_resource
def get_sf_connection():
    """Get a cached Snowflake connection for the dashboard session."""
    conn = SnowflakeConnection()
    conn.connect()
    return conn


def _run_query(query: str) -> pd.DataFrame:
    """
    Execute a query and return a DataFrame.

    Automatically handles expired Snowflake auth tokens and network/SSL issues
    by clearing the cached connection, reconnecting, and retrying the query.
    """
    try:
        conn = get_sf_connection()
        return conn.execute_query_df(query)
    except Exception as e:
        error_msg = str(e)
        error_code = getattr(e, "errno", None)
        # 390114 = token expired, 250001 = connection closed/lost, or SSL/handshake/network error
        if (
            error_code in (390114, 250001)
            or "Authentication token has expired" in error_msg
            or "SSLError" in error_msg
            or "ECONNRESET" in error_msg
            or "bad handshake" in error_msg
        ):
            logger.warning(f"Connection/SSL issue detected ({e}), reconnecting and retrying query...")
            get_sf_connection.clear()
            conn = get_sf_connection()
            return conn.execute_query_df(query)
        raise



# ── Authentication Queries ───────────────────────────────────────────────────

def authenticate_user(employee_id: str, password_hash: str):
    """Authenticate a platform user by employee ID and password hash."""
    df = _run_query(f"""
        SELECT USER_ID, EMPLOYEE_ID, FULL_NAME, EMAIL, ROLE, DEPARTMENT, CUSTOMER_ID
        FROM CASEPILOT_DB.RAW.PLATFORM_USER
        WHERE EMPLOYEE_ID = '{employee_id}'
          AND PASSWORD_HASH = '{password_hash}'
          AND IS_ACTIVE = TRUE
    """)
    if df.empty:
        return None
    return df.iloc[0].to_dict()


# ── Operational KPI Queries ──────────────────────────────────────────────────

def get_pending_review_count() -> int:
    """Count of cases in NEW or UNDER_REVIEW status."""
    df = _run_query("""
        SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
        WHERE CASE_STATUS IN ('NEW', 'UNDER_REVIEW')
    """)
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_customer_verification_requests() -> int:
    """Count of pending customer verification notifications."""
    df = _run_query("""
        SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG
        WHERE STATUS = 'SENT'
    """)
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_cases_closed_today() -> int:
    """Count of cases closed in the current day."""
    df = _run_query("""
        SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
        WHERE CASE_STATUS IN ('CLOSED', 'FALSE_POSITIVE', 'CUSTOMER_VERIFIED')
          AND CLOSED_AT >= CURRENT_DATE()
    """)
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_avg_investigation_time() -> float:
    """Average investigation time in hours for closed cases."""
    df = _run_query("""
        SELECT ROUND(AVG(TIMESTAMPDIFF(HOUR, CREATED_AT, CLOSED_AT)), 1) AS AVG_HRS
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
        WHERE CLOSED_AT IS NOT NULL
    """)
    val = df["AVG_HRS"].iloc[0] if len(df) > 0 else 0.0
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_alerts_generated() -> int:
    """Total alerts generated."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.ALERTS.ALERT")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_case_status_breakdown() -> pd.DataFrame:
    """Case status distribution for charts."""
    return _run_query("""
        SELECT CASE_STATUS, COUNT(*) AS CASE_COUNT
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
        GROUP BY CASE_STATUS
        ORDER BY CASE_COUNT DESC
    """)


def format_inr(amount: float) -> str:
    """Format currency values cleanly in INR based on scale (Lakh, Crore, or standard commas)."""
    if amount is None or pd.isna(amount):
        return "₹0.00"
    abs_amt = abs(amount)
    if abs_amt >= 10_00_00_000:
        return f"₹{amount / 1_00_00_000:,.2f} Crore"
    elif abs_amt >= 1_00_000:
        return f"₹{amount / 1_00_000:,.2f} Lakh"
    else:
        return f"₹{amount:,.2f}"


def get_total_transaction_value() -> float:
    """Sum of all processed transaction amounts."""
    df = _run_query("SELECT SUM(AMOUNT) AS TOTAL FROM CASEPILOT_DB.RAW.TRANSACTION")
    val = df["TOTAL"].iloc[0] if len(df) > 0 else 0.0
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_total_fraud_amount() -> float:
    """Sum of amounts for confirmed or suspicious fraud transactions."""
    df = _run_query("""
        SELECT SUM(AMOUNT) AS TOTAL FROM CASEPILOT_DB.RAW.TRANSACTION
        WHERE IS_FRAUD = TRUE OR CLASSIFICATION = 'FRAUD_ALERT'
    """)
    val = df["TOTAL"].iloc[0] if len(df) > 0 else 0.0
    if val == 0.0:
        df2 = _run_query("SELECT SUM(TRIGGERED_AMOUNT) AS TOTAL FROM CASEPILOT_DB.ALERTS.ALERT")
        val = df2["TOTAL"].iloc[0] if len(df2) > 0 else 0.0
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_blocked_transaction_amount() -> float:
    """Sum of amounts for blocked transactions."""
    df = _run_query("SELECT SUM(AMOUNT) AS TOTAL FROM CASEPILOT_DB.RAW.TRANSACTION WHERE STATUS = 'BLOCKED'")
    val = df["TOTAL"].iloc[0] if len(df) > 0 else 0.0
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_confirmed_fraud_amount() -> float:
    """Sum of fraud amounts for confirmed fraud cases in recovery/investigation."""
    df = _run_query("SELECT SUM(FRAUD_AMOUNT) AS TOTAL FROM CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY")
    val = df["TOTAL"].iloc[0] if len(df) > 0 else 0.0
    if val == 0.0:
        return get_total_fraud_amount()
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_recovery_rate() -> float:
    """Calculate Recovery Rate = (Recovered Amount / Confirmed Fraud Amount) * 100."""
    rec = get_money_recovered()
    fraud_amt = get_confirmed_fraud_amount()
    if fraud_amt <= 0:
        return 0.0
    return round((rec / fraud_amt) * 100, 1)


def get_active_recovery_cases() -> int:
    """Count of active/pending recovery cases."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY WHERE RECOVERY_STATUS = 'PENDING'")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_recovered_cases() -> int:
    """Count of completed/recovered cases."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY WHERE RECOVERY_STATUS IN ('COMPLETED', 'RECOVERED')")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_pending_recovery_count() -> int:
    """Count of pending recovery cases."""
    return get_active_recovery_cases()


def get_avg_resolution_time() -> float:
    """Average case resolution time in hours."""
    df = _run_query("""
        SELECT ROUND(AVG(TIMESTAMPDIFF(HOUR, CREATED_AT, CLOSED_AT)), 1) AS AVG_HRS
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
        WHERE CLOSED_AT IS NOT NULL OR CASE_STATUS IN ('CLOSED', 'FALSE_POSITIVE', 'CUSTOMER_VERIFIED')
    """)
    val = df["AVG_HRS"].iloc[0] if len(df) > 0 else 0.0
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_audit_logs(limit: int = 50) -> pd.DataFrame:
    """Retrieve real pipeline audit logs from PIPELINE_AUDIT_LOG table."""
    try:
        df = _run_query(f"""
            SELECT
                EVENT_TYPE AS ACTION_TYPE,
                CREATED_AT AS TIMESTAMP,
                DETAILS,
                FILE_NAME,
                TOTAL_ROWS,
                ALERTS_GENERATED,
                CASES_CREATED,
                INTELLIGENCE_RECORDS,
                STATUS,
                PERFORMED_BY
            FROM CASEPILOT_DB.RAW.PIPELINE_AUDIT_LOG
            ORDER BY CREATED_AT DESC
            LIMIT {limit}
        """)
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_daily_alert_trend(days: int = 30) -> pd.DataFrame:
    """Alert count by day for trend chart."""
    return _run_query(f"""
        SELECT DATE_TRUNC('day', CREATED_AT) AS ALERT_DATE,
               COUNT(*) AS ALERT_COUNT
        FROM CASEPILOT_DB.ALERTS.ALERT
        GROUP BY ALERT_DATE
        ORDER BY ALERT_DATE
    """)


def get_top_alert_types(limit: int = 5) -> pd.DataFrame:
    """Top alert types by count."""
    return _run_query(f"""
        SELECT ALERT_TYPE, COUNT(*) AS ALERT_COUNT
        FROM CASEPILOT_DB.ALERTS.ALERT
        GROUP BY ALERT_TYPE
        ORDER BY ALERT_COUNT DESC
        LIMIT {limit}
    """)


def get_ai_copilot_data() -> dict:

    """Aggregate data for the AI Copilot panel."""
    total_cases = get_total_cases()
    active = get_active_cases()
    confirmed = get_confirmed_fraud()
    fp = get_false_positives()
    frozen = get_accounts_frozen()
    recovered = get_money_recovered()
    pending = get_pending_review_count()

    # High priority cases
    hp_df = _run_query("""
        SELECT ic.CASE_NUMBER, ic.CASE_STATUS, ci.PRIORITY_SCORE, ci.RISK_BAND,
               a.ALERT_TYPE, a.SEVERITY
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE ic
        JOIN CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE ci ON ic.CASE_ID = ci.CASE_ID
        JOIN CASEPILOT_DB.ALERTS.ALERT a ON ic.ALERT_ID = a.ALERT_ID
        WHERE ic.CASE_STATUS IN ('NEW', 'UNDER_REVIEW')
          AND ci.RISK_BAND IN ('CRITICAL', 'HIGH')
        ORDER BY ci.PRIORITY_SCORE DESC
        LIMIT 5
    """)

    return {
        "total_cases": total_cases,
        "active_cases": active,
        "confirmed_fraud": confirmed,
        "false_positives": fp,
        "frozen_accounts": frozen,
        "recovered_amount": recovered,
        "pending_review": pending,
        "high_priority_cases": hp_df,
        "automation_rate": round((fp + confirmed) / max(total_cases, 1) * 100, 1),
    }


# ── KPI Queries ──────────────────────────────────────────────────────────────


def get_total_alerts() -> int:
    """Count of all alerts."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.ALERTS.ALERT")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_total_cases() -> int:
    """Count of all investigation cases."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_total_enrichments() -> int:
    """Count of all case enrichment records."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.CASE_ENRICHMENT")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_total_intelligence() -> int:
    """Count of all intelligence records."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_avg_priority_score() -> float:
    """Average priority score across all cases."""
    df = _run_query("SELECT ROUND(AVG(PRIORITY_SCORE), 2) AS AVG_SCORE FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE")
    return float(df["AVG_SCORE"].iloc[0]) if len(df) > 0 and df["AVG_SCORE"].iloc[0] is not None else 0.0


def get_high_risk_count() -> int:
    """Count of HIGH and CRITICAL risk band cases."""
    df = _run_query("""
        SELECT COUNT(*) AS CNT
        FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE
        WHERE RISK_BAND IN ('HIGH', 'CRITICAL')
    """)
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


# ── Chart Data Queries ───────────────────────────────────────────────────────

def get_risk_band_distribution() -> pd.DataFrame:
    """Risk band counts for pie chart."""
    return _run_query("""
        SELECT RISK_BAND, COUNT(*) AS CASE_COUNT
        FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE
        GROUP BY RISK_BAND ORDER BY CASE_COUNT DESC
    """)


def get_priority_score_data() -> pd.DataFrame:
    """Priority scores for histogram."""
    return _run_query("SELECT PRIORITY_SCORE FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE")


def get_alert_severity_distribution() -> pd.DataFrame:
    """Alert severity counts for bar chart."""
    return _run_query("""
        SELECT SEVERITY, COUNT(*) AS ALERT_COUNT
        FROM CASEPILOT_DB.ALERTS.ALERT
        GROUP BY SEVERITY ORDER BY ALERT_COUNT DESC
    """)


def get_alert_type_distribution() -> pd.DataFrame:
    """Alert type counts."""
    return _run_query("""
        SELECT ALERT_TYPE, COUNT(*) AS ALERT_COUNT
        FROM CASEPILOT_DB.ALERTS.ALERT
        GROUP BY ALERT_TYPE ORDER BY ALERT_COUNT DESC
    """)


def get_recent_cases(limit: int = 10) -> pd.DataFrame:
    """Recent investigation cases with intelligence."""
    return _run_query(f"""
        SELECT
            ic.CASE_ID, ic.CASE_NUMBER, ic.ALERT_ID,
            ic.CUSTOMER_ID, ic.CASE_STATUS, ic.ASSIGNED_TO,
            ic.ASSIGNED_TEAM, ic.CREATED_AT,
            ci.PRIORITY_SCORE, ci.RISK_BAND
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE ic
        LEFT JOIN CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE ci
            ON ic.CASE_ID = ci.CASE_ID
        ORDER BY ic.CREATED_AT DESC
        LIMIT {limit}
    """)


# ── Investigation Queue ─────────────────────────────────────────────────────

def get_investigation_queue(
    risk_band: str = None,
    alert_type: str = None,
    min_score: float = None,
    max_score: float = None,
) -> pd.DataFrame:
    """Full investigation queue with filters (lightweight without heavy text blobs)."""
    query = """
        SELECT
            ic.CASE_ID, ic.CASE_NUMBER, ic.ALERT_ID,
            ic.CUSTOMER_ID, ic.ACCOUNT_ID,
            ic.CASE_STATUS, ic.ASSIGNED_TO, ic.ASSIGNED_TEAM,
            ic.CREATED_AT,
            a.ALERT_TYPE, a.SEVERITY, a.ALERT_DESCRIPTION,
            ci.PRIORITY_SCORE, ci.RISK_BAND
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE ic
        LEFT JOIN CASEPILOT_DB.ALERTS.ALERT a ON ic.ALERT_ID = a.ALERT_ID
        LEFT JOIN CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE ci ON ic.CASE_ID = ci.CASE_ID
        WHERE 1=1
    """
    if risk_band and risk_band != "All":
        query += f" AND ci.RISK_BAND = '{risk_band}'"
    if alert_type and alert_type != "All":
        query += f" AND a.ALERT_TYPE = '{alert_type}'"
    if min_score is not None:
        query += f" AND ci.PRIORITY_SCORE >= {min_score}"
    if max_score is not None:
        query += f" AND ci.PRIORITY_SCORE <= {max_score}"
    query += " ORDER BY ci.PRIORITY_SCORE DESC NULLS LAST"
    return _run_query(query)



def get_distinct_risk_bands() -> list:
    """Get distinct risk bands for filter dropdown."""
    df = _run_query("SELECT DISTINCT RISK_BAND FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE ORDER BY RISK_BAND")
    return ["All"] + df["RISK_BAND"].tolist() if len(df) > 0 else ["All"]


def get_distinct_alert_types() -> list:
    """Get distinct alert types for filter dropdown."""
    df = _run_query("SELECT DISTINCT ALERT_TYPE FROM CASEPILOT_DB.ALERTS.ALERT ORDER BY ALERT_TYPE")
    return ["All"] + df["ALERT_TYPE"].tolist() if len(df) > 0 else ["All"]


# ── Case Details ─────────────────────────────────────────────────────────────

def get_case_enrichment(case_id: str) -> pd.DataFrame:
    """Get enrichment data for a specific case, dynamically fetching details from master tables."""
    df = _run_query(f"""
        SELECT
            ENRICHMENT_ID, CASE_ID,
            CUSTOMER_PROFILE, ACCOUNT_PROFILE,
            TXN_HISTORY, MERCHANT_HISTORY,
            DEVICE_HISTORY, PREVIOUS_ALERTS,
            HISTORICAL_STATS, ENRICHED_AT
        FROM CASEPILOT_DB.INVESTIGATION.CASE_ENRICHMENT
        WHERE CASE_ID = '{case_id}'
    """)
    if df.empty:
        return df

    row = df.iloc[0].to_dict()
    
    def parse_json(val):
        if not val:
            return {}
        if isinstance(val, (dict, list)):
            return val
        try:
            import json
            return json.loads(val)
        except:
            return {}

    cust_profile_raw = parse_json(row.get("CUSTOMER_PROFILE"))
    customer_id = cust_profile_raw.get("customer_id")
    risk_rating = cust_profile_raw.get("risk_rating", "LOW")

    if customer_id:
        import json
        cust_df = _run_query(f"""
            SELECT FIRST_NAME, LAST_NAME, EMAIL, PHONE, PERSONA, ANNUAL_INCOME, OCCUPATION, KYC_STATUS, CITY, STATE, COUNTRY
            FROM CASEPILOT_DB.RAW.CUSTOMER
            WHERE CUSTOMER_ID = '{customer_id}'
        """)
        if not cust_df.empty:
            c = cust_df.iloc[0]
            customer_profile = {
                "customer_id": customer_id,
                "name": f"{c['FIRST_NAME']} {c['LAST_NAME']}",
                "email": c["EMAIL"],
                "phone": c["PHONE"],
                "persona": c["PERSONA"],
                "annual_income": float(c["ANNUAL_INCOME"]) if c["ANNUAL_INCOME"] else 0.0,
                "occupation": c["OCCUPATION"],
                "kyc_status": c["KYC_STATUS"],
                "city": c["CITY"],
                "state": c["STATE"],
                "country": c["COUNTRY"],
                "risk_rating": risk_rating,
                "account_age_days": 180
            }
            row["CUSTOMER_PROFILE"] = json.dumps(customer_profile)

        acct_df = _run_query(f"""
            SELECT ACCOUNT_ID, ACCOUNT_NUMBER, ACCOUNT_TYPE, BALANCE, CURRENCY, ACCOUNT_STATUS, IFSC_CODE, OPENED_AT
            FROM CASEPILOT_DB.RAW.ACCOUNT
            WHERE CUSTOMER_ID = '{customer_id}'
        """)
        if not acct_df.empty:
            accounts = []
            for _, r in acct_df.iterrows():
                accounts.append({
                    "account_id": r["ACCOUNT_ID"],
                    "account_number": r["ACCOUNT_NUMBER"],
                    "account_type": r["ACCOUNT_TYPE"],
                    "balance": float(r["BALANCE"]),
                    "currency": r["CURRENCY"],
                    "status": r["ACCOUNT_STATUS"],
                    "ifsc": r["IFSC_CODE"],
                    "opened_at": str(r["OPENED_AT"])
                })
            row["ACCOUNT_PROFILE"] = json.dumps(accounts[0] if len(accounts) == 1 else accounts)

        txn_df = _run_query(f"""
            SELECT TXN_ID, AMOUNT, CHANNEL, TXN_TIMESTAMP, STATUS, DESCRIPTION, CLASSIFICATION
            FROM CASEPILOT_DB.RAW.TRANSACTION
            WHERE CUSTOMER_ID = '{customer_id}'
            ORDER BY TXN_TIMESTAMP DESC
        """)
        if not txn_df.empty:
            total_txns = len(txn_df)
            amounts = txn_df["AMOUNT"].astype(float)
            total_amt = float(amounts.sum())
            avg_amt = float(amounts.mean())
            max_amt = float(amounts.max())
            std_dev = float(amounts.std()) if total_txns > 1 else 0.0
            
            ch_dist = txn_df["CHANNEL"].value_counts().to_dict()
            
            recent_list = []
            for _, r in txn_df.head(10).iterrows():
                recent_list.append({
                    "TXN_ID": r["TXN_ID"],
                    "AMOUNT": float(r["AMOUNT"]),
                    "CHANNEL": r["CHANNEL"],
                    "TXN_TIMESTAMP": str(r["TXN_TIMESTAMP"]),
                    "STATUS": r["STATUS"],
                    "DESCRIPTION": r["DESCRIPTION"],
                    "CLASSIFICATION": r.get("CLASSIFICATION", "LEGITIMATE")
                })
            
            row["TXN_HISTORY"] = json.dumps({
                "total_transactions": total_txns,
                "total_amount": total_amt,
                "avg_amount": avg_amt,
                "max_amount": max_amt,
                "channel_distribution": ch_dist,
                "recent_transactions": recent_list
            })

            row["HISTORICAL_STATS"] = json.dumps({
                "total_transactions": total_txns,
                "avg_transaction_amount": avg_amt,
                "std_dev_amount": std_dev,
                "transactions_per_day": round(total_txns / 30.0, 1),
                "total_alerts": 0,
                "international_txn_ratio": 0.05
            })

        merch_df = _run_query(f"""
            SELECT DISTINCT M.MERCHANT_NAME, M.CATEGORY, M.RISK_LEVEL, T.AMOUNT
            FROM CASEPILOT_DB.RAW.TRANSACTION T
            JOIN CASEPILOT_DB.RAW.MERCHANT M ON T.MERCHANT_ID = M.MERCHANT_ID
            WHERE T.CUSTOMER_ID = '{customer_id}'
            LIMIT 10
        """)
        if not merch_df.empty:
            merch_list = []
            for _, r in merch_df.iterrows():
                merch_list.append({
                    "MERCHANT_NAME": r["MERCHANT_NAME"],
                    "CATEGORY": r["CATEGORY"],
                    "RISK_LEVEL": r["RISK_LEVEL"],
                    "LAST_AMOUNT": float(r["AMOUNT"])
                })
            row["MERCHANT_HISTORY"] = json.dumps(merch_list)

        dev_df = _run_query(f"""
            SELECT DEVICE_TYPE, DEVICE_NAME, IS_TRUSTED, IP_ADDRESS
            FROM CASEPILOT_DB.RAW.DEVICE
            WHERE CUSTOMER_ID = '{customer_id}'
        """)
        if not dev_df.empty:
            dev_list = []
            for _, r in dev_df.iterrows():
                dev_list.append({
                    "DEVICE_TYPE": r["DEVICE_TYPE"],
                    "DEVICE_NAME": r["DEVICE_NAME"],
                    "IS_TRUSTED": bool(r["IS_TRUSTED"]),
                    "IP_ADDRESS": r["IP_ADDRESS"]
                })
            row["DEVICE_HISTORY"] = json.dumps(dev_list)

        alerts_df = _run_query(f"""
            SELECT ALERT_TYPE, SEVERITY, STATUS, CREATED_AT
            FROM CASEPILOT_DB.ALERTS.ALERT
            WHERE CUSTOMER_ID = '{customer_id}'
            ORDER BY CREATED_AT DESC
        """)
        if not alerts_df.empty:
            al_list = []
            for _, r in alerts_df.iterrows():
                al_list.append({
                    "ALERT_TYPE": r["ALERT_TYPE"],
                    "SEVERITY": r["SEVERITY"],
                    "STATUS": r["STATUS"],
                    "CREATED_AT": str(r["CREATED_AT"])
                })
            row["PREVIOUS_ALERTS"] = json.dumps(al_list)
            
            stats_dict = parse_json(row.get("HISTORICAL_STATS"))
            stats_dict["total_alerts"] = len(alerts_df)
            row["HISTORICAL_STATS"] = json.dumps(stats_dict)

    return pd.DataFrame([row])


def get_case_intelligence(case_id: str) -> pd.DataFrame:
    """Get intelligence data for a specific case."""
    return _run_query(f"""
        SELECT
            INTELLIGENCE_ID, CASE_ID, ALERT_ID,
            PRIORITY_SCORE, RISK_BAND,
            INVESTIGATION_SUMMARY, RECOMMENDATIONS,
            TIMELINE, KEY_FINDINGS,
            MODEL_VERSION, GENERATED_AT
        FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE
        WHERE CASE_ID = '{case_id}'
    """)


def get_all_case_ids() -> list:
    """Get all case IDs for selection dropdowns."""
    df = _run_query("""
        SELECT ic.CASE_ID, ic.CASE_NUMBER, ci.RISK_BAND, ci.PRIORITY_SCORE
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE ic
        LEFT JOIN CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE ci ON ic.CASE_ID = ci.CASE_ID
        ORDER BY ci.PRIORITY_SCORE DESC NULLS LAST
    """)
    return df


def insert_manual_case(customer_id: str, account_id: str, alert_type: str,
                       severity: str, priority: str, assigned_to: str,
                       description: str, performed_by: str) -> str:
    """Manually insert an investigation case into Snowflake without requiring an alert."""
    import uuid
    from datetime import datetime
    case_id = str(uuid.uuid4())
    case_number = f"CASE-MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_sf_connection()
    cursor = conn.get_connection().cursor()
    try:
        cursor.execute("""
            INSERT INTO CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE (
                CASE_ID, ALERT_ID, CUSTOMER_ID, ACCOUNT_ID, CASE_NUMBER,
                CASE_STATUS, ASSIGNED_TO, ASSIGNED_TEAM, PRIORITY,
                CREATED_AT, UPDATED_AT, CLOSED_AT, CLOSURE_REASON
            ) VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL)
        """, (
            case_id, customer_id, account_id, case_number,
            'NEW', assigned_to, 'Fraud Operations', priority, now, now
        ))
        # Write audit log entry
        cursor.execute("""
            INSERT INTO CASEPILOT_DB.RAW.PIPELINE_AUDIT_LOG (
                EVENT_TYPE, FILE_NAME, TOTAL_ROWS, ALERTS_GENERATED, CASES_CREATED,
                INTELLIGENCE_RECORDS, PERFORMED_BY, STATUS, DETAILS, CREATED_AT
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
        """, (
            'MANUAL_CASE_CREATION', 'N/A', 0, 0, 1, 0, performed_by, 'SUCCESS',
            f"Manual case created: {case_number} | Customer: {customer_id} | Type: {alert_type} | Priority: {priority}"
        ))
        conn.get_connection().commit()
        return case_id
    except Exception as e:
        raise e
    finally:
        cursor.close()


# ── Analytics Queries ────────────────────────────────────────────────────────

def get_top_high_risk_customers(limit: int = 10) -> pd.DataFrame:
    """Customers with the most high/critical risk cases."""
    return _run_query(f"""
        SELECT
            ci.CASE_ID, ic.CUSTOMER_ID,
            ci.PRIORITY_SCORE, ci.RISK_BAND,
            a.ALERT_TYPE, a.SEVERITY
        FROM CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE ci
        JOIN CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE ic ON ci.CASE_ID = ic.CASE_ID
        JOIN CASEPILOT_DB.ALERTS.ALERT a ON ci.ALERT_ID = a.ALERT_ID
        ORDER BY ci.PRIORITY_SCORE DESC
        LIMIT {limit}
    """)


def get_top_merchants_by_alerts(limit: int = 10) -> pd.DataFrame:
    """Merchants with the most associated alerts."""
    return _run_query(f"""
        SELECT
            t.MERCHANT_ID,
            m.MERCHANT_NAME, m.CATEGORY, m.RISK_LEVEL,
            COUNT(a.ALERT_ID) AS ALERT_COUNT
        FROM CASEPILOT_DB.ALERTS.ALERT a
        JOIN CASEPILOT_DB.RAW.TRANSACTION t ON a.TXN_ID = t.TXN_ID
        JOIN CASEPILOT_DB.RAW.MERCHANT m ON t.MERCHANT_ID = m.MERCHANT_ID
        GROUP BY t.MERCHANT_ID, m.MERCHANT_NAME, m.CATEGORY, m.RISK_LEVEL
        ORDER BY ALERT_COUNT DESC
        LIMIT {limit}
    """)


def get_top_devices_by_alerts(limit: int = 10) -> pd.DataFrame:
    """Devices with the most associated alerts."""
    return _run_query(f"""
        SELECT
            t.DEVICE_ID,
            d.DEVICE_TYPE, d.DEVICE_NAME, d.IS_TRUSTED,
            COUNT(a.ALERT_ID) AS ALERT_COUNT
        FROM CASEPILOT_DB.ALERTS.ALERT a
        JOIN CASEPILOT_DB.RAW.TRANSACTION t ON a.TXN_ID = t.TXN_ID
        JOIN CASEPILOT_DB.RAW.DEVICE d ON t.DEVICE_ID = d.DEVICE_ID
        GROUP BY t.DEVICE_ID, d.DEVICE_TYPE, d.DEVICE_NAME, d.IS_TRUSTED
        ORDER BY ALERT_COUNT DESC
        LIMIT {limit}
    """)


def get_cases_over_time() -> pd.DataFrame:
    """Case creation trend over time."""
    return _run_query("""
        SELECT
            DATE_TRUNC('day', CREATED_AT) AS CASE_DATE,
            COUNT(*) AS CASE_COUNT
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
        GROUP BY CASE_DATE ORDER BY CASE_DATE
    """)


# ── Fraud Analytics & Management Reporting Queries (CasePilot 2.0) ───────────

def get_model_performance_metrics() -> pd.DataFrame:
    """Retrieve model performance metrics histories."""
    return _run_query("""
        SELECT
            METRIC_ID, RUN_ID, MODEL_VERSION, TOTAL_PREDICTIONS,
            TRUE_POSITIVES, TRUE_NEGATIVES, FALSE_POSITIVES, FALSE_NEGATIVES,
            ACCURACY, PRECISION_SCORE, RECALL, F1_SCORE,
            FALSE_POSITIVE_RATE, FALSE_NEGATIVE_RATE,
            EVALUATED_AT
        FROM CASEPILOT_DB.ANALYTICS.MODEL_METRICS
        ORDER BY EVALUATED_AT DESC
    """)


def get_fraud_by_type() -> pd.DataFrame:
    """Breakdown of transaction fraud categories."""
    return _run_query("""
        SELECT
            COALESCE(FRAUD_TYPE, 'LEGITIMATE') AS FRAUD_CATEGORY,
            COUNT(*) AS TXN_COUNT,
            SUM(AMOUNT) AS TOTAL_AMOUNT
        FROM CASEPILOT_DB.RAW.TRANSACTION
        GROUP BY FRAUD_TYPE
        ORDER BY TXN_COUNT DESC
    """)


def get_notification_logs(limit: int = 20) -> pd.DataFrame:
    """Retrieve detailed customer notifications logs."""
    return _run_query(f"""
        SELECT
            NOTIFICATION_ID, CUSTOMER_ID, ALERT_ID, CASE_ID,
            MESSAGE, CHANNEL, STATUS, CUSTOMER_RESPONSE,
            SENT_AT, RESPONDED_AT, RESPONSE_ACTION
        FROM CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG
        ORDER BY SENT_AT DESC
        LIMIT {limit}
    """)


def get_notification_stats() -> pd.DataFrame:
    """Aggregated notification response statistics."""
    return _run_query("""
        SELECT
            STATUS,
            CUSTOMER_RESPONSE,
            COUNT(*) AS NOTIF_COUNT
        FROM CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG
        GROUP BY STATUS, CUSTOMER_RESPONSE
    """)


def get_total_transactions() -> int:
    """Count of all transactions."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.RAW.TRANSACTION")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_suspicious_transactions() -> int:
    """Count of suspicious transactions (REVIEW or FRAUD_ALERT)."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.RAW.TRANSACTION WHERE CLASSIFICATION IN ('REVIEW', 'FRAUD_ALERT')")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_active_cases() -> int:
    """Count of active open cases."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE WHERE CASE_STATUS IN ('NEW', 'UNDER_REVIEW', 'CUSTOMER_CONTACTED')")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_confirmed_fraud() -> int:
    """Count of confirmed fraud cases."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE WHERE CASE_STATUS = 'FRAUD_CONFIRMED'")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_false_positives() -> int:
    """Count of false positive cases."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE WHERE CASE_STATUS = 'FALSE_POSITIVE'")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_accounts_frozen() -> int:
    """Count of accounts with status FROZEN."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.RAW.ACCOUNT WHERE ACCOUNT_STATUS = 'FROZEN'")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_customer_verified() -> int:
    """Count of customer verified cases."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE WHERE CASE_STATUS = 'CUSTOMER_VERIFIED'")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_money_recovered() -> float:
    """Sum of recovered fraud amounts."""
    df = _run_query("SELECT SUM(RECOVERED_AMOUNT) AS TOTAL FROM CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY")
    val = df["TOTAL"].iloc[0] if len(df) > 0 else 0.0
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_fraud_loss_prevented() -> float:
    """Sum of amounts for blocked/prevented transactions."""
    df = _run_query("SELECT SUM(AMOUNT) AS TOTAL FROM CASEPILOT_DB.RAW.TRANSACTION WHERE STATUS = 'BLOCKED'")
    val = df["TOTAL"].iloc[0] if len(df) > 0 else 0.0
    return float(val) if val is not None and not pd.isna(val) else 0.0


def get_live_event_feed(limit: int = 15) -> pd.DataFrame:
    """Retrieve recent timeline events for a combined feed."""
    txns = _run_query(f"""
        SELECT 'TRANSACTION' AS EVENT_TYPE, CREATED_AT AS EVENT_TIME, 
               CONCAT('Transaction of ₹', TO_VARCHAR(AMOUNT, '999,999,999.00'), ' at ', COALESCE(DESCRIPTION, 'Merchant'), ' status: ', STATUS) AS DESCRIPTION
        FROM CASEPILOT_DB.RAW.TRANSACTION
        ORDER BY CREATED_AT DESC LIMIT {limit}
    """)
    alerts = _run_query(f"""
        SELECT 'ALERT' AS EVENT_TYPE, CREATED_AT AS EVENT_TIME,
               CONCAT('Alert ', ALERT_TYPE, ' (', SEVERITY, ') triggered for Customer ', SUBSTR(CUSTOMER_ID, 1, 8)) AS DESCRIPTION
        FROM CASEPILOT_DB.ALERTS.ALERT
        ORDER BY CREATED_AT DESC LIMIT {limit}
    """)
    cases = _run_query(f"""
        SELECT 'CASE' AS EVENT_TYPE, UPDATED_AT AS EVENT_TIME,
               CONCAT('Case ', CASE_NUMBER, ' status: ', CASE_STATUS, ' (Assigned: ', COALESCE(ASSIGNED_TO, 'None'), ')') AS DESCRIPTION
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
        ORDER BY UPDATED_AT DESC LIMIT {limit}
    """)
    notifs = _run_query(f"""
        SELECT 'NOTIFICATION' AS EVENT_TYPE, SENT_AT AS EVENT_TIME,
               CONCAT('Notification (', CHANNEL, ') - Status: ', STATUS, IFF(CUSTOMER_RESPONSE IS NOT NULL, CONCAT(' (Response: ', CUSTOMER_RESPONSE, ')'), '')) AS DESCRIPTION
        FROM CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG
        ORDER BY SENT_AT DESC LIMIT {limit}
    """)
    
    # Merge and sort
    dfs = []
    for df in [txns, alerts, cases, notifs]:
        if df is not None and len(df) > 0:
            dfs.append(df)
            
    if not dfs:
        return pd.DataFrame(columns=['EVENT_TYPE', 'EVENT_TIME', 'DESCRIPTION'])
        
    combined = pd.concat(dfs, ignore_index=True)
    combined['EVENT_TIME'] = pd.to_datetime(combined['EVENT_TIME'])
    combined = combined.sort_values(by='EVENT_TIME', ascending=False).head(limit)
    return combined


def get_pending_customer_notifications(customer_id: str) -> pd.DataFrame:
    """Pending authorization approvals for a given customer."""
    return _run_query(f"""
        SELECT n.NOTIFICATION_ID, n.ALERT_ID, n.CASE_ID, n.MESSAGE, n.CHANNEL, n.SENT_AT, a.TXN_ID
        FROM CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG n
        JOIN CASEPILOT_DB.ALERTS.ALERT a ON n.ALERT_ID = a.ALERT_ID
        WHERE n.CUSTOMER_ID = '{customer_id}' AND n.STATUS = 'SENT'
        ORDER BY n.SENT_AT DESC
    """)


def get_customer_transactions(customer_id: str, limit: int = 20) -> pd.DataFrame:
    """Recent transaction history for customer portal."""
    return _run_query(f"""
        SELECT TXN_ID, AMOUNT, CHANNEL, STATUS, CLASSIFICATION, FRAUD_SCORE, CREATED_AT, DESCRIPTION
        FROM CASEPILOT_DB.RAW.TRANSACTION
        WHERE CUSTOMER_ID = '{customer_id}'
        ORDER BY CREATED_AT DESC
        LIMIT {limit}
    """)


def get_bank_accounts_overview(search_term: str = None) -> pd.DataFrame:
    """Overview of accounts for bank employee view."""
    query = """
        SELECT a.ACCOUNT_ID, a.ACCOUNT_NUMBER, a.ACCOUNT_TYPE, a.BALANCE, a.ACCOUNT_STATUS,
               c.CUSTOMER_ID, CONCAT(c.FIRST_NAME, ' ', c.LAST_NAME) AS CUSTOMER_NAME,
               c.RISK_RATING, c.KYC_STATUS
        FROM CASEPILOT_DB.RAW.ACCOUNT a
        JOIN CASEPILOT_DB.RAW.CUSTOMER c ON a.CUSTOMER_ID = c.CUSTOMER_ID
    """
    if search_term:
        query += f" WHERE c.FIRST_NAME ILIKE '%{search_term}%' OR c.LAST_NAME ILIKE '%{search_term}%' OR a.ACCOUNT_NUMBER ILIKE '%{search_term}%'"
    query += " ORDER BY c.FIRST_NAME, c.LAST_NAME"
    return _run_query(query)


def get_open_cases_for_bank() -> pd.DataFrame:
    """Open cases for bank employee portal."""
    return _run_query("""
        SELECT ic.CASE_ID, ic.CASE_NUMBER, ic.CASE_STATUS, ic.ASSIGNED_TO, ic.CREATED_AT,
               a.ALERT_TYPE, a.SEVERITY,
               c.CUSTOMER_ID, CONCAT(c.FIRST_NAME, ' ', c.LAST_NAME) AS CUSTOMER_NAME
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE ic
        JOIN CASEPILOT_DB.ALERTS.ALERT a ON ic.ALERT_ID = a.ALERT_ID
        JOIN CASEPILOT_DB.RAW.CUSTOMER c ON ic.CUSTOMER_ID = c.CUSTOMER_ID
        WHERE ic.CASE_STATUS IN ('NEW', 'UNDER_REVIEW', 'CUSTOMER_CONTACTED', 'FRAUD_CONFIRMED', 'ACCOUNT_FROZEN')
        ORDER BY ic.CREATED_AT DESC
    """)


def get_all_customers_list() -> pd.DataFrame:
    """Fetch all customers for login dropdown."""
    return _run_query("""
        SELECT CUSTOMER_ID, CONCAT(FIRST_NAME, ' ', LAST_NAME) AS CUSTOMER_NAME
        FROM CASEPILOT_DB.RAW.CUSTOMER
        ORDER BY CUSTOMER_NAME ASC
    """)


def approve_transaction(notif_id: str, case_id: str, alert_id: str) -> bool:
    """Approve transaction from customer side."""
    from datetime import datetime
    conn = get_sf_connection()
    cursor = conn.get_connection().cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG
            SET STATUS = 'RESPONDED',
                CUSTOMER_RESPONSE = 'YES',
                RESPONDED_AT = '{now_str}',
                RESPONSE_ACTION = 'REDUCE_RISK_CLOSE_CASE'
            WHERE NOTIFICATION_ID = '{notif_id}'
        """)
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
            SET CASE_STATUS = 'FALSE_POSITIVE',
                CLOSED_AT = '{now_str}',
                CLOSURE_REASON = 'Customer confirmed transaction was authorized.'
            WHERE CASE_ID = '{case_id}'
        """)
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.ALERTS.ALERT
            SET STATUS = 'RESOLVED',
                UPDATED_AT = '{now_str}'
            WHERE ALERT_ID = '{alert_id}'
        """)
        conn.get_connection().commit()
        return True
    except Exception as e:
        st.error(f"Error approving transaction: {e}")
        return False
    finally:
        cursor.close()


def deny_transaction(notif_id: str, case_id: str, alert_id: str, txn_id: str) -> bool:
    """Deny transaction from customer side (confirm fraud and block/freeze)."""
    from datetime import datetime
    import uuid
    conn = get_sf_connection()
    cursor = conn.get_connection().cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG
            SET STATUS = 'RESPONDED',
                CUSTOMER_RESPONSE = 'NO',
                RESPONDED_AT = '{now_str}',
                RESPONSE_ACTION = 'INCREASE_RISK_ESCALATE'
            WHERE NOTIFICATION_ID = '{notif_id}'
        """)
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
            SET CASE_STATUS = 'FRAUD_CONFIRMED',
                UPDATED_AT = '{now_str}'
            WHERE CASE_ID = '{case_id}'
        """)
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.ALERTS.ALERT
            SET STATUS = 'ESCALATED',
                UPDATED_AT = '{now_str}'
            WHERE ALERT_ID = '{alert_id}'
        """)
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.RAW.TRANSACTION
            SET STATUS = 'BLOCKED',
                IS_FRAUD = TRUE
            WHERE TXN_ID = '{txn_id}'
        """)
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.RAW.ACCOUNT
            SET ACCOUNT_STATUS = 'FROZEN',
                UPDATED_AT = '{now_str}'
            WHERE ACCOUNT_ID = (
                SELECT ACCOUNT_ID FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE WHERE CASE_ID = '{case_id}'
            )
        """)
        
        cursor.execute(f"SELECT CUSTOMER_ID, TRIGGERED_AMOUNT FROM CASEPILOT_DB.ALERTS.ALERT WHERE ALERT_ID = '{alert_id}'")
        row = cursor.fetchone()
        if row:
            cust_id, amount = row[0], float(row[1])
            rec_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY (
                    RECOVERY_ID, CASE_ID, CUSTOMER_ID, FRAUD_AMOUNT, RECOVERED_AMOUNT,
                    RECOVERY_STATUS, RECOVERY_METHOD, UPDATED_AT
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
            """, (rec_id, case_id, cust_id, amount, 0.0, 'PENDING', 'FUNDS_FREEZE'))
        
        conn.get_connection().commit()
        return True
    except Exception as e:
        st.error(f"Error denying transaction: {e}")
        return False
    finally:
        cursor.close()


def update_account_status(account_id: str, status: str) -> bool:
    """Freeze or unfreeze bank account."""
    from datetime import datetime
    conn = get_sf_connection()
    cursor = conn.get_connection().cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(f"""
            UPDATE CASEPILOT_DB.RAW.ACCOUNT
            SET ACCOUNT_STATUS = '{status}',
                UPDATED_AT = '{now_str}'
            WHERE ACCOUNT_ID = '{account_id}'
        """)
        if status == 'FROZEN':
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'ACCOUNT_FROZEN',
                    UPDATED_AT = '{now_str}'
                WHERE ACCOUNT_ID = '{account_id}'
                  AND CASE_STATUS IN ('NEW', 'UNDER_REVIEW', 'CUSTOMER_CONTACTED', 'FRAUD_CONFIRMED')
            """)
        else:
            cursor.execute(f"""
                UPDATE CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
                SET CASE_STATUS = 'CLOSED',
                    UPDATED_AT = '{now_str}'
                WHERE ACCOUNT_ID = '{account_id}'
                  AND CASE_STATUS = 'ACCOUNT_FROZEN'
            """)
        conn.get_connection().commit()
        return True
    except Exception as e:
        st.error(f"Error updating account status: {e}")
        return False
    finally:
        cursor.close()


def get_legitimate_transactions() -> int:
    """Count of transactions classified as LEGITIMATE."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.RAW.TRANSACTION WHERE CLASSIFICATION = 'LEGITIMATE'")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_review_transactions() -> int:
    """Count of transactions classified as REVIEW."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.RAW.TRANSACTION WHERE CLASSIFICATION = 'REVIEW'")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_customers_contacted() -> int:
    """Count of unique customers contacted via notification log."""
    df = _run_query("SELECT COUNT(DISTINCT CUSTOMER_ID) AS CNT FROM CASEPILOT_DB.INVESTIGATION.NOTIFICATION_LOG")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_recovery_cases_count() -> int:
    """Count of recovery cases in fraud recovery table."""
    df = _run_query("SELECT COUNT(*) AS CNT FROM CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY")
    return int(df["CNT"].iloc[0]) if len(df) > 0 else 0


def get_all_recoveries(limit: int = 100) -> pd.DataFrame:
    """Get detailed list of fraud recovery logs."""
    return _run_query(f"""
        SELECT 
            RECOVERY_ID, CASE_ID, CUSTOMER_ID, FRAUD_AMOUNT, RECOVERED_AMOUNT,
            RECOVERY_STATUS, RECOVERY_METHOD, UPDATED_AT
        FROM CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY
        ORDER BY UPDATED_AT DESC
        LIMIT {limit}
    """)


def get_recoveries_by_status() -> pd.DataFrame:
    """Get counts and sums of recoveries grouped by status."""
    return _run_query("""
        SELECT 
            RECOVERY_STATUS,
            COUNT(*) AS CASE_COUNT,
            SUM(FRAUD_AMOUNT) AS TOTAL_FRAUD,
            SUM(RECOVERED_AMOUNT) AS TOTAL_RECOVERED
        FROM CASEPILOT_DB.INVESTIGATION.FRAUD_RECOVERY
        GROUP BY RECOVERY_STATUS
    """)


import json

from src.config.snowflake_connection import SnowflakeConnection
from src.intelligence.priority_scoring import score_all_cases
from src.intelligence.case_summary import (
    generate_intelligence,
    insert_intelligence_to_snowflake,
)

BATCH_SIZE = 10

with SnowflakeConnection() as conn:

    cases_raw = conn.execute_query("""
        SELECT
            CASE_ID,
            ALERT_ID,
            CUSTOMER_ID,
            ACCOUNT_ID
        FROM INVESTIGATION.INVESTIGATION_CASE
    """)

    alerts_raw = conn.execute_query("""
        SELECT
            ALERT_ID,
            TXN_ID,
            ACCOUNT_ID,
            CUSTOMER_ID,
            ALERT_TYPE,
            ALERT_DESCRIPTION,
            SEVERITY,
            RULE_VERSION,
            TRIGGERED_AMOUNT,
            TRIGGERED_THRESHOLD,
            STATUS,
            CREATED_AT
        FROM ALERTS.ALERT
    """)

    cases = [
        {
            "CASE_ID": r[0],
            "ALERT_ID": r[1],
            "CUSTOMER_ID": r[2],
            "ACCOUNT_ID": r[3],
        }
        for r in cases_raw
    ]

    alerts = [
        {
            "ALERT_ID": r[0],
            "TXN_ID": r[1],
            "ACCOUNT_ID": r[2],
            "CUSTOMER_ID": r[3],
            "ALERT_TYPE": r[4],
            "ALERT_DESCRIPTION": r[5],
            "SEVERITY": r[6],
            "RULE_VERSION": r[7],
            "TRIGGERED_AMOUNT": float(r[8]) if r[8] is not None else 0,
            "TRIGGERED_THRESHOLD": float(r[9]) if r[9] is not None else 0,
            "STATUS": r[10],
            "CREATED_AT": str(r[11]) if r[11] else None,
        }
        for r in alerts_raw
    ]

    offset = 0
    total_inserted = 0

    while True:

        enrichments_raw = conn.execute_query(f"""
            SELECT *
            FROM INVESTIGATION.CASE_ENRICHMENT
            LIMIT {BATCH_SIZE}
            OFFSET {offset}
        """)

        if not enrichments_raw:
            break

        enrichments = []

        for r in enrichments_raw:
            enrichments.append(
                {
                    "ENRICHMENT_ID": r[0],
                    "CASE_ID": r[1],
                    "CUSTOMER_PROFILE": json.loads(r[2]),
                    "ACCOUNT_PROFILE": json.loads(r[3]),
                    "TXN_HISTORY": json.loads(r[4]),
                    "MERCHANT_HISTORY": json.loads(r[5]),
                    "DEVICE_HISTORY": json.loads(r[6]),
                    "PREVIOUS_ALERTS": json.loads(r[7]),
                    "HISTORICAL_STATS": json.loads(r[8]),
                    "ENRICHED_AT": str(r[9]),
                }
            )

        batch_case_ids = {
            e["CASE_ID"]
            for e in enrichments
        }

        batch_cases = [
            c for c in cases
            if c["CASE_ID"] in batch_case_ids
        ]

        score_results = score_all_cases(
            batch_cases,
            alerts,
            enrichments,
        )

        intelligence = generate_intelligence(
            batch_cases,
            alerts,
            enrichments,
            score_results,
        )

        inserted = insert_intelligence_to_snowflake(
            intelligence,
            conn,
        )

        total_inserted += inserted

        print(
            f"Processed batch starting at {offset}: "
            f"{inserted} records inserted"
        )

        offset += BATCH_SIZE

print(
    f"Completed successfully. "
    f"{total_inserted} intelligence records inserted."
)

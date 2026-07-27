"""
CasePilot Dashboard — Customer 360 Page
==========================================
Deep-dive customer intelligence built directly from uploaded transaction data.
Works from RAW.TRANSACTION even when enrichments/cases are not yet generated.
"""

import json
import streamlit as st
import pandas as pd

from src.dashboard.services.queries import (
    get_all_case_ids, get_case_enrichment, get_sf_connection, _run_query
)


def _get_customers_from_transactions() -> pd.DataFrame:
    """Get distinct customer IDs from uploaded transaction data."""
    return _run_query("""
        SELECT
            CUSTOMER_ID,
            COUNT(*) AS TXN_COUNT,
            SUM(AMOUNT) AS TOTAL_AMOUNT,
            SUM(CASE WHEN IS_FRAUD THEN 1 ELSE 0 END) AS FRAUD_TXN_COUNT,
            SUM(CASE WHEN CLASSIFICATION = 'FRAUD_ALERT' THEN 1 ELSE 0 END) AS ALERT_COUNT,
            MAX(TXN_TIMESTAMP) AS LAST_TXN
        FROM CASEPILOT_DB.RAW.TRANSACTION
        GROUP BY CUSTOMER_ID
        ORDER BY FRAUD_TXN_COUNT DESC, ALERT_COUNT DESC, TXN_COUNT DESC
    """)


def _get_customer_transactions(customer_id: str) -> pd.DataFrame:
    return _run_query(f"""
        SELECT TXN_ID, AMOUNT, CHANNEL, TXN_TIMESTAMP, STATUS, DESCRIPTION,
               CLASSIFICATION, FRAUD_SCORE, IS_FRAUD, MERCHANT_CITY, MERCHANT_COUNTRY
        FROM CASEPILOT_DB.RAW.TRANSACTION
        WHERE CUSTOMER_ID = '{customer_id}'
        ORDER BY TXN_TIMESTAMP DESC
    """)


def _get_customer_alerts(customer_id: str) -> pd.DataFrame:
    try:
        return _run_query(f"""
            SELECT ALERT_TYPE, SEVERITY, STATUS, TRIGGERED_AMOUNT, CREATED_AT
            FROM CASEPILOT_DB.ALERTS.ALERT
            WHERE CUSTOMER_ID = '{customer_id}'
            ORDER BY CREATED_AT DESC
        """)
    except Exception:
        return pd.DataFrame()


def _get_customer_cases(customer_id: str) -> pd.DataFrame:
    try:
        return _run_query(f"""
            SELECT CASE_NUMBER, CASE_STATUS, PRIORITY, ASSIGNED_TO, CREATED_AT
            FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
            WHERE CUSTOMER_ID = '{customer_id}'
            ORDER BY CREATED_AT DESC
        """)
    except Exception:
        return pd.DataFrame()


def render():
    """Render the Customer 360 page."""
    st.markdown("""
    <h2 style="color:#F1F5F9; margin-bottom:4px;">👤 Customer 360</h2>
    <p style="color:#64748B; font-size:0.85rem; margin-bottom:20px;">
        Full transaction intelligence profile for any customer from the uploaded dataset.
    </p>
    """, unsafe_allow_html=True)

    # ── Get distinct customers from transactions ──────────────────────────────
    customers_df = _get_customers_from_transactions()

    if customers_df.empty:
        st.markdown("""
        <div style="background-color: #1F2937; border: 1px solid #374151; border-radius: 8px;
                    padding: 40px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 12px;">👤</div>
            <h3 style="color: #F9FAFB; margin-bottom: 8px;">No Customer Profiles Available</h3>
            <p style="color: #9CA3AF; font-size: 0.9rem; max-width: 450px; margin: 0 auto 16px auto;">
                Upload a transaction dataset to view Customer 360 intelligence profiles.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Customer selector ─────────────────────────────────────────────────────
    def label_customer(row):
        cid = row["CUSTOMER_ID"]
        total = row.get("TXN_COUNT", 0)
        fraud = row.get("FRAUD_TXN_COUNT", 0)
        flag = " 🚨" if fraud > 0 else ""
        return f"{cid}{flag}  ({total} txns, {fraud} fraud alerts)"

    labels = [label_customer(r) for _, r in customers_df.iterrows()]
    selected_idx = st.selectbox("Select Customer", range(len(labels)),
                                format_func=lambda i: labels[i],
                                key="c360_customer")

    customer_id = customers_df.iloc[selected_idx]["CUSTOMER_ID"]
    summary_row = customers_df.iloc[selected_idx]

    st.markdown("---")

    # ── Overview KPI bar ─────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Transactions", f"{int(summary_row.get('TXN_COUNT', 0)):,}")
    with m2:
        total_amt = float(summary_row.get("TOTAL_AMOUNT", 0) or 0)
        st.metric("Total Amount", f"₹{total_amt:,.0f}")
    with m3:
        fraud_cnt = int(summary_row.get("FRAUD_TXN_COUNT", 0) or 0)
        st.metric("Fraud Transactions", str(fraud_cnt),
                  delta="⚠️ High Risk" if fraud_cnt > 0 else None,
                  delta_color="inverse")
    with m4:
        alert_cnt = int(summary_row.get("ALERT_COUNT", 0) or 0)
        st.metric("Alerts Triggered", str(alert_cnt))

    st.markdown("---")

    # ── Transaction History ──────────────────────────────────────────────────
    st.markdown("### 💳 Transaction History")
    txn_df = _get_customer_transactions(customer_id)

    if txn_df.empty:
        st.info("No transactions found for this customer.")
    else:
        # Summary stats
        amounts = pd.to_numeric(txn_df["AMOUNT"], errors="coerce")
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.metric("Avg Amount", f"₹{amounts.mean():,.0f}")
        with sc2:
            st.metric("Max Amount", f"₹{amounts.max():,.0f}")
        with sc3:
            channels = txn_df["CHANNEL"].value_counts().to_dict()
            top_channel = max(channels, key=channels.get) if channels else "N/A"
            st.metric("Top Channel", top_channel)
        with sc4:
            intl_pct = (txn_df["MERCHANT_COUNTRY"] != "India").mean() * 100 if "MERCHANT_COUNTRY" in txn_df.columns else 0
            st.metric("International %", f"{intl_pct:.1f}%")

        # Channel distribution chart
        if channels:
            ch_df = pd.DataFrame(list(channels.items()), columns=["Channel", "Count"])
            st.bar_chart(ch_df.set_index("Channel"), height=200)

        # Classification breakdown
        if "CLASSIFICATION" in txn_df.columns:
            class_counts = txn_df["CLASSIFICATION"].value_counts().reset_index()
            class_counts.columns = ["Classification", "Count"]
            st.markdown("**Risk Classification Breakdown:**")
            st.dataframe(class_counts, use_container_width=True, hide_index=True, height=130)

        st.markdown("**All Transactions:**")
        st.dataframe(txn_df, use_container_width=True, hide_index=True, height=280)

    st.markdown("---")

    # ── Alerts & Cases ────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🚨 Alerts")
        alerts_df = _get_customer_alerts(customer_id)
        if alerts_df.empty:
            st.success("✅ No alerts on record for this customer.")
        else:
            st.dataframe(alerts_df, use_container_width=True, hide_index=True, height=250)

    with col2:
        st.markdown("### 📋 Investigation Cases")
        cases_df = _get_customer_cases(customer_id)
        if cases_df.empty:
            st.info("No investigation cases filed for this customer.")
        else:
            st.dataframe(cases_df, use_container_width=True, hide_index=True, height=250)

    st.markdown("---")

    # ── Enrichment data if available ─────────────────────────────────────────
    cases_full = get_all_case_ids()
    if not cases_full.empty:
        # Find if there are enrichments for this customer's cases
        from src.dashboard.services.queries import get_case_enrichment as gce
        customer_cases = _run_query(f"""
            SELECT CASE_ID FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE
            WHERE CUSTOMER_ID = '{customer_id}'
            LIMIT 1
        """)
        if not customer_cases.empty:
            case_id = customer_cases.iloc[0]["CASE_ID"]
            enr_df = gce(case_id)
            if not enr_df.empty:
                st.markdown("### 🧬 AI Enrichment Intelligence")

                def _parse_variant(val):
                    if val is None: return {}
                    if isinstance(val, (dict, list)): return val
                    try: return json.loads(val)
                    except: return {}

                row = enr_df.iloc[0]
                hist = _parse_variant(row.get("HISTORICAL_STATS"))
                if hist:
                    h1, h2, h3 = st.columns(3)
                    with h1:
                        st.metric("Avg Txn Amount", f"₹{hist.get('avg_transaction_amount', 0):,.0f}")
                    with h2:
                        st.metric("Std Deviation", f"₹{hist.get('std_dev_amount', 0):,.0f}")
                    with h3:
                        st.metric("Intl Ratio", f"{hist.get('international_txn_ratio', 0):.2%}")

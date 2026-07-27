"""
CasePilot — Customer Portal
==============================
Provides customer-facing dashboard to view recent activity, account status,
approve/deny suspicious transactions, report fraud, and freeze cards.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from src.dashboard.services.queries import (
    get_customer_transactions,
    get_pending_customer_notifications,
    approve_transaction,
    deny_transaction,
    _run_query,
)


def _render_accounts(customer_id: str, customer_name: str):
    st.markdown(f"### 💳 My Accounts")
    st.write(f"Account details and balances for **{customer_name}** ({customer_id}).")

    df = _run_query(f"""
        SELECT ACCOUNT_NUMBER, ACCOUNT_TYPE, BALANCE, ACCOUNT_STATUS, IFSC_CODE, OPENED_AT
        FROM CASEPILOT_DB.RAW.ACCOUNT
        WHERE CUSTOMER_ID = '{customer_id}'
    """)
    if df.empty:
        st.info("No accounts associated with your customer ID.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "BALANCE": st.column_config.NumberColumn("Balance (INR)", format="₹%.2f"),
        }
    )


def _render_transactions(customer_id: str):
    st.markdown("### 📑 My Transactions")
    st.write("Recent activity across all linked accounts.")

    txns = get_customer_transactions(customer_id, limit=50)
    if txns is None or txns.empty:
        st.info("No transactions found.")
        return

    st.dataframe(
        txns,
        use_container_width=True,
        hide_index=True,
        column_config={
            "AMOUNT": st.column_config.NumberColumn("Amount", format="₹%.2f"),
            "CREATED_AT": "Timestamp",
        }
    )


def _render_alerts(customer_id: str):
    st.markdown("### 🔔 Security Alerts & Fraud Notifications")
    st.write("Please review transaction authorization requests from bank fraud prevention.")

    notifs = get_pending_customer_notifications(customer_id)
    if notifs is None or notifs.empty:
        st.success("✅ No pending security alerts. All transactions verified.")
        return

    for idx, row in notifs.iterrows():
        notif_id = row["NOTIFICATION_ID"]
        alert_id = row["ALERT_ID"]
        case_id = row["CASE_ID"]
        message = row["MESSAGE"]
        sent_at = row["SENT_AT"]
        txn_id = row["TXN_ID"]

        date_str = sent_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(sent_at, datetime) else str(sent_at)

        with st.container():
            st.markdown(f"""
            <div style="background-color: #1F2937; border: 1px solid #DC2626; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 700; color: #EF4444; font-size: 0.95rem;">🚨 URGENT: TRANSACTION VERIFICATION</span>
                    <span style="font-size: 0.75rem; color: #9CA3AF;">{date_str}</span>
                </div>
                <p style="color: #F9FAFB; font-size: 0.9rem; margin-bottom: 12px;">{message}</p>
            </div>
            """, unsafe_allow_html=True)

            c1, c2, _ = st.columns([1, 1, 3])
            with c1:
                if st.button("🟢 Yes, it was me", key=f"app_{notif_id}_{idx}", use_container_width=True):
                    if approve_transaction(notif_id, case_id, alert_id):
                        st.success("Transaction authorized!")
                        st.rerun()
            with c2:
                if st.button("🔴 No, NOT me", key=f"deny_{notif_id}_{idx}", use_container_width=True):
                    if deny_transaction(notif_id, case_id, alert_id, txn_id):
                        st.warning("Transaction blocked and card/account frozen!")
                        st.rerun()


def _render_report_fraud(customer_id: str):
    st.markdown("### 📢 Report Fraud")
    st.write("Report suspicious or unauthorized charges to the Bank Fraud Desk.")

    with st.form("report_fraud_form"):
        account_num = st.text_input("Account Number")
        amount = st.number_input("Transaction Amount (INR)", min_value=0.0)
        desc = st.text_area("Description / Merchant Details")
        submitted = st.form_submit_button("Submit Fraud Report")

        if submitted:
            st.success("✅ Fraud report submitted successfully. An investigator will review your claim immediately.")


def _render_freeze_card(customer_id: str):
    st.markdown("### 🔒 Freeze Card / Lock Account")
    st.write("Instantly lock your card or account to prevent further transactions.")

    df = _run_query(f"""
        SELECT ACCOUNT_ID, ACCOUNT_NUMBER, ACCOUNT_TYPE, ACCOUNT_STATUS
        FROM CASEPILOT_DB.RAW.ACCOUNT
        WHERE CUSTOMER_ID = '{customer_id}'
    """)
    if df.empty:
        st.info("No accounts found.")
        return

    for idx, row in df.iterrows():
        acc_id = row["ACCOUNT_ID"]
        acc_num = row["ACCOUNT_NUMBER"]
        status = row["ACCOUNT_STATUS"]

        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**Account:** `{acc_num}` ({row['ACCOUNT_TYPE']}) — Status: `{status}`")
        with c2:
            if status == "ACTIVE":
                if st.button("🔒 Lock Card", key=f"lock_{acc_id}"):
                    from src.dashboard.services.queries import update_account_status
                    update_account_status(acc_id, "FROZEN")
                    st.success(f"Locked {acc_num}")
                    st.rerun()
            else:
                if st.button("🔓 Unlock Card", key=f"unlock_{acc_id}"):
                    from src.dashboard.services.queries import update_account_status
                    update_account_status(acc_id, "ACTIVE")
                    st.success(f"Unlocked {acc_num}")
                    st.rerun()


def render(subpage: str):
    customer_id = st.session_state.get("customer_id", "CUST001")
    customer_name = st.session_state.get("customer_name", "Valued Customer")

    if subpage in ("💳 My Accounts", "📱 My Portal"):
        _render_accounts(customer_id, customer_name)
    elif subpage in ("📑 My Transactions",):
        _render_transactions(customer_id)
    elif subpage in ("🔔 Security Alerts", "✅ Verify Transaction"):
        _render_alerts(customer_id)
    elif subpage in ("📢 Report Fraud",):
        _render_report_fraud(customer_id)
    elif subpage in ("🔒 Freeze Card",):
        _render_freeze_card(customer_id)
    else:
        _render_accounts(customer_id, customer_name)

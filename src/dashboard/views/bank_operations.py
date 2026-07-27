"""
CasePilot — Bank Employee Portal
===================================
Provides dashboard views for bank employees to review customer accounts,
transaction history, KYC status, open investigation cases, and customer verification requests.
"""

import streamlit as st
import pandas as pd
from src.dashboard.services.queries import (
    get_bank_accounts_overview,
    get_open_cases_for_bank,
    update_account_status,
    get_customer_verification_requests,
    get_notification_logs,
    get_total_transactions,
    _run_query,
)


def _render_accounts():
    st.markdown("### 🏦 Customer Accounts")
    st.write("Search accounts, check account status, and perform freeze/unfreeze actions.")

    total_txns = get_total_transactions()
    if total_txns == 0:
        st.info("No transaction or account dataset uploaded.")

    search_term = st.text_input("🔍 Search by Customer Name or Account Number", value="", placeholder="Type customer name or account number...")
    accounts = get_bank_accounts_overview(search_term if search_term != "" else None)

    if accounts is None or accounts.empty:
        st.info("No customer accounts found.")
        return

    st.dataframe(
        accounts,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ACCOUNT_ID": "Account ID",
            "ACCOUNT_NUMBER": "Account Number",
            "ACCOUNT_TYPE": "Type",
            "BALANCE": st.column_config.NumberColumn("Balance (INR)", format="₹%.2f"),
            "ACCOUNT_STATUS": "Status",
            "CUSTOMER_NAME": "Customer Name",
            "RISK_RATING": "Risk",
            "KYC_STATUS": "KYC Status",
        }
    )

    st.markdown("<hr style='border-color: #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)
    st.markdown("#### 🔒 Account Actions")

    for idx, row in accounts.head(10).iterrows():
        acc_id = row["ACCOUNT_ID"]
        acc_num = row["ACCOUNT_NUMBER"]
        status = row["ACCOUNT_STATUS"]
        name = row["CUSTOMER_NAME"]

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"**{name}** ({acc_num}) — Status: `{status}`")
        with c2:
            if status == "ACTIVE":
                if st.button("🔒 Freeze", key=f"frz_{acc_id}"):
                    if update_account_status(acc_id, "FROZEN"):
                        st.success(f"Frozen account {acc_num}")
                        st.rerun()
            else:
                if st.button("🔓 Unfreeze", key=f"unfrz_{acc_id}"):
                    if update_account_status(acc_id, "ACTIVE"):
                        st.success(f"Activated account {acc_num}")
                        st.rerun()


def _render_txn_history():
    st.markdown("### 📜 Transaction History")
    st.write("Review recent customer transactions across channels.")

    total_txns = get_total_transactions()
    if total_txns == 0:
        st.info("No transaction dataset uploaded.")
        return

    df = _run_query("""
        SELECT TXN_ID, CUSTOMER_ID, ACCOUNT_ID, AMOUNT, CHANNEL, STATUS, CLASSIFICATION, TXN_TIMESTAMP, DESCRIPTION
        FROM CASEPILOT_DB.RAW.TRANSACTION
        ORDER BY TXN_TIMESTAMP DESC
        LIMIT 100
    """)
    if df.empty:
        st.info("No transaction records.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "AMOUNT": st.column_config.NumberColumn("Amount", format="₹%.2f"),
            "TXN_TIMESTAMP": "Timestamp",
        }
    )


def _render_kyc():
    st.markdown("### 📋 KYC Details")
    st.write("Customer Know-Your-Customer verification records and compliance ratings.")

    accounts = get_bank_accounts_overview()
    if accounts is None or accounts.empty:
        st.info("No customer KYC records found.")
        return

    kyc_df = accounts[["CUSTOMER_ID", "CUSTOMER_NAME", "KYC_STATUS", "RISK_RATING", "ACCOUNT_NUMBER"]].drop_duplicates()
    st.dataframe(kyc_df, use_container_width=True, hide_index=True)


def _render_open_cases():
    st.markdown("### 🚨 Open Investigation Cases")
    st.write("View active cases escalated to bank operations.")

    cases = get_open_cases_for_bank()
    if cases is None or cases.empty:
        st.success("🎉 No active cases pending bank employee review.")
        return

    st.dataframe(cases, use_container_width=True, hide_index=True)


def _render_verification_requests():
    st.markdown("### 📩 Customer Verification Requests")
    st.write("Manage outbound transaction verification notices sent to customers.")

    notifs = get_notification_logs(limit=50)
    if notifs is None or notifs.empty:
        st.info("No pending verification requests found.")
        return

    st.dataframe(notifs, use_container_width=True, hide_index=True)


def render(subpage: str):
    if subpage in ("🏦 Customer Accounts", "🏢 Bank Operations"):
        _render_accounts()
    elif subpage in ("📜 Transaction History",):
        _render_txn_history()
    elif subpage in ("📋 KYC Details", "👤 Customer Accounts & KYC"):
        _render_kyc()
    elif subpage in ("🚨 Open Cases", "📋 Open Cases Queue"):
        _render_open_cases()
    elif subpage in ("📩 Customer Verification Requests",):
        _render_verification_requests()
    else:
        _render_accounts()

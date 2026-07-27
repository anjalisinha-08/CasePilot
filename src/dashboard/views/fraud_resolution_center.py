"""
CasePilot — Fraud Resolution Center
=====================================
Enterprise banking view for tracking fraud recovery operations,
loss prevention, chargebacks, and active recovery workflows.
Calculates all financial figures directly from the uploaded dataset.
"""

import streamlit as st
import plotly.express as px
import pandas as pd

from src.dashboard.services.queries import (
    get_total_transactions,
    get_total_transaction_value,
    get_total_fraud_amount,
    get_blocked_transaction_amount,
    get_money_recovered,
    get_fraud_loss_prevented,
    get_recovery_rate,
    get_active_recovery_cases,
    get_recovered_cases,
    get_pending_recovery_count,
    get_cases_closed_today,
    get_confirmed_fraud,
    get_all_recoveries,
    get_recoveries_by_status,
    format_inr,
)


def render():
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="color:#F9FAFB; margin-bottom:2px; font-size: 1.4rem; font-weight: 700;">
            💸 Fraud Resolution Center
        </h2>
        <p style="color:#6B7280; font-size:0.8rem;">
            Real-time loss prevention, recovery workflow oversight, and chargeback tracking.
        </p>
    </div>
    """, unsafe_allow_html=True)

    total_txns = get_total_transactions()
    if total_txns == 0:
        st.markdown("""
        <div style="background-color: #1F2937; border: 1px solid #374151; border-radius: 8px; padding: 40px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 12px;">📭</div>
            <h3 style="color: #F9FAFB; margin-bottom: 8px;">No dataset uploaded</h3>
            <p style="color: #9CA3AF; font-size: 0.9rem; max-width: 450px; margin: 0 auto 16px auto;">
                Upload a transaction dataset to calculate financial metrics, fraud loss prevention, and recovery case statuses.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Calculate financial metrics
    total_val = get_total_transaction_value()
    fraud_amt = get_total_fraud_amount()
    blocked_amt = get_blocked_transaction_amount()
    recovered_amt = get_money_recovered()
    loss_prevented = blocked_amt + recovered_amt
    recovery_rate = get_recovery_rate()
    active_recovery = get_active_recovery_cases()
    recovered_cases = get_recovered_cases()
    pending_recovery = get_pending_recovery_count()
    cases_closed = get_cases_closed_today()

    # Financial KPI Grid — Row 1
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Transaction Value", format_inr(total_val))
    with m2:
        st.metric("Total Fraud Amount", format_inr(fraud_amt))
    with m3:
        st.metric("Blocked Txn Amount", format_inr(blocked_amt))
    with m4:
        st.metric("Recovered Amount", format_inr(recovered_amt))
    with m5:
        st.metric("Fraud Loss Prevented", format_inr(loss_prevented))

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

    # Operational KPI Grid — Row 2
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Recovery Rate", f"{recovery_rate:.1f}%")
    with c2:
        st.metric("Active Recovery Cases", f"{active_recovery:,}")
    with c3:
        st.metric("Recovered Cases", f"{recovered_cases:,}")
    with c4:
        st.metric("Pending Recovery", f"{pending_recovery:,}")
    with c5:
        st.metric("Cases Closed", f"{cases_closed:,}")

    st.markdown("<hr style='border-color: #1F2937; margin: 20px 0;'>", unsafe_allow_html=True)

    # Recovery breakdown table & charts
    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown('<div class="section-header">📋 Fraud Recovery Logs</div>', unsafe_allow_html=True)
        rec_df = get_all_recoveries()
        if rec_df is not None and not rec_df.empty:
            rec_display = rec_df.copy()
            if "FRAUD_AMOUNT" in rec_display.columns:
                rec_display["FRAUD_AMOUNT"] = rec_display["FRAUD_AMOUNT"].apply(lambda x: format_inr(float(x)))
            if "RECOVERED_AMOUNT" in rec_display.columns:
                rec_display["RECOVERED_AMOUNT"] = rec_display["RECOVERED_AMOUNT"].apply(lambda x: format_inr(float(x)))

            st.dataframe(
                rec_display,
                use_container_width=True,
                hide_index=True,
                height=350,
                column_config={
                    "RECOVERY_ID": "Recovery ID",
                    "CASE_ID": "Case ID",
                    "CUSTOMER_ID": "Customer ID",
                    "FRAUD_AMOUNT": "Fraud Amount",
                    "RECOVERED_AMOUNT": "Recovered",
                    "RECOVERY_STATUS": "Status",
                    "RECOVERY_METHOD": "Method",
                    "UPDATED_AT": "Last Updated",
                }
            )
        else:
            st.info("No active fraud recovery cases log found.")

    with col2:
        st.markdown('<div class="section-header">📊 Recovery Status Distribution</div>', unsafe_allow_html=True)
        status_df = get_recoveries_by_status()
        if status_df is not None and not status_df.empty:
            fig = px.pie(
                status_df,
                names="RECOVERY_STATUS",
                values="CASE_COUNT",
                color_discrete_sequence=["#059669", "#D97706", "#DC2626", "#2563EB"],
                hole=0.4
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9CA3AF"),
                margin=dict(l=20, r=20, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No recovery status distribution data.")

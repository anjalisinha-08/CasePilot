"""
CasePilot 2.0 — Recovery Tracking Dashboard View
=================================================
Displays fraud recovery pipeline statistics, status breakdown, methods, and transaction log.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.dashboard.services.queries import (
    get_money_recovered,
    get_fraud_loss_prevented,
    get_recovery_cases_count,
    get_recoveries_by_status,
    get_all_recoveries
)


def render():
    st.markdown("""
        <h2 style='color: #F1F5F9; font-weight: 600; margin-bottom: 2px;'>💸 Recovery Tracking</h2>
        <p style='color: #94A3B8; font-size: 0.9rem; margin-bottom: 24px;'>
            Monitor and track recovery cases, blocked transaction amounts, and recovery success rates across channels.
        </p>
    """, unsafe_allow_html=True)

    # Fetch data
    total_recovered = get_money_recovered()
    loss_prevented = get_fraud_loss_prevented()
    recovery_cases = get_recovery_cases_count()
    status_df = get_recoveries_by_status()
    all_rec_df = get_all_recoveries()

    # KPI summary metrics
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Money Recovered", f"₹{total_recovered:,.2f}")
    with m2:
        st.metric("Fraud Loss Prevented", f"₹{loss_prevented:,.2f}")
    with m3:
        st.metric("Active Recovery Cases", f"{recovery_cases:,}")
    with m4:
        # Calculate overall recovery rate
        if not status_df.empty:
            total_fraud_amt = status_df["TOTAL_FRAUD"].sum()
            total_rec_amt = status_df["TOTAL_RECOVERED"].sum()
            rate = (total_rec_amt / total_fraud_amt * 100) if total_fraud_amt > 0 else 0.0
            st.metric("Recovery Rate", f"{rate:.2f}%")
        else:
            st.metric("Recovery Rate", "0.00%")

    st.markdown("<br>", unsafe_allow_html=True)

    # Status breakdown and charts
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Recoveries by Status</h4>", unsafe_allow_html=True)
        if not status_df.empty:
            fig_pie = px.pie(
                status_df,
                names='RECOVERY_STATUS',
                values='CASE_COUNT',
                color='RECOVERY_STATUS',
                color_discrete_map={
                    "COMPLETED": "#10B981",
                    "PARTIAL": "#F59E0B",
                    "PENDING": "#3B82F6",
                    "FAILED": "#EF4444"
                }
            )
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=10, b=10)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No recovery status data available.")

    with c2:
        st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Recovery Efficiency (Amount)</h4>", unsafe_allow_html=True)
        if not status_df.empty:
            fig_bar = px.bar(
                status_df,
                x='RECOVERY_STATUS',
                y=['TOTAL_FRAUD', 'TOTAL_RECOVERED'],
                barmode='group',
                labels={"value": "Amount (₹)", "variable": "Metric"},
                color_discrete_sequence=["#EF4444", "#10B981"]
            )
            fig_bar.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#1E293B'),
                margin=dict(l=20, r=20, t=10, b=10)
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No recovery amount data available.")

    st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)

    # Detailed recovery tracking list
    st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Recovery Cases Listing</h4>", unsafe_allow_html=True)
    if all_rec_df is not None and not all_rec_df.empty:
        # Format columns for display
        display_rec = all_rec_df.copy()
        display_rec["FRAUD_AMOUNT"] = display_rec["FRAUD_AMOUNT"].apply(lambda x: f"₹{x:,.2f}")
        display_rec["RECOVERED_AMOUNT"] = display_rec["RECOVERED_AMOUNT"].apply(lambda x: f"₹{x:,.2f}")
        display_rec = display_rec.rename(columns={
            "RECOVERY_ID": "Recovery ID",
            "CASE_ID": "Case ID",
            "CUSTOMER_ID": "Customer ID",
            "FRAUD_AMOUNT": "Fraud Amount",
            "RECOVERED_AMOUNT": "Recovered Amount",
            "RECOVERY_STATUS": "Status",
            "RECOVERY_METHOD": "Method",
            "UPDATED_AT": "Last Updated"
        })
        st.dataframe(display_rec, use_container_width=True, hide_index=True)
    else:
        st.info("No recovery cases currently registered.")

"""
CasePilot 2.0 — Management Reporting Dashboard View
======================================================
Displays customer response loopback logs, alert dispatch metrics,
notification channels breakdown, and automated action audits.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from src.dashboard.services import queries


def render():
    st.markdown("""
        <h2 style='color: #F1F5F9; font-weight: 600; margin-bottom: 2px;'>📋 Customer Response & Management Audit</h2>
        <p style='color: #94A3B8; font-size: 0.9rem; margin-bottom: 24px;'>
            Audit customer responses (SMS, Push notifications) and track automatic case escalations or false positive closures.
        </p>
    """, unsafe_allow_html=True)

    # Fetch data
    stats_df = queries.get_notification_stats()
    logs_df = queries.get_notification_logs(limit=30)

    if stats_df.empty:
        st.warning("No notification statistics found. Please ensure the simulator and orchestrator are running.")
        return

    # Aggregate key stats
    total_sent = stats_df['NOTIF_COUNT'].sum()
    responded_df = stats_df[stats_df['STATUS'] == 'RESPONDED']
    total_responded = responded_df['NOTIF_COUNT'].sum()
    
    response_rate = (total_responded / total_sent * 100) if total_sent > 0 else 0.0

    yes_responses = stats_df[stats_df['CUSTOMER_RESPONSE'] == 'YES']['NOTIF_COUNT'].sum()
    no_responses = stats_df[stats_df['CUSTOMER_RESPONSE'] == 'NO']['NOTIF_COUNT'].sum()
    no_response_count = total_sent - total_responded

    # Render summary KPIs
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(label="Total Alerts Dispatched", value=f"{total_sent:,}")
    with m2:
        st.metric(label="Total Responses Received", value=f"{total_responded:,}")
    with m3:
        st.metric(label="Response Rate", value=f"{response_rate:.1f}%")
    with m4:
        st.metric(label="Escalated Fraud Reports", value=f"{no_responses:,}")

    st.markdown("<br>", unsafe_allow_html=True)

    # Response charts
    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Customer Response Loopback Outcomes</h4>", unsafe_allow_html=True)
        response_pie = pd.DataFrame({
            "Outcome": ["Confirmed Authorized (YES)", "Reported Fraud (NO)", "Unanswered/Ignored"],
            "Count": [yes_responses, no_responses, no_response_count]
        })
        fig_pie = px.pie(
            response_pie,
            names='Outcome',
            values='Count',
            color='Outcome',
            color_discrete_map={
                "Confirmed Authorized (YES)": "#10B981",
                "Reported Fraud (NO)": "#EF4444",
                "Unanswered/Ignored": "#64748B"
            }
        )
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94A3B8'),
            margin=dict(l=20, r=20, t=10, b=10)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Channel Distribution</h4>", unsafe_allow_html=True)
        # Use log counts to get channels
        if not logs_df.empty:
            channel_counts = logs_df.groupby('CHANNEL').size().reset_index(name='Count')
            fig_bar = px.bar(
                channel_counts,
                x='CHANNEL',
                y='Count',
                color='CHANNEL',
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_bar.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#1E293B'),
                margin=dict(l=20, r=20, t=10, b=10),
                showlegend=False
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No notification records to analyze.")

    st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)

    # Detailed notification log table
    st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Audit Log: Recent Customer Communications & Actions</h4>", unsafe_allow_html=True)
    if not logs_df.empty:
        # Display clean format
        display_logs = logs_df[[
            'NOTIFICATION_ID', 'CUSTOMER_ID', 'CASE_ID', 'CHANNEL',
            'STATUS', 'CUSTOMER_RESPONSE', 'RESPONSE_ACTION', 'SENT_AT'
        ]].copy()
        
        # Shorten IDs for readability
        display_logs['NOTIFICATION_ID'] = display_logs['NOTIFICATION_ID'].apply(lambda x: f"{x[:8]}...")
        display_logs['CUSTOMER_ID'] = display_logs['CUSTOMER_ID'].apply(lambda x: f"{x[:8]}...")
        display_logs['CASE_ID'] = display_logs['CASE_ID'].apply(lambda x: f"{x[:8]}..." if x else "N/A")

        st.dataframe(
            display_logs,
            column_config={
                "NOTIFICATION_ID": "Notification ID",
                "CUSTOMER_ID": "Customer ID",
                "CASE_ID": "Case ID",
                "CHANNEL": "Channel",
                "STATUS": "Delivery Status",
                "CUSTOMER_RESPONSE": "Customer Reply",
                "RESPONSE_ACTION": "Automated Remediation",
                "SENT_AT": "Sent Time"
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No recent customer response loopback logs available.")

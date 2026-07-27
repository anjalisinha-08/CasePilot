"""
CasePilot Dashboard — Risk Analytics Page
============================================
Comprehensive analytics: risk distribution, alert types, priority
histograms, top risky customers, accounts, merchants, and devices.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.services.queries import (
    get_risk_band_distribution, get_alert_type_distribution,
    get_priority_score_data, get_top_high_risk_customers,
    get_top_merchants_by_alerts, get_top_devices_by_alerts,
    get_cases_over_time,
)

CHART_COLORS = {"CRITICAL": "#DC2626", "HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#10B981"}
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#94A3B8"),
    margin=dict(l=20, r=20, t=40, b=20),
)


def render():
    """Render the Risk Analytics page."""
    st.markdown("""
    <h2 style="color:#F1F5F9; margin-bottom:4px;">📈 Risk Analytics</h2>
    <p style="color:#64748B; font-size:0.85rem; margin-bottom:20px;">
        Deep analytics on risk posture, alert patterns, and high-risk entities.
    </p>
    """, unsafe_allow_html=True)

    # ── Row 1: Risk Band + Alert Type ────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">🎯 Risk Band Distribution</div>', unsafe_allow_html=True)
        df = get_risk_band_distribution()
        if not df.empty:
            fig = px.pie(df, values="CASE_COUNT", names="RISK_BAND",
                         color="RISK_BAND", color_discrete_map=CHART_COLORS, hole=0.45)
            fig.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=True)
            fig.update_traces(textposition="inside", textinfo="percent+label",
                              marker=dict(line=dict(color="#0F172A", width=2)))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available.")

    with col2:
        st.markdown('<div class="section-header">🔔 Alert Type Distribution</div>', unsafe_allow_html=True)
        df = get_alert_type_distribution()
        if not df.empty:
            fig = go.Figure(go.Bar(
                x=df["ALERT_COUNT"], y=df["ALERT_TYPE"],
                orientation="h",
                marker_color="#3B82F6",
                marker_line_color="#1E293B", marker_line_width=1,
                text=df["ALERT_COUNT"], textposition="outside",
                textfont=dict(color="#F1F5F9"),
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=320,
                              xaxis=dict(gridcolor="#1E293B"),
                              yaxis=dict(gridcolor="#1E293B", autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available.")

    st.markdown("---")

    # ── Row 2: Priority Histogram + Cases Over Time ──────────────────────
    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="section-header">📊 Priority Score Histogram</div>', unsafe_allow_html=True)
        df = get_priority_score_data()
        if not df.empty:
            fig = go.Figure(go.Histogram(
                x=df["PRIORITY_SCORE"], nbinsx=20,
                marker_color="#3B82F6", marker_line_color="#1E293B",
                marker_line_width=1, opacity=0.85,
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=320,
                              xaxis_title="Score", yaxis_title="Count",
                              xaxis=dict(gridcolor="#1E293B"),
                              yaxis=dict(gridcolor="#1E293B"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available.")

    with col4:
        st.markdown('<div class="section-header">📅 Cases Over Time</div>', unsafe_allow_html=True)
        df = get_cases_over_time()
        if not df.empty:
            fig = go.Figure(go.Scatter(
                x=df["CASE_DATE"], y=df["CASE_COUNT"],
                mode="lines+markers",
                line=dict(color="#3B82F6", width=2),
                marker=dict(size=6, color="#2563EB"),
                fill="tozeroy",
                fillcolor="rgba(37,99,235,0.1)",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=320,
                              xaxis_title="Date", yaxis_title="Cases",
                              xaxis=dict(gridcolor="#1E293B"),
                              yaxis=dict(gridcolor="#1E293B"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available.")

    st.markdown("---")

    # ── Row 3: Top High-Risk Entities ────────────────────────────────────
    st.markdown('<div class="section-header">🔥 Top High-Risk Entities</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🧑 Customers", "🏪 Merchants", "📱 Devices"])

    with tab1:
        df = get_top_high_risk_customers(10)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True, height=350,
                         column_config={
                             "PRIORITY_SCORE": st.column_config.ProgressColumn(
                                 "Score", min_value=0, max_value=100, format="%.1f"
                             ),
                         })
        else:
            st.info("No high-risk customer data.")

    with tab2:
        df = get_top_merchants_by_alerts(10)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True, height=350)
        else:
            st.info("No merchant alert data.")

    with tab3:
        df = get_top_devices_by_alerts(10)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True, height=350)
        else:
            st.info("No device alert data.")

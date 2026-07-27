"""
CasePilot — Operations Dashboard (Executive View)
====================================================
Enterprise-grade AML operations dashboard with operational banking KPIs,
AI summary banner, case status distribution, alert trends, and live event feed.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.services.queries import (
    get_total_transactions, get_total_transaction_value,
    get_suspicious_transactions, get_alerts_generated,
    get_active_cases, get_confirmed_fraud, get_false_positives,
    get_customer_verification_requests, get_accounts_frozen,
    get_money_recovered, get_blocked_transaction_amount,
    get_fraud_loss_prevented, get_cases_closed_today,
    get_avg_investigation_time, get_avg_resolution_time,
    get_pending_review_count, get_risk_band_distribution,
    get_alert_severity_distribution, get_recent_cases,
    get_case_status_breakdown, get_live_event_feed,
    format_inr,
)

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#9CA3AF"),
    margin=dict(l=20, r=20, t=40, b=20),
)


def _render_ai_summary(total_txns: int):
    """Render top AI Copilot Summary Banner."""
    if total_txns == 0:
        return

    suspicious = get_suspicious_transactions()
    alerts = get_alerts_generated()
    active_cases = get_active_cases()
    
    # Calculate realistic estimated analyst effort saved
    est_hours = max(1, round(total_txns * 0.006, 1))
    est_mins = max(5, round(active_cases * 1.5))

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(30,64,175,0.12), rgba(17,24,39,0.9));
                border: 1px solid rgba(59,130,246,0.3); border-radius: 8px;
                padding: 18px 22px; margin-bottom: 20px;">
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 1.3rem; margin-right: 10px;">🤖</span>
            <span style="color: #F9FAFB; font-weight: 700; font-size: 1.05rem;">
                AI Investigation Copilot Summary
            </span>
        </div>
        <p style="color: #E5E7EB; font-size: 0.92rem; line-height: 1.5; margin-bottom: 0;">
            CasePilot analyzed <strong>{total_txns:,}</strong> transactions.
            <strong>{suspicious:,}</strong> suspicious activities detected.
            <strong>{alerts:,}</strong> alerts generated.
            <strong>{active_cases:,}</strong> cases require immediate investigation.
            Estimated analyst effort reduced from approximately <strong>{est_hours} hours</strong> to less than <strong>{est_mins} minutes</strong>.
        </p>
    </div>
    """, unsafe_allow_html=True)


def _render_kpis(total_txns: int):
    """Render 14+ Operational Banking KPI Cards."""
    total_val = get_total_transaction_value()
    suspicious = get_suspicious_transactions()
    alerts = get_alerts_generated()
    active = get_active_cases()
    confirmed = get_confirmed_fraud()
    fp = get_false_positives()
    verification_pending = get_customer_verification_requests()
    accounts_frozen = get_accounts_frozen()
    recovered = get_money_recovered()
    blocked = get_blocked_transaction_amount()
    loss_prevented = blocked + recovered
    closed_today = get_cases_closed_today()
    avg_inv_time = get_avg_investigation_time()
    avg_res_time = get_avg_resolution_time()

    # Row 1 — Transaction & Alert Volume
    r11, r12, r13, r14, r15 = st.columns(5)
    with r11:
        st.metric("Total Transactions", f"{total_txns:,}")
    with r12:
        st.metric("Total Txn Value", format_inr(total_val))
    with r13:
        st.metric("Suspicious Txns", f"{suspicious:,}")
    with r14:
        st.metric("Alerts Generated", f"{alerts:,}")
    with r15:
        st.metric("Active Cases", f"{active:,}")

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

    # Row 2 — Fraud & Account Status
    r21, r22, r23, r24, r25 = st.columns(5)
    with r21:
        st.metric("Confirmed Fraud", f"{confirmed:,}")
    with r22:
        st.metric("False Positives", f"{fp:,}")
    with r23:
        st.metric("Verification Pending", f"{verification_pending:,}")
    with r24:
        st.metric("Accounts Frozen", f"{accounts_frozen:,}")
    with r25:
        st.metric("Cases Closed Today", f"{closed_today:,}")

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

    # Row 3 — Financial Loss Prevention & Speed
    r31, r32, r33, r34 = st.columns(4)
    with r31:
        st.metric("Recovered Amount", format_inr(recovered))
    with r32:
        st.metric("Fraud Loss Prevented", format_inr(loss_prevented))
    with r33:
        st.metric("Avg Investigation Time", f"{avg_inv_time:.1f} hrs")
    with r34:
        st.metric("Avg Resolution Time", f"{avg_res_time:.1f} hrs")


def _render_case_status_chart():
    """Case status distribution donut chart."""
    df = get_case_status_breakdown()
    if df.empty:
        return

    status_colors = {
        "FRAUD_CONFIRMED": "#DC2626",
        "ACCOUNT_FROZEN": "#EF4444",
        "MONEY_RECOVERED": "#059669",
        "FALSE_POSITIVE": "#6B7280",
        "CUSTOMER_VERIFIED": "#2563EB",
        "CUSTOMER_CONTACTED": "#D97706",
        "UNDER_REVIEW": "#F59E0B",
        "NEW": "#3B82F6",
        "CLOSED": "#4B5563",
    }
    fig = px.pie(
        df, values="CASE_COUNT", names="CASE_STATUS",
        color="CASE_STATUS",
        color_discrete_map=status_colors,
        hole=0.45,
    )
    fig.update_layout(**PLOTLY_LAYOUT, title="Case Status Distribution", showlegend=True, height=320)
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        textfont_size=10,
        marker=dict(line=dict(color="#0B1120", width=1.5))
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_risk_distribution():
    """Risk band distribution chart."""
    df = get_risk_band_distribution()
    if df.empty:
        return
    risk_colors = {"CRITICAL": "#DC2626", "HIGH": "#EF4444", "MEDIUM": "#D97706", "LOW": "#059669"}
    fig = go.Figure(go.Bar(
        x=df["RISK_BAND"], y=df["CASE_COUNT"],
        marker_color=[risk_colors.get(b, "#6B7280") for b in df["RISK_BAND"]],
        marker_line_color="#0B1120", marker_line_width=1,
        text=df["CASE_COUNT"], textposition="outside",
        textfont=dict(color="#9CA3AF", size=10),
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title="Risk Band Distribution",
                      xaxis_title=None, yaxis_title="Count", height=320,
                      xaxis=dict(gridcolor="#1F2937"), yaxis=dict(gridcolor="#1F2937"))
    st.plotly_chart(fig, use_container_width=True)


def _render_recent_queue():
    """Recent investigation cases table."""
    df = get_recent_cases(15)
    if df.empty:
        return
    display_cols = ["CASE_NUMBER", "CUSTOMER_ID", "CASE_STATUS",
                    "ASSIGNED_TO", "PRIORITY_SCORE", "RISK_BAND", "CREATED_AT"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[available],
        use_container_width=True,
        hide_index=True,
        height=320,
        column_config={
            "PRIORITY_SCORE": st.column_config.ProgressColumn(
                "Priority", min_value=0, max_value=100, format="%.0f"
            ),
            "CREATED_AT": st.column_config.DatetimeColumn("Created", format="YYYY-MM-DD HH:mm"),
        }
    )


def _render_live_feed():
    """Render live event feed."""
    try:
        df = get_live_event_feed(limit=12)
        if df.empty:
            st.info("No timeline events.")
            return

        for _, row in df.iterrows():
            etype = row["EVENT_TYPE"]
            etime = row["EVENT_TIME"].strftime("%H:%M:%S")
            desc = row["DESCRIPTION"]

            icon = "💸"
            color = "#2563EB"
            if etype == "ALERT":
                icon = "🚨"
                color = "#DC2626"
            elif etype == "CASE":
                icon = "📋"
                color = "#D97706"
            elif etype == "NOTIFICATION":
                icon = "📩"
                color = "#059669"

            st.markdown(f"""
            <div style="display: flex; align-items: flex-start; margin-bottom: 8px;
                        padding: 8px 12px; background: rgba(31,41,55,0.5);
                        border-left: 3px solid {color}; border-radius: 4px;">
                <div style="font-size: 1.1rem; margin-right: 10px; padding-top: 1px;">{icon}</div>
                <div>
                    <div style="font-size: 0.65rem; color: #6B7280;">{etime} · <strong>{etype}</strong></div>
                    <div style="font-size: 0.78rem; color: #D1D5DB; margin-top: 1px;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading event feed: {e}")


def render():
    """Render the Operations Dashboard page."""
    user_name = st.session_state.get("user_name", "Analyst")
    st.markdown(f"""
    <div style="margin-bottom: 20px;">
        <h2 style="color:#F9FAFB; margin-bottom:2px; font-size: 1.4rem; font-weight: 700;">
            📊 Operations Dashboard
        </h2>
        <p style="color:#6B7280; font-size:0.8rem;">
            Real-time AML investigation pipeline health · Logged in as <strong style="color:#9CA3AF;">{user_name}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    total_txns = get_total_transactions()

    # Empty State check
    if total_txns == 0:
        st.markdown("""
        <div style="background-color: #1F2937; border: 1px solid #374151; border-radius: 8px; padding: 40px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3.5rem; margin-bottom: 16px;">📭</div>
            <h3 style="color: #F9FAFB; margin-bottom: 8px; font-size: 1.3rem;">No dataset uploaded</h3>
            <p style="color: #9CA3AF; font-size: 0.95rem; max-width: 500px; margin: 0 auto 24px auto; line-height: 1.5;">
                Upload a transaction dataset to begin analysis. The AI fraud detection pipeline will evaluate transactions, generate alerts, and populate investigation metrics.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Render AI Copilot Summary Banner
    _render_ai_summary(total_txns)

    # Render KPIs
    _render_kpis(total_txns)
    st.markdown("<hr style='border-color: #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # Charts row 1
    col1, col2 = st.columns(2)
    with col1:
        _render_case_status_chart()
    with col2:
        _render_risk_distribution()

    # Recent cases & feed
    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="section-header">🚨 Recent Investigation Queue</div>', unsafe_allow_html=True)
        _render_recent_queue()
    with col4:
        st.markdown('<div class="section-header">⚡ Live Event Feed</div>', unsafe_allow_html=True)
        _render_live_feed()

"""
CasePilot — AI Copilot Panel
================================
AI-powered investigation assistant summarizing today's operations,
highlighting high-priority cases, and recommending analyst actions.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from src.dashboard.services.queries import (
    get_ai_copilot_data,
    get_total_transactions,
    get_false_positives,
    get_confirmed_fraud,
    get_active_cases,
    get_pending_review_count,
)


def _render_summary_card(title, icon, value, subtitle="", color="#3B82F6"):
    """Render a single summary stat."""
    st.markdown(f"""
    <div style="background: #1F2937; border: 1px solid #374151; border-radius: 8px;
                padding: 14px 18px; margin-bottom: 8px;">
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 1.2rem; margin-right: 8px;">{icon}</span>
            <span style="color: #9CA3AF; font-size: 0.72rem; text-transform: uppercase;
                         letter-spacing: 0.5px;">{title}</span>
        </div>
        <div style="font-size: 1.6rem; font-weight: 700; color: {color};">{value}</div>
        <div style="font-size: 0.72rem; color: #6B7280; margin-top: 2px;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def render():
    """Render the AI Copilot page."""
    now = datetime.now()
    user_name = st.session_state.get("user_name", "Analyst")

    st.markdown(f"""
    <div style="margin-bottom: 20px;">
        <h2 style="color:#F9FAFB; margin-bottom:2px; font-size: 1.4rem; font-weight: 700;">
            🤖 AI Investigation Copilot
        </h2>
        <p style="color:#6B7280; font-size:0.8rem;">
            Automated investigation summary · {now.strftime('%A, %d %B %Y %H:%M IST')}
        </p>
    </div>
    """, unsafe_allow_html=True)

    total_txns = get_total_transactions()
    if total_txns == 0:
        st.markdown("""
        <div style="background-color: #1F2937; border: 1px solid #374151; border-radius: 8px; padding: 40px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 12px;">🤖</div>
            <h3 style="color: #F9FAFB; margin-bottom: 8px;">No dataset uploaded</h3>
            <p style="color: #9CA3AF; font-size: 0.9rem; max-width: 450px; margin: 0 auto 16px auto;">
                Upload a transaction dataset to enable AI Copilot briefings, high-priority case highlighting, and efficiency metrics.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Fetch aggregated copilot data
    data = get_ai_copilot_data()

    hp_df = data["high_priority_cases"]

    # ── Daily Briefing ───────────────────────────────────────────────────
    st.markdown("""
    <div class="copilot-panel">
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 1.3rem; margin-right: 10px;">📋</span>
            <span style="color: #F9FAFB; font-weight: 600; font-size: 1rem;">Daily Investigation Briefing</span>
        </div>
    """, unsafe_allow_html=True)

    # Build AI summary text
    pending = data["pending_review"]
    confirmed = data["confirmed_fraud"]
    fp = data["false_positives"]
    recovered = data["recovered_amount"]
    automation_rate = data["automation_rate"]
    active = data["active_cases"]

    total_resolved = confirmed + fp
    avg_time_saved = round(total_resolved * 0.35, 1)  # ~21 min saved per automated triage

    briefing = f"""
    Good {'morning' if now.hour < 12 else 'afternoon' if now.hour < 17 else 'evening'}, **{user_name}**.

    Here is your investigation status summary:

    - **{pending:,}** cases are pending analyst review — prioritize CRITICAL and HIGH risk bands first.
    - **{confirmed:,}** cases have been confirmed as fraud, with **{data['frozen_accounts']:,}** accounts currently frozen.
    - **{fp:,}** cases were resolved as false positives — customer verification cleared these transactions.
    - **₹{recovered:,.0f}** has been recovered through chargebacks, insurance claims, and fund reversals.
    - Automated triage resolved **{automation_rate:.1f}%** of total cases, saving an estimated **{avg_time_saved:.0f} analyst-hours**.
    """

    st.markdown(briefing)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # ── KPI Summary Row ──────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _render_summary_card("Pending Review", "⏳", f"{pending:,}",
                             "Cases awaiting analyst action", "#D97706")
    with c2:
        _render_summary_card("Confirmed Fraud", "🚨", f"{confirmed:,}",
                             "Verified fraudulent transactions", "#DC2626")
    with c3:
        _render_summary_card("Automation Rate", "⚡", f"{automation_rate:.1f}%",
                             "Cases auto-triaged by system", "#059669")
    with c4:
        _render_summary_card("Analyst Time Saved", "⏱️", f"{avg_time_saved:.0f} hrs",
                             "Estimated via automated triage", "#2563EB")

    st.markdown("<hr style='border-color: #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # ── High Priority Cases ──────────────────────────────────────────────
    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 1.1rem; margin-right: 8px;">🔴</span>
            <span style="color: #F9FAFB; font-weight: 600; font-size: 0.95rem;">
                High-Priority Cases Requiring Immediate Attention
            </span>
        </div>
        """, unsafe_allow_html=True)

        if hp_df is not None and not hp_df.empty:
            for _, row in hp_df.iterrows():
                case_num = row.get("CASE_NUMBER", "N/A")
                risk = row.get("RISK_BAND", "N/A")
                score = row.get("PRIORITY_SCORE", 0)
                alert_type = row.get("ALERT_TYPE", "N/A")
                severity = row.get("SEVERITY", "N/A")

                badge_cls = "critical" if risk == "CRITICAL" else "high" if risk == "HIGH" else "medium"
                st.markdown(f"""
                <div style="background: #1F2937; border: 1px solid #374151; border-radius: 6px;
                            padding: 12px 16px; margin-bottom: 8px;
                            border-left: 3px solid {'#DC2626' if risk == 'CRITICAL' else '#EF4444'};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="color: #F9FAFB; font-weight: 600; font-size: 0.88rem;">{case_num}</span>
                            <span class="badge badge-{badge_cls}" style="margin-left: 8px;">{risk}</span>
                        </div>
                        <span style="color: #9CA3AF; font-size: 0.75rem;">Score: {score:.0f}</span>
                    </div>
                    <div style="color: #9CA3AF; font-size: 0.78rem; margin-top: 4px;">
                        {alert_type} · Severity: {severity}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No high-priority cases pending. All critical items have been triaged.")

    # ── Recommended Actions ──────────────────────────────────────────────
    with col2:
        st.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 1.1rem; margin-right: 8px;">💡</span>
            <span style="color: #F9FAFB; font-weight: 600; font-size: 0.95rem;">
                Recommended Actions
            </span>
        </div>
        """, unsafe_allow_html=True)

        recommendations = []

        if pending > 0:
            recommendations.append(
                f"Review **{min(pending, 10)}** highest-priority pending cases in the Investigation Queue."
            )
        if data["frozen_accounts"] > 5:
            recommendations.append(
                f"Coordinate with Branch Operations to process **{data['frozen_accounts']}** frozen account reviews."
            )
        if confirmed > 0:
            recommendations.append(
                "Initiate chargeback/insurance claims for confirmed fraud cases to accelerate recovery."
            )
        if fp > 100:
            recommendations.append(
                "Review alert rules — high false positive count suggests rule thresholds may need recalibration."
            )
        recommendations.append(
            "Run the Upload Dataset pipeline if new transaction batches have arrived from core banking."
        )
        recommendations.append(
            "Export today's investigation summary for the AML compliance report."
        )

        for rec in recommendations:
            st.markdown(f"""<div class="rec-card">{rec}</div>""", unsafe_allow_html=True)

    st.markdown("<hr style='border-color: #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # ── Operations Efficiency Summary ────────────────────────────────────
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 12px;">
        <span style="font-size: 1.1rem; margin-right: 8px;">📊</span>
        <span style="color: #F9FAFB; font-weight: 600; font-size: 0.95rem;">
            Operations Efficiency Summary
        </span>
    </div>
    """, unsafe_allow_html=True)

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Total Cases Processed", f"{data['total_cases']:,}")
    with e2:
        st.metric("Resolution Rate", f"{(total_resolved / max(data['total_cases'], 1) * 100):.1f}%")
    with e3:
        st.metric("False Positive Rate", f"{(fp / max(data['total_cases'], 1) * 100):.1f}%")
    with e4:
        st.metric("Active Workload", f"{active:,} cases")

"""
CasePilot Dashboard — Investigation Queue Page
=================================================
Searchable, filterable table of all investigation cases.
Supports manual case creation for analysts.
"""

import streamlit as st
import uuid
from datetime import datetime

from src.dashboard.services.queries import (
    get_investigation_queue, get_distinct_risk_bands, get_distinct_alert_types,
    insert_manual_case, get_total_cases, get_case_intelligence,
)



def _risk_badge(band: str) -> str:
    """Generate HTML for a risk band badge."""
    cls = f"badge-{band.lower()}" if band else "badge-low"
    return f'<span class="badge {cls}">{band}</span>'


def _render_add_case_form():
    """Render a form for manually adding a case to the investigation queue."""
    with st.expander("➕ Add Manual Investigation Case", expanded=False):
        st.markdown("""
        <p style="color:#9CA3AF; font-size:0.82rem; margin-bottom:12px;">
            Use this form to manually file an investigation case for a suspicious transaction
            or customer account that was flagged outside the automated pipeline.
        </p>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            customer_id = st.text_input("Customer ID *", placeholder="e.g. CUST_001", key="mc_customer")
            account_id = st.text_input("Account ID *", placeholder="e.g. ACC_101", key="mc_account")
            alert_type = st.selectbox("Alert Type *", [
                "HIGH_VALUE_TRANSACTION", "ODD_HOUR_ACTIVITY", "FOREIGN_ACTIVITY",
                "NEW_DEVICE_TRANSACTION", "RAPID_SUCCESSION", "STRUCTURING",
                "MANUAL_REVIEW", "OTHER"
            ], key="mc_alert_type")
        with col2:
            severity = st.selectbox("Severity *", ["LOW", "MEDIUM", "HIGH", "CRITICAL"], index=2, key="mc_severity")
            priority = st.selectbox("Priority *", ["LOW", "MEDIUM", "HIGH", "CRITICAL"], index=2, key="mc_priority")
            assigned_to = st.text_input("Assign To", placeholder="e.g. Analyst Name", key="mc_assigned")

        description = st.text_area(
            "Case Description / Reason for Filing",
            placeholder="Describe why this case is being manually raised...",
            key="mc_description",
            height=80
        )

        submitted = st.button("📋 File Investigation Case", type="primary", key="mc_submit")
        if submitted:
            if not customer_id.strip() or not account_id.strip():
                st.error("❌ Customer ID and Account ID are required.")
            else:
                try:
                    performed_by = st.session_state.get("user_name", "ANALYST")
                    case_id = insert_manual_case(
                        customer_id=customer_id.strip(),
                        account_id=account_id.strip(),
                        alert_type=alert_type,
                        severity=severity,
                        priority=priority,
                        assigned_to=assigned_to.strip() or "Unassigned",
                        description=description.strip(),
                        performed_by=performed_by
                    )
                    st.success(f"✅ Investigation case filed successfully! Case ID: `{case_id[:8]}...`")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to create case: {e}")


def render():
    """Render the Investigation Queue page."""
    st.markdown("""
    <h2 style="color:#F1F5F9; margin-bottom:4px;">🔍 Investigation Queue</h2>
    <p style="color:#64748B; font-size:0.85rem; margin-bottom:20px;">
        All open investigation cases sorted by priority. Use filters to narrow results.
    </p>
    """, unsafe_allow_html=True)

    # ── Add Manual Case Form ──────────────────────────────────────────────────
    _render_add_case_form()

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

    # ── Filters ──────────────────────────────────────────────────────────────
    with st.container():
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            risk_bands = get_distinct_risk_bands()
            selected_band = st.selectbox("Risk Band", risk_bands, key="iq_risk")
        with fc2:
            alert_types = get_distinct_alert_types()
            selected_type = st.selectbox("Alert Type", alert_types, key="iq_alert")
        with fc3:
            min_score = st.number_input("Min Score", 0.0, 100.0, 0.0, step=5.0, key="iq_min")
        with fc4:
            max_score = st.number_input("Max Score", 0.0, 100.0, 100.0, step=5.0, key="iq_max")

    st.markdown("---")

    # ── Query with filters ───────────────────────────────────────────────────
    df = get_investigation_queue(
        risk_band=selected_band if selected_band != "All" else None,
        alert_type=selected_type if selected_type != "All" else None,
        min_score=min_score if min_score > 0 else None,
        max_score=max_score if max_score < 100 else None,
    )

    if df.empty:
        st.markdown("""
        <div style="background-color: #1F2937; border: 1px solid #374151; border-radius: 8px;
                    padding: 40px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 12px;">🔍</div>
            <h3 style="color: #F9FAFB; margin-bottom: 8px;">No investigation cases found</h3>
            <p style="color: #9CA3AF; font-size: 0.9rem; max-width: 450px; margin: 0 auto 16px auto;">
                Upload a transaction dataset to auto-generate investigation cases,
                or use the <strong>Add Manual Investigation Case</strong> form above.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"""
    <div style="color:#94A3B8; font-size:0.85rem; margin-bottom:12px;">
        Showing <strong style="color:#F1F5F9;">{len(df)}</strong> cases
    </div>
    """, unsafe_allow_html=True)

    # ── Search ───────────────────────────────────────────────────────────────
    search = st.text_input("🔎 Search by Case ID, Customer ID, or Summary",
                           key="iq_search", placeholder="Type to search...")
    if search:
        mask = df.apply(lambda row: search.lower() in str(row.values).lower(), axis=1)
        df = df[mask]

    # ── Display table ────────────────────────────────────────────────────────
    display_cols = ["CASE_NUMBER", "ALERT_TYPE", "CUSTOMER_ID",
                    "PRIORITY_SCORE", "RISK_BAND", "CASE_STATUS",
                    "ASSIGNED_TO", "SEVERITY", "CREATED_AT"]
    available = [c for c in display_cols if c in df.columns]

    st.dataframe(
        df[available],
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "PRIORITY_SCORE": st.column_config.ProgressColumn(
                "Priority Score", min_value=0, max_value=100, format="%.1f"
            ),
            "RISK_BAND": st.column_config.TextColumn("Risk Band"),
            "CREATED_AT": st.column_config.DatetimeColumn("Created", format="YYYY-MM-DD HH:mm"),
        }
    )

    # ── Case Detail Expander ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-header">📋 Case Details</div>', unsafe_allow_html=True)

    if "CASE_ID" in df.columns and len(df) > 0:
        case_options = df["CASE_ID"].tolist()
        labels = []
        for _, row in df.iterrows():
            cn = row.get("CASE_NUMBER", row.get("CASE_ID", ""))[:20]
            rb = row.get("RISK_BAND", "—")
            ps = row.get("PRIORITY_SCORE", "—")
            labels.append(f"{cn} | {rb} | Score: {ps}")

        selected_idx = st.selectbox("Select a case to view details",
                                    range(len(labels)),
                                    format_func=lambda i: labels[i],
                                    key="iq_case_select")

        selected_case = df.iloc[selected_idx]
        selected_case_id = selected_case.get("CASE_ID")
        with st.expander(f"📂 Case: {labels[selected_idx]}", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**Case ID:** `{selected_case.get('CASE_ID', 'N/A')}`")
                st.markdown(f"**Customer:** `{selected_case.get('CUSTOMER_ID', 'N/A')}`")
            with c2:
                st.markdown(f"**Alert Type:** {selected_case.get('ALERT_TYPE', 'Manual') or 'Manual'}")
                st.markdown(f"**Severity:** {selected_case.get('SEVERITY', 'N/A') or 'N/A'}")
            with c3:
                st.markdown(f"**Status:** {selected_case.get('CASE_STATUS', 'N/A')}")
                st.markdown(f"**Assigned To:** {selected_case.get('ASSIGNED_TO', 'Unassigned') or 'Unassigned'}")

            # Dynamically fetch intelligence summary for single case
            if selected_case_id:
                intel_df = get_case_intelligence(selected_case_id)
                if not intel_df.empty:
                    summary = intel_df.iloc[0].get("INVESTIGATION_SUMMARY", "")
                    if summary:
                        st.markdown("**Investigation Summary:**")
                        st.text(str(summary)[:1000])

            desc = selected_case.get("ALERT_DESCRIPTION", "")
            if desc:
                st.markdown("**Alert Description:**")
                st.info(str(desc)[:500])


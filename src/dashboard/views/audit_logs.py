"""
CasePilot — Platform Audit Logs
==================================
Displays real pipeline audit events — dataset uploads, manual case creations,
and system actions. All records sourced from PIPELINE_AUDIT_LOG table.
"""

import streamlit as st
import pandas as pd
from src.dashboard.services.queries import get_audit_logs


def render():
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="color:#F9FAFB; margin-bottom:2px; font-size: 1.4rem; font-weight: 700;">
            📜 Platform Audit Logs
        </h2>
        <p style="color:#6B7280; font-size:0.8rem;">
            Real-time compliance audit trail of dataset uploads, manual case filings, and pipeline events.
        </p>
    </div>
    """, unsafe_allow_html=True)

    df = get_audit_logs(limit=100)

    if df is None or df.empty:
        st.markdown("""
        <div style="background-color: #1F2937; border: 1px solid #374151; border-radius: 8px;
                    padding: 40px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 12px;">📜</div>
            <h3 style="color: #F9FAFB; margin-bottom: 8px;">No Audit Events Recorded Yet</h3>
            <p style="color: #9CA3AF; font-size: 0.9rem; max-width: 450px; margin: 0 auto 16px auto;">
                Audit entries are created automatically when you upload a dataset or manually file
                an investigation case.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Summary stats ────────────────────────────────────────────────────────
    upload_events = df[df["ACTION_TYPE"] == "DATASET_UPLOAD"] if "ACTION_TYPE" in df.columns else pd.DataFrame()
    manual_events = df[df["ACTION_TYPE"] == "MANUAL_CASE_CREATION"] if "ACTION_TYPE" in df.columns else pd.DataFrame()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Audit Events", f"{len(df):,}")
    with m2:
        st.metric("Dataset Uploads", f"{len(upload_events):,}")
    with m3:
        st.metric("Manual Cases Filed", f"{len(manual_events):,}")
    with m4:
        total_rows = int(df["TOTAL_ROWS"].sum()) if "TOTAL_ROWS" in df.columns else 0
        st.metric("Total Rows Imported", f"{total_rows:,}")

    st.markdown("<hr style='border-color: #1F2937; margin: 12px 0;'>", unsafe_allow_html=True)

    # ── Search ───────────────────────────────────────────────────────────────
    search_term = st.text_input("🔍 Search Audit Trail", placeholder="Filter by event type, file name, or user...")
    if search_term:
        mask = df.apply(lambda row: search_term.lower() in str(row.values).lower(), axis=1)
        df = df[mask]

    # ── Display ──────────────────────────────────────────────────────────────
    display_cols = [c for c in ["ACTION_TYPE", "TIMESTAMP", "FILE_NAME", "TOTAL_ROWS",
                                "ALERTS_GENERATED", "CASES_CREATED", "STATUS",
                                "PERFORMED_BY", "DETAILS"] if c in df.columns]

    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        height=450,
        column_config={
            "ACTION_TYPE": st.column_config.TextColumn("Event Type"),
            "TIMESTAMP": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss"),
            "FILE_NAME": st.column_config.TextColumn("File"),
            "TOTAL_ROWS": st.column_config.NumberColumn("Rows Imported", format="%d"),
            "ALERTS_GENERATED": st.column_config.NumberColumn("Alerts", format="%d"),
            "CASES_CREATED": st.column_config.NumberColumn("Cases", format="%d"),
            "STATUS": st.column_config.TextColumn("Status"),
            "PERFORMED_BY": st.column_config.TextColumn("Performed By"),
            "DETAILS": st.column_config.TextColumn("Details"),
        }
    )

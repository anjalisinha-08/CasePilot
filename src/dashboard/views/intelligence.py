"""
CasePilot Dashboard — Case Intelligence Page
===============================================
Displays AI-generated intelligence: priority score, risk band,
investigation summary, recommendations, timeline, and key findings.
"""

import json
import streamlit as st

from src.dashboard.services.queries import get_all_case_ids, get_case_intelligence


def _parse_variant(val):
    """Parse a Snowflake VARIANT field."""
    if val is None:
        return []
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _render_score_card(score: float, band: str):
    """Render the priority score as a large visual card."""
    band_colors = {
        "CRITICAL": ("#DC2626", "#FCA5A5"),
        "HIGH": ("#EF4444", "#FCA5A5"),
        "MEDIUM": ("#F59E0B", "#FCD34D"),
        "LOW": ("#10B981", "#6EE7B7"),
    }
    bg_color, text_color = band_colors.get(band, ("#64748B", "#F1F5F9"))

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {bg_color}22, {bg_color}11);
                    border: 2px solid {bg_color}; border-radius: 16px;
                    padding: 32px; text-align: center; margin-bottom: 20px;">
            <div style="color: #94A3B8; font-size: 0.9rem; text-transform: uppercase;
                        letter-spacing: 1px; margin-bottom: 8px;">Priority Score</div>
            <div style="color: {text_color}; font-size: 3.5rem; font-weight: 800;
                        line-height: 1;">{score:.1f}</div>
            <div style="margin-top: 8px;">
                <span class="badge badge-{band.lower()}" style="font-size: 0.9rem;
                      padding: 6px 20px;">{band}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_summary(summary: str):
    """Render investigation summary as formatted text."""
    st.markdown('<div class="section-header">📝 Investigation Summary</div>', unsafe_allow_html=True)
    if not summary:
        st.info("No investigation summary available.")
        return
    st.markdown(f"""
    <div class="info-card">
        <pre style="color: #CBD5E1; font-family: 'Inter', sans-serif; font-size: 0.85rem;
                    white-space: pre-wrap; word-wrap: break-word; margin: 0;
                    background: transparent; border: none; padding: 0;">{summary}</pre>
    </div>
    """, unsafe_allow_html=True)


def _render_recommendations(recommendations):
    """Render recommendations as styled bullet cards."""
    st.markdown('<div class="section-header">💡 Recommendations</div>', unsafe_allow_html=True)
    if not recommendations:
        st.info("No recommendations generated.")
        return
    for rec in recommendations:
        st.markdown(f'<div class="rec-card">{rec}</div>', unsafe_allow_html=True)


def _render_timeline(timeline):
    """Render event timeline vertically."""
    st.markdown('<div class="section-header">⏱ Investigation Timeline</div>', unsafe_allow_html=True)
    if not timeline:
        st.info("No timeline data available.")
        return
    for event in timeline:
        event_type = event.get("type", "")
        css_class = "current" if event_type == "CURRENT_ALERT" else ""
        ts = event.get("timestamp", "")
        ev = event.get("event", "")
        desc = event.get("description", "")

        st.markdown(f"""
        <div class="timeline-item {css_class}">
            <div class="tl-time">{ts}</div>
            <div class="tl-event">{ev}</div>
            <div class="tl-desc">{desc[:200]}</div>
        </div>
        """, unsafe_allow_html=True)


def _render_key_findings(findings):
    """Render key findings as highlighted items."""
    st.markdown('<div class="section-header">🔑 Key Findings</div>', unsafe_allow_html=True)
    if not findings:
        st.info("No key findings identified.")
        return
    for i, finding in enumerate(findings, 1):
        st.markdown(f"""
        <div style="background: rgba(37,99,235,0.08); border-left: 3px solid #2563EB;
                    padding: 10px 14px; margin-bottom: 8px; border-radius: 0 8px 8px 0;
                    color: #E2E8F0; font-size: 0.88rem;">
            <strong style="color: #3B82F6;">Finding {i}:</strong> {finding}
        </div>
        """, unsafe_allow_html=True)


def render():
    """Render the Case Intelligence page."""
    st.markdown("""
    <h2 style="color:#F1F5F9; margin-bottom:4px;">🧠 Case Intelligence</h2>
    <p style="color:#64748B; font-size:0.85rem; margin-bottom:20px;">
        AI-generated investigation intelligence — priority scoring,
        narrative summaries, actionable recommendations, and event timelines.
    </p>
    """, unsafe_allow_html=True)

    # ── Case Selector ────────────────────────────────────────────────────
    cases_df = get_all_case_ids()
    if cases_df.empty:
        st.warning("No cases found.")
        return

    labels = []
    for _, row in cases_df.iterrows():
        cn = row.get("CASE_NUMBER", row.get("CASE_ID", "N/A"))
        rb = row.get("RISK_BAND", "")
        ps = row.get("PRIORITY_SCORE", "")
        labels.append(f"{cn} | {rb} | Score: {ps}")

    selected_idx = st.selectbox("Select a Case", range(len(labels)),
                                format_func=lambda i: labels[i], key="intel_case")
    case_id = cases_df.iloc[selected_idx]["CASE_ID"]

    st.markdown("---")

    # ── Fetch intelligence ───────────────────────────────────────────────
    intel_df = get_case_intelligence(case_id)
    if intel_df.empty:
        st.warning(f"No intelligence data for case `{case_id}`.")
        return

    row = intel_df.iloc[0]
    score = float(row.get("PRIORITY_SCORE", 0))
    band = str(row.get("RISK_BAND", "MEDIUM"))
    summary = str(row.get("INVESTIGATION_SUMMARY", ""))
    recommendations = _parse_variant(row.get("RECOMMENDATIONS"))
    timeline = _parse_variant(row.get("TIMELINE"))
    key_findings = _parse_variant(row.get("KEY_FINDINGS"))

    # ── Render ───────────────────────────────────────────────────────────
    _render_score_card(score, band)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.metric("Model Version", row.get("MODEL_VERSION", "1.0"))
    with c2:
        st.metric("Generated At", str(row.get("GENERATED_AT", "N/A"))[:19])

    st.markdown("---")
    _render_summary(summary)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        _render_recommendations(recommendations)
    with col2:
        _render_timeline(timeline)

    st.markdown("---")
    _render_key_findings(key_findings)

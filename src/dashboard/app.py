"""
CasePilot — Enterprise AML Investigation Platform
====================================================
AI-Powered Anti-Money Laundering Investigation Platform.
Role-based access with secure authentication.

Run: streamlit run src/dashboard/app.py
"""

import os
import sys
import hashlib
import streamlit as st

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="CasePilot — AML Investigation Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Enterprise Dark Theme CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --primary: #1E40AF;
        --primary-light: #3B82F6;
        --bg-dark: #0B1120;
        --bg-surface: #111827;
        --bg-card: #1F2937;
        --border: #374151;
        --border-subtle: #1F2937;
        --text-primary: #F9FAFB;
        --text-secondary: #9CA3AF;
        --text-muted: #6B7280;
        --success: #059669;
        --success-light: #10B981;
        --warning: #D97706;
        --danger: #DC2626;
        --danger-light: #EF4444;
        --info: #2563EB;
    }

    /* Global Typography & Background */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: var(--bg-dark);
        color: var(--text-primary);
    }

    [data-testid="stSidebar"] {
        background-color: var(--bg-surface);
        border-right: 1px solid var(--border);
    }

    /* Cards & Containers */
    div[data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: var(--text-primary);
        font-size: 1.5rem !important;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--text-secondary);
        font-size: 0.78rem !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Metric card styling */
    [data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px 16px;
    }

    /* Custom Section Headers */
    .section-header {
        color: var(--text-primary);
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 12px;
        letter-spacing: -0.2px;
    }

    .sub-header {
        color: var(--text-muted);
        font-size: 0.8rem;
        margin-bottom: 16px;
    }

    /* Badge styles */
    .badge-critical {
        background-color: rgba(220, 38, 38, 0.2);
        color: #F87171;
        border: 1px solid rgba(220, 38, 38, 0.4);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-high {
        background-color: rgba(217, 119, 6, 0.2);
        color: #FBBF24;
        border: 1px solid rgba(217, 119, 6, 0.4);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-medium {
        background-color: rgba(37, 99, 235, 0.2);
        color: #60A5FA;
        border: 1px solid rgba(37, 99, 235, 0.4);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-low {
        background-color: rgba(5, 150, 105, 0.2);
        color: #34D399;
        border: 1px solid rgba(5, 150, 105, 0.4);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
    }

    /* Buttons */
    .stButton > button {
        background-color: var(--bg-card);
        color: var(--text-primary);
        border: 1px solid var(--border);
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.85rem;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        background-color: var(--primary);
        border-color: var(--primary-light);
        color: white;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        border-bottom: 1px solid var(--border);
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--text-secondary);
        font-weight: 500;
        font-size: 0.85rem;
        border-radius: 6px 6px 0 0;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        color: var(--text-primary) !important;
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-bottom: none !important;
    }

    /* Info cards */
    .info-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .info-card h4 {
        color: var(--primary-light);
        margin-bottom: 6px;
        font-size: 0.9rem;
    }
    .info-card p, .info-card li {
        color: var(--text-secondary);
        font-size: 0.85rem;
    }

    /* User badge in sidebar */
    .user-badge {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    .user-badge .user-name {
        color: var(--text-primary);
        font-weight: 600;
        font-size: 0.9rem;
    }
    .user-badge .user-role {
        color: var(--primary-light);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .user-badge .user-dept {
        color: var(--text-muted);
        font-size: 0.72rem;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ── Authentication ───────────────────────────────────────────────────────────

def _render_login():
    """Render the login page."""
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style="text-align: center; margin-top: 60px; margin-bottom: 24px;">
            <div style="font-size: 3rem; margin-bottom: 8px;">🛡️</div>
            <h1 style="color: #F9FAFB; font-size: 1.6rem; font-weight: 700; margin: 0;">CasePilot</h1>
            <p style="color: #6B7280; font-size: 0.85rem; margin-top: 4px;">Enterprise AML Investigation Platform</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            employee_id = st.text_input("User ID / Employee ID", placeholder="e.g. FA001, BE001, CUST001")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                if not employee_id or not password:
                    st.error("Please enter User ID and Password.")
                    return

                password_hash = hashlib.sha256(password.encode()).hexdigest()
                from src.dashboard.services.queries import authenticate_user
                user = authenticate_user(employee_id.strip().upper(), password_hash)

                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.session_state.role = user["ROLE"]
                    st.session_state.user_name = user["FULL_NAME"]
                    st.session_state.employee_id = user["EMPLOYEE_ID"]
                    if user.get("CUSTOMER_ID"):
                        st.session_state.customer_id = user["CUSTOMER_ID"]
                        st.session_state.customer_name = user["FULL_NAME"]
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please verify your Login ID and password.")

        st.markdown("<hr style='border-color: #1F2937; margin: 20px 0;'>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align: center; color: #6B7280; font-size: 0.75rem;">
            <p style="margin-bottom: 4px;"><strong>System Demo Credentials</strong></p>
            <p style="margin: 2px 0;">Fraud Analyst: <code style="color: #9CA3AF;">FA001</code> / <code style="color: #9CA3AF;">analyst123</code></p>
            <p style="margin: 2px 0;">Bank Employee: <code style="color: #9CA3AF;">BE001</code> / <code style="color: #9CA3AF;">employee123</code></p>
            <p style="margin: 2px 0;">Customer: <code style="color: #9CA3AF;">CUST001</code> / <code style="color: #9CA3AF;">customer123</code></p>
        </div>
        """, unsafe_allow_html=True)


if not st.session_state.get("authenticated", False):
    _render_login()
    st.stop()

# Authenticated User
user = st.session_state.user
current_role = st.session_state.role

# ── Sidebar Navigation ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 12px 0 4px 0;">
        <span style="font-size: 2rem;">🛡️</span>
        <h1 style="margin: 2px 0 0 0; font-size: 1.2rem; font-weight: 700; color: #F9FAFB;">
            CasePilot
        </h1>
        <p style="color: #6B7280; font-size: 0.65rem; margin-top: 2px; letter-spacing: 1px; text-transform: uppercase;">
            AML Investigation Platform
        </p>
    </div>
    """, unsafe_allow_html=True)

    role_label = current_role.replace("_", " ").title()
    dept = user.get("DEPARTMENT", "")
    st.markdown(f"""
    <div class="user-badge">
        <div class="user-name">{user['FULL_NAME']}</div>
        <div class="user-role">{role_label}</div>
        <div class="user-dept">{dept or ''} · {user['EMPLOYEE_ID']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color: #1F2937; margin: 4px 0 12px 0;'>", unsafe_allow_html=True)

    if current_role == "FRAUD_ANALYST":
        pages = [
            "📊 Operations Dashboard",
            "🔍 Investigation Queue",
            "👤 Customer 360",
            "🤖 AI Copilot",
            "💸 Fraud Resolution Center",
            "📤 Upload Dataset",
            "📜 Audit Logs",
        ]
    elif current_role == "BANK_EMPLOYEE":
        pages = [
            "🏦 Customer Accounts",
            "📜 Transaction History",
            "📋 KYC Details",
            "🚨 Open Cases",
            "📩 Customer Verification Requests",
        ]
    else:  # CUSTOMER
        pages = [
            "💳 My Accounts",
            "📑 My Transactions",
            "🔔 Security Alerts",
            "✅ Verify Transaction",
            "📢 Report Fraud",
            "🔒 Freeze Card",
        ]

    page = st.radio("Navigation", options=pages, label_visibility="collapsed")

    st.markdown("<hr style='border-color: #1F2937; margin: 12px 0;'>", unsafe_allow_html=True)

    if current_role == "FRAUD_ANALYST":
        auto_refresh = st.toggle("🔄 Live Refresh", value=False, key="auto_refresh")
        if auto_refresh:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=30000, limit=None, key="live_refresh")

    st.markdown("<hr style='border-color: #1F2937; margin: 8px 0;'>", unsafe_allow_html=True)

    if st.button("🚪 Sign Out", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ── Page Routing ─────────────────────────────────────────────────────────────
if current_role == "FRAUD_ANALYST":
    if page == "📊 Operations Dashboard":
        from src.dashboard.views.executive import render
        render()
    elif page == "🔍 Investigation Queue":
        from src.dashboard.views.investigation import render
        render()
    elif page == "👤 Customer 360":
        from src.dashboard.views.customer360 import render
        render()
    elif page == "🤖 AI Copilot":
        from src.dashboard.views.ai_copilot import render
        render()
    elif page == "💸 Fraud Resolution Center":
        from src.dashboard.views.fraud_resolution_center import render
        render()
    elif page == "📤 Upload Dataset":
        from src.dashboard.views.upload_dataset import render
        render()
    elif page == "📜 Audit Logs":
        from src.dashboard.views.audit_logs import render
        render()

elif current_role == "BANK_EMPLOYEE":
    from src.dashboard.views.bank_operations import render
    render(subpage=page)

elif current_role == "CUSTOMER":
    from src.dashboard.views.customer_portal import render
    render(subpage=page)

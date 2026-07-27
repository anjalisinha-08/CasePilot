"""
CasePilot 2.0 — Central Configuration
========================================
All database names, schema names, table names, simulation parameters,
and application settings in one place.

v2.0 Changes:
  - 6 personas (added RETIRED, HIGH_NET_WORTH, FREELANCER)
  - 7 channels (UPI, IMPS, NEFT, RTGS, POS, ATM, ONLINE_BANKING)
  - Scale: 5K customers, 10K accounts, 2K merchants, 15K devices, 500K txns
  - Fraud labeling config (95/5 split)
"""

import os
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# SNOWFLAKE INFRASTRUCTURE
# =============================================================================

SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "CASEPILOT_WH"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "CASEPILOT_DB"),
    "role": os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
}

DATABASE = "CASEPILOT_DB"
WAREHOUSE = "CASEPILOT_WH"

SCHEMAS = {
    "RAW": "RAW",
    "CORE": "CORE",
    "ALERTS": "ALERTS",
    "INVESTIGATION": "INVESTIGATION",
    "ANALYTICS": "ANALYTICS",
}

TABLES = {
    "CUSTOMER": f"{DATABASE}.{SCHEMAS['RAW']}.CUSTOMER",
    "ACCOUNT": f"{DATABASE}.{SCHEMAS['RAW']}.ACCOUNT",
    "MERCHANT": f"{DATABASE}.{SCHEMAS['RAW']}.MERCHANT",
    "DEVICE": f"{DATABASE}.{SCHEMAS['RAW']}.DEVICE",
    "TRANSACTION": f"{DATABASE}.{SCHEMAS['RAW']}.TRANSACTION",
    "ALERT": f"{DATABASE}.{SCHEMAS['ALERTS']}.ALERT",
    "INVESTIGATION_CASE": f"{DATABASE}.{SCHEMAS['INVESTIGATION']}.INVESTIGATION_CASE",
    "CASE_ENRICHMENT": f"{DATABASE}.{SCHEMAS['INVESTIGATION']}.CASE_ENRICHMENT",
    "CASE_INTELLIGENCE": f"{DATABASE}.{SCHEMAS['ANALYTICS']}.CASE_INTELLIGENCE",
    "CUSTOMER_BEHAVIOR_PROFILE": f"{DATABASE}.{SCHEMAS['ANALYTICS']}.CUSTOMER_BEHAVIOR_PROFILE",
    "MODEL_METRICS": f"{DATABASE}.{SCHEMAS['ANALYTICS']}.MODEL_METRICS",
    "NOTIFICATION_LOG": f"{DATABASE}.{SCHEMAS['INVESTIGATION']}.NOTIFICATION_LOG",
}


# =============================================================================
# SIMULATION PARAMETERS (v2.0 — 50x scale)
# =============================================================================

SIMULATION = {
    "num_customers": 5000,
    "num_accounts": 10000,
    "num_merchants": 2000,
    "num_devices": 15000,
    "num_transactions": 500000,
    "suspicious_ratio": 0.03,      # 3% fraudulent transactions (fits 2-5% target)
    "transaction_days": 180,       # 6 months of history
    "random_seed": 42,
}

# =============================================================================
# CUSTOMER PERSONAS (v2.0 — 6 personas)
# =============================================================================

PERSONAS = {
    "SALARIED": {
        "weight": 0.30,
        "income_range": (300000, 2000000),
        "avg_txn_amount": (500, 15000),
        "txn_frequency_daily": (1, 5),
        "risk_rating": "LOW",
        "occupations": [
            "Software Engineer", "Accountant", "Teacher", "Manager",
            "Analyst", "HR Executive", "Marketing Manager", "Civil Engineer",
            "Doctor", "Lawyer",
        ],
    },
    "BUSINESS_OWNER": {
        "weight": 0.20,
        "income_range": (1000000, 50000000),    # Up to 5 Cr
        "avg_txn_amount": (5000, 500000),       # Regular large txns
        "txn_frequency_daily": (5, 20),
        "risk_rating": "MEDIUM",
        "occupations": [
            "Business Owner", "Entrepreneur", "Import-Export Dealer",
            "Manufacturer", "Wholesaler", "Retailer",
        ],
    },
    "STUDENT": {
        "weight": 0.15,
        "income_range": (50000, 300000),
        "avg_txn_amount": (50, 3000),
        "txn_frequency_daily": (1, 3),
        "risk_rating": "LOW",
        "occupations": [
            "Undergraduate Student", "Graduate Student", "PhD Scholar",
            "Research Assistant", "Intern",
        ],
    },
    "RETIRED": {
        "weight": 0.10,
        "income_range": (200000, 1500000),
        "avg_txn_amount": (200, 8000),
        "txn_frequency_daily": (1, 3),
        "risk_rating": "LOW",
        "occupations": [
            "Retired Government Officer", "Retired Teacher",
            "Retired Bank Employee", "Pensioner", "Senior Citizen",
        ],
    },
    "FREELANCER": {
        "weight": 0.15,
        "income_range": (200000, 5000000),
        "avg_txn_amount": (500, 25000),
        "txn_frequency_daily": (2, 8),
        "risk_rating": "MEDIUM",
        "occupations": [
            "Freelance Developer", "Content Creator", "Consultant",
            "Travel Blogger", "Graphic Designer", "Photographer",
        ],
    },
    "HIGH_NET_WORTH": {
        "weight": 0.10,
        "income_range": (10000000, 100000000),  # 1 Cr to 10 Cr
        "avg_txn_amount": (50000, 5000000),     # Regular large txns
        "txn_frequency_daily": (3, 15),
        "risk_rating": "MEDIUM",
        "occupations": [
            "CEO", "Managing Director", "Venture Capitalist",
            "Real Estate Developer", "Investment Banker", "Surgeon",
        ],
    },
}

# Backward compatibility alias
SALARY_EMPLOYEE = PERSONAS.get("SALARIED")

# =============================================================================
# TRANSACTION CHANNELS (v2.0 — 7 channels)
# =============================================================================

CHANNELS = {
    "UPI": 0.30,
    "IMPS": 0.10,
    "NEFT": 0.08,
    "RTGS": 0.02,
    "POS": 0.20,
    "ATM": 0.10,
    "ONLINE_BANKING": 0.20,
}

TXN_TYPES = {
    "DEBIT": 0.65,
    "CREDIT": 0.30,
    "TRANSFER": 0.05,
}


# =============================================================================
# FRAUD CONFIGURATION (v2.0 — NEW)
# =============================================================================

FRAUD_TYPES = [
    "ACCOUNT_TAKEOVER",
    "NEW_DEVICE_FRAUD",
    "VELOCITY_FRAUD",
    "MONEY_MULE",
    "CARD_FRAUD",
    "BENEFICIARY_FRAUD",
    "GEO_ANOMALY",
    "LARGE_AMOUNT_ANOMALY",
]

FRAUD_CONFIG = {
    "fraud_ratio": 0.05,            # 5% of all transactions are fraud
    "fraud_probability": 0.15,      # Live pipeline: 15% chance per batch
    "confidence_range": (0.60, 0.99),
}

# =============================================================================
# ALERT RULES CONFIGURATION
# =============================================================================

ALERT_RULES = {
    "HIGH_VALUE_TXN": {
        "description": "Transaction amount exceeds threshold relative to customer baseline",
        "threshold": 25000,
        "persona_thresholds": {
            "STUDENT": 15000,
            "RETIRED": 25000,
            "SALARIED": 50000,
            "FREELANCER": 75000,
            "BUSINESS_OWNER": 1000000,
            "HIGH_NET_WORTH": 10000000
        },
        "severity_map": {
            25000: "MEDIUM",
            50000: "HIGH",
            100000: "CRITICAL",
        },
    },
    "ODD_HOUR_ACTIVITY": {
        "description": "Transaction between 00:00 and 04:00 hours",
        "start_hour": 0,
        "end_hour": 4,
        "default_severity": "MEDIUM",
    },
    "NEW_DEVICE_USED": {
        "description": "Transaction from an untrusted/unknown device",
        "default_severity": "HIGH",
        "min_amount": 10000,
        "personal_only": True,
    },
    "RAPID_TXN_BURST": {
        "description": "More than 5 transactions within a 10-minute window",
        "max_txns": 5,
        "window_minutes": 10,
        "default_severity": "HIGH",
    },
    "FOREIGN_ACTIVITY": {
        "description": "Transaction originating outside regular geography (India)",
        "home_country": "India",
        "default_severity": "HIGH",
    },
}

# Alerts that require manual analyst review to generate a case
ALERTS_REQUIRING_REVIEW = ["HIGH", "CRITICAL"]


# =============================================================================
# PRIORITY SCORING WEIGHTS
# =============================================================================

SCORING_WEIGHTS = {
    "alert_severity": 0.20,
    "amount_deviation": 0.20,
    "customer_risk": 0.10,
    "previous_alerts": 0.10,
    "device_trust": 0.10,
    "time_anomaly": 0.10,
    "geo_anomaly": 0.05,
    "velocity_risk": 0.05,
    "channel_anomaly": 0.05,
    "merchant_risk": 0.05,
}

RISK_BANDS = {
    "LOW": (0, 25),
    "MEDIUM": (26, 50),
    "HIGH": (51, 75),
    "CRITICAL": (76, 100),
}

SEVERITY_SCORES = {
    "LOW": 20,
    "MEDIUM": 50,
    "HIGH": 75,
    "CRITICAL": 100,
}


# =============================================================================
# GEOGRAPHY DATA
# =============================================================================

INDIAN_CITIES = [
    {"city": "Mumbai", "state": "Maharashtra", "pin_prefix": "400"},
    {"city": "Delhi", "state": "Delhi", "pin_prefix": "110"},
    {"city": "Bangalore", "state": "Karnataka", "pin_prefix": "560"},
    {"city": "Hyderabad", "state": "Telangana", "pin_prefix": "500"},
    {"city": "Chennai", "state": "Tamil Nadu", "pin_prefix": "600"},
    {"city": "Kolkata", "state": "West Bengal", "pin_prefix": "700"},
    {"city": "Pune", "state": "Maharashtra", "pin_prefix": "411"},
    {"city": "Ahmedabad", "state": "Gujarat", "pin_prefix": "380"},
    {"city": "Jaipur", "state": "Rajasthan", "pin_prefix": "302"},
    {"city": "Lucknow", "state": "Uttar Pradesh", "pin_prefix": "226"},
    {"city": "Chandigarh", "state": "Chandigarh", "pin_prefix": "160"},
    {"city": "Noida", "state": "Uttar Pradesh", "pin_prefix": "201"},
    {"city": "Gurugram", "state": "Haryana", "pin_prefix": "122"},
    {"city": "Kochi", "state": "Kerala", "pin_prefix": "682"},
    {"city": "Indore", "state": "Madhya Pradesh", "pin_prefix": "452"},
]

FOREIGN_CITIES = [
    {"city": "Dubai", "country": "UAE"},
    {"city": "Singapore", "country": "Singapore"},
    {"city": "London", "country": "UK"},
    {"city": "New York", "country": "USA"},
    {"city": "Bangkok", "country": "Thailand"},
    {"city": "Hong Kong", "country": "Hong Kong"},
    {"city": "Kuala Lumpur", "country": "Malaysia"},
    {"city": "Tokyo", "country": "Japan"},
]


# =============================================================================
# MERCHANT CATEGORIES
# =============================================================================

MERCHANT_CATEGORIES = [
    {"category": "GROCERY", "mcc": "5411", "risk": "LOW"},
    {"category": "ELECTRONICS", "mcc": "5732", "risk": "LOW"},
    {"category": "TRAVEL", "mcc": "4722", "risk": "MEDIUM"},
    {"category": "FUEL", "mcc": "5541", "risk": "LOW"},
    {"category": "RESTAURANT", "mcc": "5812", "risk": "LOW"},
    {"category": "ENTERTAINMENT", "mcc": "7832", "risk": "LOW"},
    {"category": "HEALTHCARE", "mcc": "8011", "risk": "LOW"},
    {"category": "EDUCATION", "mcc": "8211", "risk": "LOW"},
    {"category": "FASHION", "mcc": "5651", "risk": "LOW"},
    {"category": "JEWELRY", "mcc": "5944", "risk": "MEDIUM"},
    {"category": "ONLINE_GAMING", "mcc": "7994", "risk": "HIGH"},
    {"category": "CRYPTOCURRENCY", "mcc": "6051", "risk": "HIGH"},
    {"category": "FOREIGN_EXCHANGE", "mcc": "6012", "risk": "HIGH"},
    {"category": "LUXURY_GOODS", "mcc": "5094", "risk": "MEDIUM"},
    {"category": "TELECOM", "mcc": "4812", "risk": "LOW"},
]


# =============================================================================
# INVESTIGATION TEAMS
# =============================================================================

INVESTIGATION_TEAMS = {
    "TEAM_ALPHA": {
        "analysts": ["Priya Sharma", "Rahul Verma", "Ananya Patel"],
        "specialization": "High-value transactions",
    },
    "TEAM_BETA": {
        "analysts": ["Vikram Singh", "Neha Gupta", "Arjun Reddy"],
        "specialization": "Device and channel fraud",
    },
    "TEAM_GAMMA": {
        "analysts": ["Kavita Nair", "Suresh Kumar", "Deepa Iyer"],
        "specialization": "International and geographic anomalies",
    },
}


# =============================================================================
# DASHBOARD CONFIGURATION
# =============================================================================

DASHBOARD = {
    "title": "CasePilot 2.0 — Fraud Investigation Platform",
    "page_icon": "🛡️",
    "layout": "wide",
    "theme": "dark",
    "refresh_interval_seconds": 30,
}

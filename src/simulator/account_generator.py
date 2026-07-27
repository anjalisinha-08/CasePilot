"""
CasePilot 2.0 — Account Generator
====================================
Generates bank accounts linked to customers.
Account types, weights, and balance ranges are tailored to the 6 personas.

Personas: SALARIED, BUSINESS_OWNER, STUDENT, RETIRED, FREELANCER, HIGH_NET_WORTH
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.config.settings import SIMULATION, PERSONAS
from src.utils.helpers import (
    generate_uuid, generate_account_number, generate_ifsc_code,
)

logger = logging.getLogger(__name__)

# Balance ranges by account type and persona
BALANCE_CONFIG = {
    "SALARIED": {
        "SAVINGS": (5000, 200000),
        "SALARY": (10000, 500000),
        "FD": (50000, 1000000),
    },
    "STUDENT": {
        "SAVINGS": (500, 30000),
    },
    "BUSINESS_OWNER": {
        "CURRENT": (50000, 10000000),   # Up to 1 Cr
        "SAVINGS": (20000, 1000000),
        "FD": (100000, 5000000),
    },
    "RETIRED": {
        "SAVINGS": (10000, 500000),
        "FD": (50000, 2500000),
    },
    "FREELANCER": {
        "SAVINGS": (5000, 300000),
        "CURRENT": (10000, 1000000),
    },
    "HIGH_NET_WORTH": {
        "SAVINGS": (500000, 20000000),  # Up to 2 Cr
        "CURRENT": (1000000, 50000000), # Up to 5 Cr
        "FD": (2000000, 100000000),    # Up to 10 Cr
    },
}

# Account type weights by persona
ACCOUNT_TYPE_WEIGHTS = {
    "SALARIED": {"SAVINGS": 0.40, "SALARY": 0.40, "FD": 0.20},
    "STUDENT": {"SAVINGS": 1.0},
    "BUSINESS_OWNER": {"CURRENT": 0.50, "SAVINGS": 0.30, "FD": 0.20},
    "RETIRED": {"SAVINGS": 0.60, "FD": 0.40},
    "FREELANCER": {"SAVINGS": 0.70, "CURRENT": 0.30},
    "HIGH_NET_WORTH": {"CURRENT": 0.40, "SAVINGS": 0.30, "FD": 0.30},
}


def _choose_account_type(persona: str, existing_types: List[str]) -> str:
    """Choose an account type that the customer doesn't already have."""
    weights = ACCOUNT_TYPE_WEIGHTS.get(persona, {"SAVINGS": 1.0})
    available = {k: v for k, v in weights.items() if k not in existing_types}
    if not available:
        available = weights
    types = list(available.keys())
    type_weights = list(available.values())
    return random.choices(types, weights=type_weights, k=1)[0]


def generate_accounts(customers: List[Dict[str, Any]], count: int = None) -> List[Dict[str, Any]]:
    """
    Generate bank accounts linked to customers.
    Ensures every customer gets at least one account, then distributes the rest.
    """
    count = count or SIMULATION["num_accounts"]
    random.seed(SIMULATION["random_seed"] + 1)
    
    accounts = []
    customer_account_types = {c["CUSTOMER_ID"]: [] for c in customers}

    # Phase 1: Ensure every customer gets at least one account
    for customer in customers:
        cid = customer["CUSTOMER_ID"]
        persona = customer["PERSONA"]
        acct_type = _choose_account_type(persona, [])
        customer_account_types[cid].append(acct_type)

        balance_range = BALANCE_CONFIG.get(persona, {}).get(acct_type, (1000, 50000))
        balance = round(random.uniform(*balance_range), 2)

        cust_created = datetime.strptime(customer["CREATED_AT"], "%Y-%m-%d %H:%M:%S")
        opened_at = cust_created + timedelta(days=random.randint(0, 30))

        accounts.append({
            "ACCOUNT_ID": generate_uuid(),
            "CUSTOMER_ID": cid,
            "ACCOUNT_TYPE": acct_type,
            "ACCOUNT_NUMBER": generate_account_number(),
            "IFSC_CODE": generate_ifsc_code(),
            "BRANCH_CODE": f"BR{random.randint(100, 999)}",
            "BALANCE": balance,
            "CURRENCY": "INR",
            "ACCOUNT_STATUS": "ACTIVE",
            "OPENED_AT": opened_at.strftime("%Y-%m-%d %H:%M:%S"),
            "UPDATED_AT": opened_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Phase 2: Distribute remaining accounts
    remaining = count - len(accounts)
    if remaining > 0:
        for _ in range(remaining):
            customer = random.choice(customers)
            cid = customer["CUSTOMER_ID"]
            persona = customer["PERSONA"]
            existing_types = customer_account_types[cid]
            acct_type = _choose_account_type(persona, existing_types)
            customer_account_types[cid].append(acct_type)

            balance_range = BALANCE_CONFIG.get(persona, {}).get(acct_type, (1000, 50000))
            balance = round(random.uniform(*balance_range), 2)

            cust_created = datetime.strptime(customer["CREATED_AT"], "%Y-%m-%d %H:%M:%S")
            opened_at = cust_created + timedelta(days=random.randint(0, 90))

            accounts.append({
                "ACCOUNT_ID": generate_uuid(),
                "CUSTOMER_ID": cid,
                "ACCOUNT_TYPE": acct_type,
                "ACCOUNT_NUMBER": generate_account_number(),
                "IFSC_CODE": generate_ifsc_code(),
                "BRANCH_CODE": f"BR{random.randint(100, 999)}",
                "BALANCE": balance,
                "CURRENCY": "INR",
                "ACCOUNT_STATUS": random.choices(
                    ["ACTIVE", "DORMANT", "FROZEN"],
                    weights=[0.92, 0.06, 0.02], k=1
                )[0],
                "OPENED_AT": opened_at.strftime("%Y-%m-%d %H:%M:%S"),
                "UPDATED_AT": opened_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

    # Log summary
    type_counts = {}
    for a in accounts:
        t = a["ACCOUNT_TYPE"]
        type_counts[t] = type_counts.get(t, 0) + 1
    logger.info(f"Generated {len(accounts)} accounts. Types: {type_counts}")

    return accounts


def insert_accounts_to_snowflake(accounts: List[Dict[str, Any]], connection) -> int:
    """Insert generated accounts into Snowflake RAW.ACCOUNT table."""
    connection.use_schema("RAW")

    insert_query = """
        INSERT INTO ACCOUNT (
            ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_TYPE, ACCOUNT_NUMBER,
            IFSC_CODE, BRANCH_CODE, BALANCE, CURRENCY,
            ACCOUNT_STATUS, OPENED_AT, UPDATED_AT
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    data = [
        (
            a["ACCOUNT_ID"], a["CUSTOMER_ID"], a["ACCOUNT_TYPE"],
            a["ACCOUNT_NUMBER"], a["IFSC_CODE"], a["BRANCH_CODE"],
            a["BALANCE"], a["CURRENCY"], a["ACCOUNT_STATUS"],
            a["OPENED_AT"], a["UPDATED_AT"],
        )
        for a in accounts
    ]

    rows = connection.execute_many(insert_query, data)
    logger.info(f"Inserted {rows} accounts into Snowflake.")
    return rows

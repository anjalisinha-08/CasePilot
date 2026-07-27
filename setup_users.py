"""
CasePilot — Platform User Setup & Seeding
============================================
Creates the PLATFORM_USER table and seeds initial accounts for authentication.
"""

import uuid
import hashlib
import logging
from src.config.snowflake_connection import SnowflakeConnection

logging.basicConfig(level=logging.INFO)


def hash_password(password: str) -> str:
    """Simple SHA-256 hash for demo authentication."""
    return hashlib.sha256(password.encode()).hexdigest()


def main():
    conn = SnowflakeConnection()
    conn.connect()
    try:
        # Create PLATFORM_USER table
        conn.execute_query("""
            CREATE TABLE IF NOT EXISTS CASEPILOT_DB.RAW.PLATFORM_USER (
                USER_ID         VARCHAR(36)     NOT NULL PRIMARY KEY,
                EMPLOYEE_ID     VARCHAR(20)     NOT NULL UNIQUE,
                FULL_NAME       VARCHAR(200)    NOT NULL,
                EMAIL           VARCHAR(255)    NOT NULL,
                PASSWORD_HASH   VARCHAR(64)     NOT NULL,
                ROLE            VARCHAR(30)     NOT NULL,
                DEPARTMENT      VARCHAR(100),
                CUSTOMER_ID     VARCHAR(36),
                IS_ACTIVE       BOOLEAN         NOT NULL DEFAULT TRUE,
                CREATED_AT      TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        logging.info("PLATFORM_USER table created/verified.")

        # Check if users already exist
        existing = conn.execute_query("SELECT COUNT(*) FROM CASEPILOT_DB.RAW.PLATFORM_USER")
        if existing[0][0] > 0:
            logging.info(f"Users already exist ({existing[0][0]}). Skipping seed.")
            return

        # Fetch 3 customer IDs for customer accounts
        cust_rows = conn.execute_query("""
            SELECT CUSTOMER_ID, CONCAT(FIRST_NAME, ' ', LAST_NAME) AS NAME, EMAIL
            FROM CASEPILOT_DB.RAW.CUSTOMER
            ORDER BY FIRST_NAME
            LIMIT 3
        """)

        users = [
            # Fraud Analysts
            {
                "USER_ID": str(uuid.uuid4()),
                "EMPLOYEE_ID": "FA001",
                "FULL_NAME": "Anjali Sinha",
                "EMAIL": "anjali.sinha@casepilot.bank",
                "PASSWORD_HASH": hash_password("analyst123"),
                "ROLE": "FRAUD_ANALYST",
                "DEPARTMENT": "Fraud Operations Center",
                "CUSTOMER_ID": None,
            },
            {
                "USER_ID": str(uuid.uuid4()),
                "EMPLOYEE_ID": "FA002",
                "FULL_NAME": "Ravi Kumar",
                "EMAIL": "ravi.kumar@casepilot.bank",
                "PASSWORD_HASH": hash_password("analyst123"),
                "ROLE": "FRAUD_ANALYST",
                "DEPARTMENT": "Fraud Operations Center",
                "CUSTOMER_ID": None,
            },
            # Bank Employees
            {
                "USER_ID": str(uuid.uuid4()),
                "EMPLOYEE_ID": "BE001",
                "FULL_NAME": "Priya Sharma",
                "EMAIL": "priya.sharma@casepilot.bank",
                "PASSWORD_HASH": hash_password("employee123"),
                "ROLE": "BANK_EMPLOYEE",
                "DEPARTMENT": "Branch Operations",
                "CUSTOMER_ID": None,
            },
            {
                "USER_ID": str(uuid.uuid4()),
                "EMPLOYEE_ID": "BE002",
                "FULL_NAME": "Arjun Patel",
                "EMAIL": "arjun.patel@casepilot.bank",
                "PASSWORD_HASH": hash_password("employee123"),
                "ROLE": "BANK_EMPLOYEE",
                "DEPARTMENT": "Customer Service",
                "CUSTOMER_ID": None,
            },
        ]

        # Add customer accounts linked to real customer IDs
        for i, cust in enumerate(cust_rows):
            users.append({
                "USER_ID": str(uuid.uuid4()),
                "EMPLOYEE_ID": f"CUST{str(i+1).zfill(3)}",
                "FULL_NAME": cust[1],
                "EMAIL": cust[2],
                "PASSWORD_HASH": hash_password("customer123"),
                "ROLE": "CUSTOMER",
                "DEPARTMENT": None,
                "CUSTOMER_ID": cust[0],
            })

        # Insert users
        cursor = conn.get_connection().cursor()
        for u in users:
            cursor.execute("""
                INSERT INTO CASEPILOT_DB.RAW.PLATFORM_USER
                (USER_ID, EMPLOYEE_ID, FULL_NAME, EMAIL, PASSWORD_HASH, ROLE, DEPARTMENT, CUSTOMER_ID)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                u["USER_ID"], u["EMPLOYEE_ID"], u["FULL_NAME"], u["EMAIL"],
                u["PASSWORD_HASH"], u["ROLE"], u["DEPARTMENT"], u["CUSTOMER_ID"]
            ))
        conn.get_connection().commit()
        cursor.close()

        logging.info(f"Seeded {len(users)} platform users successfully.")

        # Print credentials for reference
        print("\n" + "=" * 60)
        print("  CASEPILOT PLATFORM USER CREDENTIALS")
        print("=" * 60)
        print(f"  {'Role':<20} {'Employee ID':<12} {'Password'}")
        print("-" * 60)
        print(f"  {'Fraud Analyst':<20} {'FA001':<12} analyst123")
        print(f"  {'Fraud Analyst':<20} {'FA002':<12} analyst123")
        print(f"  {'Bank Employee':<20} {'BE001':<12} employee123")
        print(f"  {'Bank Employee':<20} {'BE002':<12} employee123")
        for i in range(len(cust_rows)):
            print(f"  {'Customer':<20} {f'CUST{str(i+1).zfill(3)}':<12} customer123")
        print("=" * 60)

    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()

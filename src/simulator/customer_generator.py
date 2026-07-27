"""
CasePilot — Customer Generator
================================
Generates 100 realistic banking customers with persona-driven profiles.

Personas:
    - SALARY_EMPLOYEE (40%): Regular income, moderate spending
    - STUDENT (20%): Low income, small transactions
    - BUSINESS_OWNER (25%): High income, frequent large transactions
    - TRAVELER (15%): International activity, varied geography
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from faker import Faker

from src.config.settings import (
    SIMULATION, PERSONAS, INDIAN_CITIES,
)
from src.utils.helpers import (
    generate_uuid, generate_phone_number, generate_pan_number,
    generate_aadhar_hash, weighted_choice,
)

logger = logging.getLogger(__name__)
fake = Faker("en_IN")


def _assign_persona() -> str:
    """Assign a persona based on configured distribution weights."""
    persona_weights = {k: v["weight"] for k, v in PERSONAS.items()}
    return weighted_choice(persona_weights)


def _generate_single_customer(persona: str) -> Dict[str, Any]:
    """
    Generate a single customer record based on persona.

    Args:
        persona: Customer persona type.

    Returns:
        Dictionary representing a customer row.
    """
    config = PERSONAS[persona]
    city_info = random.choice(INDIAN_CITIES)
    income = round(random.uniform(*config["income_range"]), 2)
    occupation = random.choice(config["occupations"])

    # Age distribution varies by persona
    if persona == "STUDENT":
        age = random.randint(18, 25)
    elif persona == "SALARIED":
        age = random.randint(22, 60)
    elif persona == "BUSINESS_OWNER":
        age = random.randint(25, 65)
    elif persona == "RETIRED":
        age = random.randint(60, 85)
    elif persona == "FREELANCER":
        age = random.randint(20, 50)
    elif persona == "HIGH_NET_WORTH":
        age = random.randint(30, 70)
    else:
        age = random.randint(25, 60)

    dob = datetime.now() - timedelta(days=age * 365 + random.randint(0, 364))
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1,99)}@{'gmail.com' if random.random() > 0.3 else 'yahoo.com'}"

    # KYC status - mostly verified
    kyc_status = random.choices(
        ["VERIFIED", "PENDING", "EXPIRED"],
        weights=[0.85, 0.10, 0.05],
        k=1
    )[0]

    # Risk rating based on persona + some randomness
    base_risk = config["risk_rating"]
    if random.random() < 0.1:
        risk_options = ["LOW", "MEDIUM", "HIGH"]
        base_risk = random.choice(risk_options)

    created_at = datetime.now() - timedelta(days=random.randint(30, 730))

    return {
        "CUSTOMER_ID": generate_uuid(),
        "FIRST_NAME": first_name,
        "LAST_NAME": last_name,
        "EMAIL": email,
        "PHONE": generate_phone_number(),
        "PERSONA": persona,
        "DATE_OF_BIRTH": dob.strftime("%Y-%m-%d"),
        "CITY": city_info["city"],
        "STATE": city_info["state"],
        "COUNTRY": "India",
        "PIN_CODE": city_info["pin_prefix"] + "".join(random.choices("0123456789", k=3)),
        "ANNUAL_INCOME": income,
        "OCCUPATION": occupation,
        "KYC_STATUS": kyc_status,
        "RISK_RATING": base_risk,
        "PAN_NUMBER": generate_pan_number(),
        "AADHAR_HASH": generate_aadhar_hash(),
        "CREATED_AT": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "UPDATED_AT": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "IS_ACTIVE": True,
    }


def generate_customers(count: int = None) -> List[Dict[str, Any]]:
    """
    Generate a list of realistic customer records.

    Args:
        count: Number of customers to generate. Defaults to SIMULATION config.

    Returns:
        List of customer dictionaries ready for Snowflake insertion.
    """
    count = count or SIMULATION["num_customers"]
    random.seed(SIMULATION["random_seed"])
    Faker.seed(SIMULATION["random_seed"])

    customers = []
    for i in range(count):
        persona = _assign_persona()
        customer = _generate_single_customer(persona)
        customers.append(customer)

    # Log persona distribution
    persona_counts = {}
    for c in customers:
        p = c["PERSONA"]
        persona_counts[p] = persona_counts.get(p, 0) + 1
    logger.info(f"Generated {len(customers)} customers. Distribution: {persona_counts}")

    return customers


def insert_customers_to_snowflake(customers: List[Dict[str, Any]], connection) -> int:
    """
    Insert generated customers into Snowflake RAW.CUSTOMER table.

    Args:
        customers: List of customer dictionaries.
        connection: SnowflakeConnection instance.

    Returns:
        Number of rows inserted.
    """
    connection.use_schema("RAW")

    insert_query = """
        INSERT INTO CUSTOMER (
            CUSTOMER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE, PERSONA,
            DATE_OF_BIRTH, CITY, STATE, COUNTRY, PIN_CODE, ANNUAL_INCOME,
            OCCUPATION, KYC_STATUS, RISK_RATING, PAN_NUMBER, AADHAR_HASH,
            CREATED_AT, UPDATED_AT, IS_ACTIVE
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    data = [
        (
            c["CUSTOMER_ID"], c["FIRST_NAME"], c["LAST_NAME"], c["EMAIL"],
            c["PHONE"], c["PERSONA"], c["DATE_OF_BIRTH"], c["CITY"],
            c["STATE"], c["COUNTRY"], c["PIN_CODE"], c["ANNUAL_INCOME"],
            c["OCCUPATION"], c["KYC_STATUS"], c["RISK_RATING"],
            c["PAN_NUMBER"], c["AADHAR_HASH"], c["CREATED_AT"],
            c["UPDATED_AT"], c["IS_ACTIVE"],
        )
        for c in customers
    ]

    rows = connection.execute_many(insert_query, data)
    logger.info(f"Inserted {rows} customers into Snowflake.")
    return rows


if __name__ == "__main__":
    """Generate customers and print sample output."""
    from src.utils.helpers import setup_logging
    setup_logging()

    customers = generate_customers(10)
    for c in customers[:3]:
        print(f"  {c['FIRST_NAME']} {c['LAST_NAME']} | {c['PERSONA']} | "
              f"{c['CITY']} | ₹{c['ANNUAL_INCOME']:,.0f}")
    print(f"  ... and {len(customers) - 3} more")

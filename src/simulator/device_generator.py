"""
CasePilot — Device Generator
================================
Generates 300 devices linked to customers.
Device types include phones, laptops, tablets, ATM terminals, and POS terminals.
Trust status reflects whether the device is known/verified.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.config.settings import SIMULATION, INDIAN_CITIES
from src.utils.helpers import generate_uuid, generate_ip_address

logger = logging.getLogger(__name__)

# Device specifications
DEVICE_SPECS = {
    "MOBILE": {
        "names": [
            "iPhone 15 Pro", "iPhone 14", "Samsung Galaxy S24", "Samsung Galaxy A54",
            "OnePlus 12", "Pixel 8", "Xiaomi 14", "Realme GT", "Vivo V30",
            "OPPO Reno 11", "Nothing Phone 2", "iQOO Neo 9",
        ],
        "os_options": ["iOS 17", "iOS 16", "Android 14", "Android 13"],
        "browsers": ["Safari", "Chrome Mobile", "Samsung Browser", "Firefox Mobile"],
    },
    "LAPTOP": {
        "names": [
            "MacBook Pro M3", "MacBook Air M2", "Dell XPS 15", "Lenovo ThinkPad X1",
            "HP Spectre x360", "ASUS ZenBook", "Acer Swift 5",
        ],
        "os_options": ["macOS Sonoma", "macOS Ventura", "Windows 11", "Windows 10", "Ubuntu 22.04"],
        "browsers": ["Chrome", "Safari", "Firefox", "Edge"],
    },
    "TABLET": {
        "names": [
            "iPad Pro 12.9", "iPad Air", "Samsung Galaxy Tab S9",
            "Lenovo Tab P12", "OnePlus Pad",
        ],
        "os_options": ["iPadOS 17", "Android 14", "Android 13"],
        "browsers": ["Safari", "Chrome", "Samsung Browser"],
    },
    "ATM_TERMINAL": {
        "names": ["NCR SelfServ", "Diebold Nixdorf CS", "Hitachi-Omron SR7500", "GRG H68N"],
        "os_options": ["Windows Embedded"],
        "browsers": [None],
    },
    "POS_TERMINAL": {
        "names": ["Ingenico Move 5000", "Verifone V240m", "PAX A920", "Pine Labs"],
        "os_options": ["Linux Embedded", "Android POS"],
        "browsers": [None],
    },
}

DEVICE_TYPE_WEIGHTS = {
    "MOBILE": 0.45,
    "LAPTOP": 0.20,
    "TABLET": 0.10,
    "ATM_TERMINAL": 0.10,
    "POS_TERMINAL": 0.15,
}


def generate_devices(customers: List[Dict[str, Any]], count: int = None) -> List[Dict[str, Any]]:
    """
    Generate device records linked to customers.

    Each customer gets 1-5 devices. Personal devices (MOBILE, LAPTOP, TABLET)
    are assigned to specific customers. ATM and POS terminals are shared.

    Args:
        customers: List of customer dictionaries.
        count: Number of devices. Defaults to SIMULATION config.

    Returns:
        List of device dictionaries.
    """
    count = count or SIMULATION["num_devices"]
    random.seed(SIMULATION["random_seed"] + 2)

    devices = []

    # Phase 1: Every customer gets at least one personal device (mobile)
    for customer in customers:
        cid = customer["CUSTOMER_ID"]
        city = customer["CITY"]
        specs = DEVICE_SPECS["MOBILE"]

        first_seen = datetime.strptime(customer["CREATED_AT"], "%Y-%m-%d %H:%M:%S")
        last_seen = first_seen + timedelta(days=random.randint(1, 365))

        devices.append({
            "DEVICE_ID": generate_uuid(),
            "CUSTOMER_ID": cid,
            "DEVICE_TYPE": "MOBILE",
            "DEVICE_NAME": random.choice(specs["names"]),
            "OS": random.choice(specs["os_options"]),
            "BROWSER": random.choice(specs["browsers"]),
            "IP_ADDRESS": generate_ip_address(is_indian=True),
            "CITY": city,
            "COUNTRY": "India",
            "IS_TRUSTED": True,  # Primary device is trusted
            "FIRST_SEEN": first_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "LAST_SEEN": last_seen.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Phase 2: Distribute remaining devices
    remaining = count - len(devices)
    for _ in range(remaining):
        customer = random.choice(customers)
        cid = customer["CUSTOMER_ID"]

        # Choose device type
        device_type = random.choices(
            list(DEVICE_TYPE_WEIGHTS.keys()),
            weights=list(DEVICE_TYPE_WEIGHTS.values()),
            k=1
        )[0]

        specs = DEVICE_SPECS[device_type]
        city_info = random.choice(INDIAN_CITIES)

        first_seen = datetime.strptime(customer["CREATED_AT"], "%Y-%m-%d %H:%M:%S")
        first_seen += timedelta(days=random.randint(0, 300))
        last_seen = first_seen + timedelta(days=random.randint(0, 180))

        # Trust varies: primary personal devices trusted, others less so
        is_trusted = random.choices([True, False], weights=[0.6, 0.4], k=1)[0]

        devices.append({
            "DEVICE_ID": generate_uuid(),
            "CUSTOMER_ID": cid,
            "DEVICE_TYPE": device_type,
            "DEVICE_NAME": random.choice(specs["names"]),
            "OS": random.choice(specs["os_options"]),
            "BROWSER": random.choice([b for b in specs["browsers"] if b] or [None]),
            "IP_ADDRESS": generate_ip_address(is_indian=True),
            "CITY": city_info["city"],
            "COUNTRY": "India",
            "IS_TRUSTED": is_trusted,
            "FIRST_SEEN": first_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "LAST_SEEN": last_seen.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Log summary
    type_counts = {}
    for d in devices:
        t = d["DEVICE_TYPE"]
        type_counts[t] = type_counts.get(t, 0) + 1
    trusted_count = sum(1 for d in devices if d["IS_TRUSTED"])
    logger.info(
        f"Generated {len(devices)} devices. Types: {type_counts}. "
        f"Trusted: {trusted_count}, Untrusted: {len(devices) - trusted_count}"
    )

    return devices


def insert_devices_to_snowflake(devices: List[Dict[str, Any]], connection) -> int:
    """Insert generated devices into Snowflake RAW.DEVICE table."""
    connection.use_schema("RAW")

    insert_query = """
        INSERT INTO DEVICE (
            DEVICE_ID, CUSTOMER_ID, DEVICE_TYPE, DEVICE_NAME,
            OS, BROWSER, IP_ADDRESS, CITY, COUNTRY,
            IS_TRUSTED, FIRST_SEEN, LAST_SEEN
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    data = [
        (
            d["DEVICE_ID"], d["CUSTOMER_ID"], d["DEVICE_TYPE"], d["DEVICE_NAME"],
            d["OS"], d["BROWSER"], d["IP_ADDRESS"], d["CITY"], d["COUNTRY"],
            d["IS_TRUSTED"], d["FIRST_SEEN"], d["LAST_SEEN"],
        )
        for d in devices
    ]

    rows = connection.execute_many(insert_query, data)
    logger.info(f"Inserted {rows} devices into Snowflake.")
    return rows

"""
CasePilot — Utility Helpers
=============================
Common utility functions used across the CasePilot platform.
"""

import uuid
import logging
import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List


def generate_uuid() -> str:
    """Generate a UUID4 string for use as primary keys."""
    return str(uuid.uuid4())


def generate_case_number(prefix: str = "CP") -> str:
    """Generate a human-readable case number. Format: CP-YYYYMMDD-XXXXX"""
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}-{date_part}-{random_part}"


def generate_account_number() -> str:
    """Generate a realistic 12-digit bank account number."""
    return "".join(random.choices(string.digits, k=12))


def generate_ifsc_code() -> str:
    """Generate a realistic IFSC code. Format: 4 letters + 0 + 6 digits."""
    bank_codes = ["HDFC", "ICIC", "SBIN", "AXIS", "KOTK", "PUNB", "BARB", "UTIB"]
    bank = random.choice(bank_codes)
    branch = "".join(random.choices(string.digits, k=6))
    return f"{bank}0{branch}"


def generate_pan_number() -> str:
    """Generate a realistic PAN number. Format: 5 letters + 4 digits + 1 letter."""
    part1 = "".join(random.choices(string.ascii_uppercase, k=5))
    part2 = "".join(random.choices(string.digits, k=4))
    part3 = random.choice(string.ascii_uppercase)
    return f"{part1}{part2}{part3}"


def generate_aadhar_hash() -> str:
    """Generate a fake Aadhar number and return its SHA-256 hash."""
    fake_aadhar = "".join(random.choices(string.digits, k=12))
    return hashlib.sha256(fake_aadhar.encode()).hexdigest()


def generate_phone_number() -> str:
    """Generate a realistic Indian phone number. Format: +91-XXXXXXXXXX."""
    prefixes = ["98", "97", "96", "95", "94", "93", "91", "90", "88", "87"]
    prefix = random.choice(prefixes)
    suffix = "".join(random.choices(string.digits, k=8))
    return f"+91-{prefix}{suffix}"


def generate_ip_address(is_indian: bool = True) -> str:
    """Generate a realistic IP address."""
    if is_indian:
        first_octets = [49, 103, 106, 117, 122, 152, 157, 182, 202, 203]
    else:
        first_octets = [8, 13, 20, 34, 52, 54, 72, 104, 142, 216]
    first = random.choice(first_octets)
    rest = ".".join(str(random.randint(0, 255)) for _ in range(3))
    return f"{first}.{rest}"


def format_timestamp(dt: Optional[datetime] = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime object as a string."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def random_timestamp(start: datetime, end: datetime) -> datetime:
    """Generate a random timestamp between start and end."""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def weighted_choice(choices: dict) -> str:
    """Make a weighted random selection from a dict of {item: weight}."""
    items = list(choices.keys())
    weights = list(choices.values())
    return random.choices(items, weights=weights, k=1)[0]


def chunk_list(lst: list, chunk_size: int) -> list:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def format_currency(amount: float, currency: str = "INR") -> str:
    """Format a number as currency string."""
    if currency == "INR":
        return f"₹{amount:,.2f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """Configure application-wide logging."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=level, format=log_format, handlers=handlers)
    logger = logging.getLogger("casepilot")
    logger.info("CasePilot logging initialized.")
    return logger


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default on division by zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp a value within a range."""
    return max(min_val, min(value, max_val))

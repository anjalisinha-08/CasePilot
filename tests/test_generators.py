"""
CasePilot — Unit Tests for Generators
========================================
Tests for customer, account, merchant, device, and transaction generators.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulator.customer_generator import generate_customers
from src.simulator.account_generator import generate_accounts
from src.simulator.merchant_generator import generate_merchants
from src.simulator.device_generator import generate_devices
from src.simulator.transaction_generator import generate_transactions


class TestCustomerGenerator:
    """Tests for customer_generator.py."""

    def test_generates_correct_count(self):
        customers = generate_customers(10)
        assert len(customers) == 10

    def test_customer_has_required_fields(self):
        customers = generate_customers(1)
        c = customers[0]
        required = [
            "CUSTOMER_ID", "FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE",
            "PERSONA", "DATE_OF_BIRTH", "CITY", "STATE", "COUNTRY",
            "ANNUAL_INCOME", "OCCUPATION", "KYC_STATUS", "RISK_RATING",
        ]
        for field in required:
            assert field in c, f"Missing field: {field}"

    def test_persona_is_valid(self):
        customers = generate_customers(20)
        valid = {"SALARIED", "STUDENT", "BUSINESS_OWNER", "RETIRED", "FREELANCER", "HIGH_NET_WORTH"}
        for c in customers:
            assert c["PERSONA"] in valid

    def test_country_is_india(self):
        customers = generate_customers(5)
        for c in customers:
            assert c["COUNTRY"] == "India"

    def test_uuid_format(self):
        customers = generate_customers(3)
        for c in customers:
            assert len(c["CUSTOMER_ID"]) == 36
            assert c["CUSTOMER_ID"].count("-") == 4


class TestAccountGenerator:
    """Tests for account_generator.py."""

    def test_generates_accounts(self):
        customers = generate_customers(10)
        accounts = generate_accounts(customers, 15)
        assert len(accounts) == 15

    def test_every_customer_has_account(self):
        customers = generate_customers(10)
        accounts = generate_accounts(customers, 15)
        customer_ids = {c["CUSTOMER_ID"] for c in customers}
        account_cids = {a["CUSTOMER_ID"] for a in accounts}
        assert customer_ids.issubset(account_cids)

    def test_account_has_required_fields(self):
        customers = generate_customers(5)
        accounts = generate_accounts(customers, 5)
        required = ["ACCOUNT_ID", "CUSTOMER_ID", "ACCOUNT_TYPE",
                     "ACCOUNT_NUMBER", "BALANCE", "CURRENCY"]
        for a in accounts:
            for field in required:
                assert field in a, f"Missing: {field}"

    def test_balance_positive(self):
        customers = generate_customers(5)
        accounts = generate_accounts(customers, 10)
        for a in accounts:
            assert a["BALANCE"] >= 0


class TestMerchantGenerator:
    """Tests for merchant_generator.py."""

    def test_generates_correct_count(self):
        merchants = generate_merchants(10)
        assert len(merchants) == 10

    def test_merchant_has_required_fields(self):
        merchants = generate_merchants(3)
        required = ["MERCHANT_ID", "MERCHANT_NAME", "CATEGORY",
                     "MCC_CODE", "RISK_LEVEL"]
        for m in merchants:
            for field in required:
                assert field in m, f"Missing: {field}"

    def test_risk_levels_valid(self):
        merchants = generate_merchants(20)
        valid = {"LOW", "MEDIUM", "HIGH"}
        for m in merchants:
            assert m["RISK_LEVEL"] in valid


class TestDeviceGenerator:
    """Tests for device_generator.py."""

    def test_generates_devices(self):
        customers = generate_customers(10)
        devices = generate_devices(customers, 30)
        assert len(devices) == 30

    def test_device_has_required_fields(self):
        customers = generate_customers(5)
        devices = generate_devices(customers, 10)
        required = ["DEVICE_ID", "CUSTOMER_ID", "DEVICE_TYPE", "IS_TRUSTED"]
        for d in devices:
            for field in required:
                assert field in d, f"Missing: {field}"


class TestTransactionGenerator:
    """Tests for transaction_generator.py."""

    def test_generates_transactions(self):
        customers = generate_customers(10)
        accounts = generate_accounts(customers, 15)
        merchants = generate_merchants(10)
        devices = generate_devices(customers, 20)
        txns = generate_transactions(customers, accounts, merchants, devices, 100)
        assert len(txns) >= 100  # May be more due to burst injections

    def test_transaction_has_required_fields(self):
        customers = generate_customers(5)
        accounts = generate_accounts(customers, 5)
        merchants = generate_merchants(5)
        devices = generate_devices(customers, 10)
        txns = generate_transactions(customers, accounts, merchants, devices, 20)
        required = ["TXN_ID", "ACCOUNT_ID", "CUSTOMER_ID", "AMOUNT",
                     "CHANNEL", "TXN_TIMESTAMP"]
        for t in txns[:5]:
            for field in required:
                assert field in t, f"Missing: {field}"

    def test_channels_valid(self):
        customers = generate_customers(5)
        accounts = generate_accounts(customers, 5)
        merchants = generate_merchants(5)
        devices = generate_devices(customers, 10)
        txns = generate_transactions(customers, accounts, merchants, devices, 50)
        valid = {"UPI", "IMPS", "NEFT", "RTGS", "POS", "ATM", "ONLINE_BANKING"}
        for t in txns:
            assert t["CHANNEL"] in valid

    def test_suspicious_transactions_exist(self):
        customers = generate_customers(10)
        accounts = generate_accounts(customers, 15)
        merchants = generate_merchants(10)
        devices = generate_devices(customers, 20)
        txns = generate_transactions(customers, accounts, merchants, devices, 200)
        suspicious = [t for t in txns if t.get("IS_FRAUD")]
        assert len(suspicious) > 0, "No suspicious (fraudulent) transactions generated"

"""
CasePilot — Unit Tests for Alert Engine
==========================================
Tests for all 5 alert rules and the batch engine.
"""

import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.alerts.alert_engine import (
    check_high_value_txn, check_odd_hour_activity,
    check_new_device, check_foreign_activity,
    check_rapid_burst, run_alert_engine,
)
from src.utils.helpers import generate_uuid


def _make_txn(**overrides):
    """Create a test transaction with defaults."""
    base = {
        "TXN_ID": generate_uuid(),
        "ACCOUNT_ID": generate_uuid(),
        "CUSTOMER_ID": generate_uuid(),
        "AMOUNT": 1000,
        "CHANNEL": "UPI",
        "TXN_TIMESTAMP": "2026-07-10 14:30:00",
        "DESCRIPTION": "Test txn",
        "MERCHANT_COUNTRY": "India",
        "IS_INTERNATIONAL": False,
        "DEVICE_ID": generate_uuid(),
        "STATUS": "COMPLETED",
    }
    base.update(overrides)
    return base


class TestHighValueTxn:
    def test_triggers_above_threshold(self):
        txn = _make_txn(AMOUNT=30000)
        alert = check_high_value_txn(txn)
        assert alert is not None
        assert alert["ALERT_TYPE"] == "HIGH_VALUE_TXN"

    def test_no_trigger_below_threshold(self):
        txn = _make_txn(AMOUNT=5000)
        assert check_high_value_txn(txn) is None

    def test_severity_critical(self):
        txn = _make_txn(AMOUNT=150000)
        alert = check_high_value_txn(txn)
        assert alert["SEVERITY"] == "CRITICAL"

    def test_severity_medium(self):
        txn = _make_txn(AMOUNT=26000)
        alert = check_high_value_txn(txn)
        assert alert["SEVERITY"] == "MEDIUM"


class TestOddHourActivity:
    def test_triggers_at_2am(self):
        txn = _make_txn(TXN_TIMESTAMP="2026-07-10 02:30:00")
        alert = check_odd_hour_activity(txn)
        assert alert is not None
        assert alert["ALERT_TYPE"] == "ODD_HOUR_ACTIVITY"

    def test_no_trigger_at_noon(self):
        txn = _make_txn(TXN_TIMESTAMP="2026-07-10 12:00:00")
        assert check_odd_hour_activity(txn) is None


class TestNewDevice:
    def test_triggers_untrusted_device(self):
        device_id = generate_uuid()
        txn = _make_txn(DEVICE_ID=device_id, AMOUNT=15000)
        devices = [{"DEVICE_ID": device_id, "IS_TRUSTED": False,
                     "DEVICE_NAME": "Unknown Phone", "DEVICE_TYPE": "MOBILE",
                     "IP_ADDRESS": "1.2.3.4"}]
        alert = check_new_device(txn, devices)
        assert alert is not None
        assert alert["ALERT_TYPE"] == "NEW_DEVICE_USED"

    def test_no_trigger_trusted_device(self):
        device_id = generate_uuid()
        txn = _make_txn(DEVICE_ID=device_id)
        devices = [{"DEVICE_ID": device_id, "IS_TRUSTED": True}]
        assert check_new_device(txn, devices) is None


class TestForeignActivity:
    def test_triggers_foreign(self):
        txn = _make_txn(MERCHANT_COUNTRY="UAE", IS_INTERNATIONAL=True)
        alert = check_foreign_activity(txn)
        assert alert is not None
        assert alert["ALERT_TYPE"] == "FOREIGN_ACTIVITY"

    def test_no_trigger_domestic(self):
        txn = _make_txn(MERCHANT_COUNTRY="India", IS_INTERNATIONAL=False)
        assert check_foreign_activity(txn) is None


class TestRapidBurst:
    def test_detects_burst(self):
        cid = generate_uuid()
        txns = [
            _make_txn(CUSTOMER_ID=cid, TXN_TIMESTAMP=f"2026-07-10 10:0{i}:00")
            for i in range(7)
        ]
        alerts = check_rapid_burst(txns)
        assert len(alerts) > 0
        assert alerts[0]["ALERT_TYPE"] == "RAPID_TXN_BURST"

    def test_no_burst_spread_out(self):
        cid = generate_uuid()
        txns = [
            _make_txn(CUSTOMER_ID=cid, TXN_TIMESTAMP=f"2026-07-10 {10+i}:00:00")
            for i in range(5)
        ]
        alerts = check_rapid_burst(txns)
        assert len(alerts) == 0


class TestAlertEngine:
    def test_engine_returns_list(self):
        txns = [_make_txn(AMOUNT=50000)]
        devices = []
        alerts = run_alert_engine(txns, devices)
        assert isinstance(alerts, list)
        assert len(alerts) > 0

"""
CasePilot — Unit Tests for Priority Scoring
==============================================
Tests for the multi-factor priority scoring algorithm.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.intelligence.priority_scoring import calculate_priority_score


def _make_alert(**overrides):
    base = {
        "ALERT_ID": "test-alert-1",
        "ALERT_TYPE": "HIGH_VALUE_TXN",
        "SEVERITY": "HIGH",
        "TRIGGERED_AMOUNT": 50000,
        "CREATED_AT": "2026-07-10 14:30:00",
    }
    base.update(overrides)
    return base


def _make_enrichment(**overrides):
    base = {
        "CUSTOMER_PROFILE": {
            "risk_rating": "MEDIUM",
            "kyc_status": "VERIFIED",
            "account_age_days": 365,
            "name": "Test User",
        },
        "TXN_HISTORY": {
            "recent_transactions": [],
            "total_transactions": 100,
        },
        "DEVICE_HISTORY": [
            {"is_trusted": True},
            {"is_trusted": True},
        ],
        "PREVIOUS_ALERTS": [],
        "HISTORICAL_STATS": {
            "avg_transaction_amount": 5000,
            "std_dev_amount": 3000,
            "total_transactions": 100,
        },
    }
    base.update(overrides)
    return base


class TestPriorityScoring:

    def test_returns_required_fields(self):
        result = calculate_priority_score(_make_alert(), _make_enrichment())
        assert "priority_score" in result
        assert "risk_band" in result
        assert "factor_scores" in result

    def test_score_in_range(self):
        result = calculate_priority_score(_make_alert(), _make_enrichment())
        assert 0 <= result["priority_score"] <= 100

    def test_risk_band_valid(self):
        result = calculate_priority_score(_make_alert(), _make_enrichment())
        assert result["risk_band"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    def test_critical_severity_high_score(self):
        alert = _make_alert(SEVERITY="CRITICAL", TRIGGERED_AMOUNT=200000)
        enrichment = _make_enrichment(
            CUSTOMER_PROFILE={"risk_rating": "HIGH", "kyc_status": "EXPIRED", "account_age_days": 15},
            PREVIOUS_ALERTS=[{"severity": "HIGH"}] * 10,
            DEVICE_HISTORY=[{"is_trusted": False}],
        )
        result = calculate_priority_score(alert, enrichment)
        assert result["priority_score"] >= 60

    def test_low_severity_low_score(self):
        alert = _make_alert(SEVERITY="LOW", TRIGGERED_AMOUNT=1000, ALERT_TYPE="HIGH_VALUE_TXN")
        enrichment = _make_enrichment(
            CUSTOMER_PROFILE={"risk_rating": "LOW", "kyc_status": "VERIFIED", "account_age_days": 730},
            HISTORICAL_STATS={"avg_transaction_amount": 900, "std_dev_amount": 500},
        )
        result = calculate_priority_score(alert, enrichment)
        assert result["priority_score"] <= 50

    def test_factor_scores_present(self):
        result = calculate_priority_score(_make_alert(), _make_enrichment())
        factors = result["factor_scores"]
        expected_keys = ["alert_severity", "amount_deviation", "customer_risk",
                         "previous_alerts", "device_trust", "time_anomaly", "geo_anomaly"]
        for key in expected_keys:
            assert key in factors

    def test_expired_kyc_increases_score(self):
        base_enrichment = _make_enrichment()
        result_verified = calculate_priority_score(_make_alert(), base_enrichment)

        expired_enrichment = _make_enrichment(
            CUSTOMER_PROFILE={"risk_rating": "MEDIUM", "kyc_status": "EXPIRED", "account_age_days": 365}
        )
        result_expired = calculate_priority_score(_make_alert(), expired_enrichment)
        assert result_expired["priority_score"] >= result_verified["priority_score"]

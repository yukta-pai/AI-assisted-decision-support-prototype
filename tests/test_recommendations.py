"""
test_recommendations.py
Unit tests for the recommendation engine.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.recommendation_engine import generate_recommendations, compute_priority_tag


class TestGenerateRecommendations:

    def _make_kpi(self, name, label, pct_change, status):
        return {
            "name": name,
            "label": label,
            "format": "currency",
            "current": 100000,
            "previous": 100000 / (1 + pct_change) if pct_change != -1 else 0,
            "pct_change": pct_change,
            "status": status,
        }

    def test_no_alerts_returns_empty(self):
        kpis = [self._make_kpi("gross_revenue", "Gross Revenue", 0.05, "ok")]
        result = generate_recommendations(kpis)
        assert result == []

    def test_traffic_drop_triggers_acquisition_rec(self):
        kpis = [self._make_kpi("traffic", "Traffic", -0.15, "alert")]
        result = generate_recommendations(kpis)
        ids = [r["id"] for r in result]
        assert "traffic_acquisition" in ids

    def test_conversion_drop_triggers_funnel_rec(self):
        kpis = [self._make_kpi("conversion_rate", "Conversion Rate", -0.10, "alert")]
        result = generate_recommendations(kpis)
        ids = [r["id"] for r in result]
        assert "conversion_funnel" in ids

    def test_high_return_rate_triggers_quality_rec(self):
        kpis = [self._make_kpi("return_rate", "Return Rate", 0.08, "alert")]
        result = generate_recommendations(kpis)
        ids = [r["id"] for r in result]
        assert "returns_quality" in ids

    def test_margin_drop_triggers_efficiency_rec(self):
        kpis = [self._make_kpi("gross_margin", "Gross Margin", -0.15, "alert")]
        result = generate_recommendations(kpis)
        ids = [r["id"] for r in result]
        assert "margin_efficiency" in ids

    def test_small_drop_below_threshold_not_triggered(self):
        # -2% traffic should NOT trigger the -8% threshold
        kpis = [self._make_kpi("traffic", "Traffic", -0.02, "ok")]
        result = generate_recommendations(kpis)
        ids = [r["id"] for r in result]
        assert "traffic_acquisition" not in ids

    def test_result_has_required_fields(self):
        kpis = [self._make_kpi("traffic", "Traffic", -0.20, "alert")]
        result = generate_recommendations(kpis)
        assert len(result) > 0
        rec = result[0]
        for field in ("id", "title", "rationale", "actions", "impact",
                      "effort", "urgency", "confidence", "priority_tag", "category"):
            assert field in rec, f"Missing field: {field}"

    def test_actions_is_list(self):
        kpis = [self._make_kpi("conversion_rate", "Conversion Rate", -0.12, "alert")]
        result = generate_recommendations(kpis)
        for rec in result:
            assert isinstance(rec["actions"], list)
            assert len(rec["actions"]) > 0

    def test_sorted_by_priority(self):
        kpis = [
            self._make_kpi("traffic", "Traffic", -0.20, "alert"),
            self._make_kpi("return_rate", "Return Rate", 0.10, "alert"),
            self._make_kpi("marketing_spend", "Marketing Spend", 0.25, "alert"),
        ]
        result = generate_recommendations(kpis)
        priority_order = {"Critical": 0, "High priority": 1, "Medium priority": 2, "Low priority": 3}
        priorities = [priority_order.get(r["priority_tag"], 9) for r in result]
        assert priorities == sorted(priorities)

    def test_multiple_triggers(self):
        kpis = [
            self._make_kpi("traffic", "Traffic", -0.20, "alert"),
            self._make_kpi("conversion_rate", "Conversion Rate", -0.10, "alert"),
            self._make_kpi("return_rate", "Return Rate", 0.08, "alert"),
            self._make_kpi("gross_margin", "Gross Margin", -0.15, "alert"),
        ]
        result = generate_recommendations(kpis)
        assert len(result) >= 3

    def test_confidence_in_valid_range(self):
        kpis = [self._make_kpi("traffic", "Traffic", -0.20, "alert")]
        result = generate_recommendations(kpis)
        for rec in result:
            assert 0.0 <= rec["confidence"] <= 1.0


class TestPriorityMatrix:

    def test_high_impact_high_urgency_high_confidence(self):
        tag = compute_priority_tag("high", "high", 0.80)
        assert tag == "Critical"

    def test_high_impact_medium_urgency(self):
        tag = compute_priority_tag("high", "medium", 0.80)
        assert tag in ("High priority", "Critical")

    def test_low_confidence_medium_result(self):
        tag = compute_priority_tag("medium", "medium", 0.55)
        assert tag in ("Medium priority", "Low priority")

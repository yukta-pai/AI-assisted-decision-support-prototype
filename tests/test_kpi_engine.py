"""
test_kpi_engine.py
Unit tests for KPI aggregation, comparison, and alert logic.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from src.kpi_engine import (
    aggregate_period, compute_kpi_comparison,
    get_weekly_trend, get_top_alerts
)
from src.data_generator import generate_dataset


@pytest.fixture(scope="module")
def full_dataset():
    return generate_dataset(periods=52)


def make_period(df, start, n):
    dates = sorted(df["date"].unique())
    return df[df["date"].isin(dates[start:start + n])]


class TestAggregatePeriod:

    def test_returns_series(self, full_dataset):
        period = make_period(full_dataset, 10, 4)
        result = aggregate_period(period)
        assert isinstance(result, pd.Series)

    def test_formula_orders(self, full_dataset):
        period = make_period(full_dataset, 10, 4)
        agg = aggregate_period(period)
        # Orders should equal sum of orders in the slice
        assert abs(agg["orders"] - period["orders"].sum()) < 1

    def test_formula_net_revenue(self, full_dataset):
        period = make_period(full_dataset, 10, 4)
        agg = aggregate_period(period)
        expected = agg["gross_revenue"] - agg["refunds"]
        assert abs(agg["net_revenue"] - expected) < 0.01

    def test_empty_returns_empty(self):
        result = aggregate_period(pd.DataFrame())
        assert result.empty

    def test_conversion_rate_weighted(self, full_dataset):
        period = make_period(full_dataset, 10, 4)
        agg = aggregate_period(period)
        expected_conv = period["orders"].sum() / period["traffic"].sum()
        assert abs(agg["conversion_rate"] - expected_conv) < 0.0001


class TestComputeKpiComparison:

    def test_returns_list_of_dicts(self, full_dataset):
        cur = make_period(full_dataset, 20, 4)
        pri = make_period(full_dataset, 16, 4)
        result = compute_kpi_comparison(cur, pri)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_has_required_fields(self, full_dataset):
        cur = make_period(full_dataset, 20, 4)
        pri = make_period(full_dataset, 16, 4)
        result = compute_kpi_comparison(cur, pri)
        for row in result:
            for field in ("name", "label", "format", "current", "previous",
                          "pct_change", "status"):
                assert field in row

    def test_status_values_valid(self, full_dataset):
        cur = make_period(full_dataset, 20, 4)
        pri = make_period(full_dataset, 16, 4)
        result = compute_kpi_comparison(cur, pri)
        for row in result:
            assert row["status"] in ("ok", "warning", "alert")

    def test_empty_prior_still_returns(self, full_dataset):
        cur = make_period(full_dataset, 20, 4)
        result = compute_kpi_comparison(cur, pd.DataFrame())
        assert isinstance(result, list)


class TestGetTopAlerts:

    def test_only_alerts_and_warnings(self, full_dataset):
        cur = make_period(full_dataset, 20, 4)
        pri = make_period(full_dataset, 16, 4)
        kpis = compute_kpi_comparison(cur, pri)
        alerts = get_top_alerts(kpis)
        for a in alerts:
            assert a["status"] in ("alert", "warning")

    def test_sorted_alert_first(self):
        mock_kpis = [
            {"name": "a", "label": "A", "format": "currency",
             "current": 1, "previous": 1, "pct_change": -0.05, "status": "warning"},
            {"name": "b", "label": "B", "format": "currency",
             "current": 1, "previous": 1, "pct_change": -0.20, "status": "alert"},
        ]
        alerts = get_top_alerts(mock_kpis)
        assert alerts[0]["status"] == "alert"


class TestWeeklyTrend:

    def test_returns_dataframe(self, full_dataset):
        result = get_weekly_trend(full_dataset, "gross_revenue")
        assert isinstance(result, pd.DataFrame)

    def test_sorted_by_date(self, full_dataset):
        result = get_weekly_trend(full_dataset, "gross_revenue")
        assert list(result["date"]) == sorted(result["date"].tolist())

    def test_correct_columns(self, full_dataset):
        result = get_weekly_trend(full_dataset, "gross_revenue")
        assert "date" in result.columns
        assert "gross_revenue" in result.columns

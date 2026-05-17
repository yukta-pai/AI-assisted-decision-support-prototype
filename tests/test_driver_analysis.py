"""
test_driver_analysis.py
Unit tests for driver attribution logic.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from src.driver_analysis import compute_driver_scores, get_narrative_summary
from src.data_generator import generate_dataset


@pytest.fixture(scope="module")
def dataset():
    return generate_dataset(periods=52)


def make_period(df, start_week, n_weeks):
    dates = sorted(df["date"].unique())
    selected = dates[start_week: start_week + n_weeks]
    return df[df["date"].isin(selected)]


class TestDriverScores:

    def test_returns_list(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "gross_revenue")
        assert isinstance(result, list)

    def test_all_drivers_present(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "gross_revenue")
        driver_names = [d["driver"] for d in result]
        for expected in ["traffic", "conversion_rate", "avg_order_value", "return_rate"]:
            assert expected in driver_names

    def test_relevance_sums_to_one(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "gross_revenue")
        total = sum(d["relevance"] for d in result)
        assert abs(total - 1.0) < 0.01, f"Relevance sum should be ~1.0, got {total}"

    def test_sorted_descending(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "gross_revenue")
        scores = [d["relevance"] for d in result]
        assert scores == sorted(scores, reverse=True)

    def test_relevance_in_range(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "gross_revenue")
        for d in result:
            assert 0.0 <= d["relevance"] <= 1.0

    def test_impact_direction_valid(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "gross_revenue")
        for d in result:
            assert d["impact_direction"] in ("positive", "negative")

    def test_empty_prior_returns_empty(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = pd.DataFrame()
        result = compute_driver_scores(cur, pri, "gross_revenue")
        assert result == []

    def test_unknown_target_returns_empty(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "nonexistent_kpi")
        assert result == []

    def test_margin_target(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        result = compute_driver_scores(cur, pri, "gross_margin")
        assert len(result) > 0
        total = sum(d["relevance"] for d in result)
        assert abs(total - 1.0) < 0.01


class TestNarrativeSummary:

    def test_returns_string(self, dataset):
        cur = make_period(dataset, 20, 4)
        pri = make_period(dataset, 16, 4)
        drivers = compute_driver_scores(cur, pri, "gross_revenue")
        result = get_narrative_summary(drivers, "gross_revenue")
        assert isinstance(result, str)
        assert len(result) > 20

    def test_empty_drivers(self):
        result = get_narrative_summary([], "gross_revenue")
        assert "No significant" in result

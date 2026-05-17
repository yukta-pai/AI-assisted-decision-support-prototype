"""
test_scenarios.py
Unit tests for the scenario simulation engine.
Verifies formula consistency and boundary behaviour.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from src.scenario_simulator import run_scenario, format_scenario_table
from src.data_generator import generate_dataset


@pytest.fixture(scope="module")
def baseline_df():
    df = generate_dataset(periods=52)
    dates = sorted(df["date"].unique())
    selected = dates[20:28]
    return df[df["date"].isin(selected)]


class TestRunScenario:

    def test_returns_dict(self, baseline_df):
        result = run_scenario(baseline_df)
        assert isinstance(result, dict)
        assert "baseline" in result
        assert "projected" in result
        assert "delta" in result
        assert "delta_pct" in result

    def test_no_changes_equals_baseline(self, baseline_df):
        result = run_scenario(baseline_df)
        for key in ("gross_revenue", "orders", "traffic"):
            base = result["baseline"][key]
            proj = result["projected"][key]
            assert abs(proj - base) < 0.01, f"{key}: no-change scenario should match baseline"

    def test_traffic_increase_raises_revenue(self, baseline_df):
        result = run_scenario(baseline_df, traffic_change=0.10)
        assert result["projected"]["gross_revenue"] > result["baseline"]["gross_revenue"]
        assert result["projected"]["orders"] > result["baseline"]["orders"]

    def test_traffic_increase_delta_pct(self, baseline_df):
        result = run_scenario(baseline_df, traffic_change=0.10)
        traffic_delta_pct = result["delta_pct"]["traffic"]
        assert abs(traffic_delta_pct - 0.10) < 0.001

    def test_conversion_increase_raises_orders(self, baseline_df):
        result = run_scenario(baseline_df, conversion_change=0.005)
        assert result["projected"]["orders"] > result["baseline"]["orders"]

    def test_return_rate_decrease_raises_net_revenue(self, baseline_df):
        result = run_scenario(baseline_df, return_rate_change=-0.02)
        assert result["projected"]["net_revenue"] > result["baseline"]["net_revenue"]
        assert result["projected"]["refunds"] < result["baseline"]["refunds"]

    def test_return_rate_ceiling(self, baseline_df):
        # Even with extreme input, return rate should stay below 50%
        result = run_scenario(baseline_df, return_rate_change=0.99)
        assert result["projected"]["return_rate"] <= 0.50

    def test_conversion_floor(self, baseline_df):
        result = run_scenario(baseline_df, conversion_change=-0.99)
        assert result["projected"]["conversion_rate"] >= 0.005

    def test_formula_consistency(self, baseline_df):
        """
        Verify: orders = traffic * conversion_rate
        gross_revenue = orders * aov
        refunds = gross_revenue * return_rate
        net_revenue = gross_revenue - refunds
        """
        result = run_scenario(baseline_df, traffic_change=0.05, conversion_change=0.003)
        p = result["projected"]

        expected_orders = p["traffic"] * p["conversion_rate"]
        assert abs(p["orders"] - expected_orders) < 1.0

        expected_gross_rev = p["orders"] * p["avg_order_value"]
        assert abs(p["gross_revenue"] - expected_gross_rev) < 1.0

        expected_refunds = p["gross_revenue"] * p["return_rate"]
        assert abs(p["refunds"] - expected_refunds) < 1.0

        expected_net_rev = p["gross_revenue"] - p["refunds"]
        assert abs(p["net_revenue"] - expected_net_rev) < 0.01

    def test_marketing_increase_reduces_margin(self, baseline_df):
        result = run_scenario(baseline_df, marketing_change=0.50)
        assert result["projected"]["gross_margin"] < result["baseline"]["gross_margin"]

    def test_combined_scenario(self, baseline_df):
        result = run_scenario(
            baseline_df,
            traffic_change=0.10,
            conversion_change=0.005,
            return_rate_change=-0.02,
            marketing_change=0.05,
        )
        # Revenue should be higher
        assert result["projected"]["gross_revenue"] > result["baseline"]["gross_revenue"]
        # Net revenue should be higher (less returns)
        assert result["projected"]["net_revenue"] > result["baseline"]["net_revenue"]

    def test_empty_df_returns_empty(self):
        result = run_scenario(pd.DataFrame())
        assert result == {}


class TestFormatScenarioTable:

    def test_returns_dataframe(self, baseline_df):
        scenario = run_scenario(baseline_df, traffic_change=0.10)
        df = format_scenario_table(scenario)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_has_required_columns(self, baseline_df):
        scenario = run_scenario(baseline_df, traffic_change=0.10)
        df = format_scenario_table(scenario)
        for col in ("KPI", "Baseline", "Projected", "Change %"):
            assert col in df.columns

    def test_empty_scenario_returns_empty(self):
        df = format_scenario_table({})
        assert df.empty

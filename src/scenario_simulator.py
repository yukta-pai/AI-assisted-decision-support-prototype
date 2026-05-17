"""
scenario_simulator.py
Applies user-defined business assumptions to a baseline period
and returns projected KPI outcomes. Deterministic, formula-based.
"""

import pandas as pd
import numpy as np
from src.kpi_engine import aggregate_period


def run_scenario(
    baseline_df: pd.DataFrame,
    traffic_change: float = 0.0,          # e.g. +0.10 = +10%
    conversion_change: float = 0.0,       # e.g. +0.005 = +0.5pp
    aov_change: float = 0.0,              # e.g. +0.05 = +5%
    marketing_change: float = 0.0,        # e.g. +0.10 = +10%
    return_rate_change: float = 0.0,      # e.g. -0.02 = -2pp
    margin_change: float = 0.0,           # e.g. +0.02 = +2pp
) -> dict:
    """
    Apply assumption deltas to a baseline period aggregate.

    Returns:
        baseline: dict of current KPI values
        projected: dict of projected KPI values
        delta: dict of absolute change
        delta_pct: dict of % change
    """
    base = aggregate_period(baseline_df)
    if base.empty:
        return {}

    # --- Apply assumptions ---
    sim_traffic = base["traffic"] * (1 + traffic_change)
    sim_conversion = base["conversion_rate"] + conversion_change
    sim_conversion = float(np.clip(sim_conversion, 0.005, 0.25))
    sim_aov = base["avg_order_value"] * (1 + aov_change)
    sim_marketing = base["marketing_spend"] * (1 + marketing_change)

    base_return = base["return_rate"]
    sim_return = float(np.clip(base_return + return_rate_change, 0.005, 0.50))

    base_margin = base["margin_pct"]
    sim_margin = float(np.clip(base_margin + margin_change, 0.05, 0.80))

    # --- Recompute derived metrics ---
    sim_orders = sim_traffic * sim_conversion
    sim_gross_revenue = sim_orders * sim_aov
    sim_refunds = sim_gross_revenue * sim_return
    sim_net_revenue = sim_gross_revenue - sim_refunds
    sim_gross_margin = (sim_net_revenue * sim_margin) - sim_marketing
    sim_roas = sim_gross_revenue / sim_marketing if sim_marketing > 0 else 0
    sim_cac = sim_marketing / sim_orders if sim_orders > 0 else 0

    projected = {
        "traffic": sim_traffic,
        "conversion_rate": sim_conversion,
        "orders": sim_orders,
        "avg_order_value": sim_aov,
        "gross_revenue": sim_gross_revenue,
        "marketing_spend": sim_marketing,
        "return_rate": sim_return,
        "refunds": sim_refunds,
        "net_revenue": sim_net_revenue,
        "margin_pct": sim_margin,
        "gross_margin": sim_gross_margin,
        "roas": sim_roas,
        "cac_proxy": sim_cac,
    }

    baseline_dict = base.to_dict()
    delta = {k: projected[k] - baseline_dict.get(k, 0) for k in projected}
    delta_pct = {
        k: (delta[k] / baseline_dict[k]) if baseline_dict.get(k, 0) != 0 else 0
        for k in projected
    }

    return {
        "baseline": baseline_dict,
        "projected": projected,
        "delta": delta,
        "delta_pct": delta_pct,
        "assumptions": {
            "traffic_change": traffic_change,
            "conversion_change": conversion_change,
            "aov_change": aov_change,
            "marketing_change": marketing_change,
            "return_rate_change": return_rate_change,
            "margin_change": margin_change,
        },
    }


def format_scenario_table(scenario: dict) -> pd.DataFrame:
    """
    Format scenario output as a display-ready DataFrame.
    Shows baseline, projected, and delta for key KPIs.
    """
    if not scenario:
        return pd.DataFrame()

    display_kpis = [
        ("traffic",         "Traffic",          "number"),
        ("orders",          "Orders",            "number"),
        ("conversion_rate", "Conversion Rate",   "percent"),
        ("avg_order_value", "Avg Order Value",   "currency"),
        ("gross_revenue",   "Gross Revenue",     "currency"),
        ("net_revenue",     "Net Revenue",       "currency"),
        ("gross_margin",    "Gross Margin",      "currency"),
        ("return_rate",     "Return Rate",       "percent"),
        ("marketing_spend", "Marketing Spend",   "currency"),
        ("roas",            "ROAS",              "ratio"),
    ]

    rows = []
    for col, label, fmt in display_kpis:
        base_val = scenario["baseline"].get(col, 0)
        proj_val = scenario["projected"].get(col, 0)
        d_pct = scenario["delta_pct"].get(col, 0)
        rows.append({
            "KPI": label,
            "Baseline": base_val,
            "Projected": proj_val,
            "Change %": d_pct,
            "_format": fmt,
            "_delta": scenario["delta"].get(col, 0),
        })

    return pd.DataFrame(rows)

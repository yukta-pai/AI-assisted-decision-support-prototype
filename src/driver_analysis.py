"""
driver_analysis.py
Attributes KPI movement to likely business drivers using a weighted
dependency map. Returns ranked relevance scores, not a single explanation.
"""

import pandas as pd
import numpy as np
from src.kpi_engine import aggregate_period
from src.utils import load_config, pct_change

CONFIG = load_config()

# Dependency maps: which metrics drive which target KPI
DEPENDENCY_MAP = {
    "gross_revenue": {
        "traffic": 0.35,
        "conversion_rate": 0.30,
        "avg_order_value": 0.20,
        "return_rate": -0.15,   # negative: higher return rate → lower revenue
    },
    "gross_margin": {
        "net_revenue": 0.40,
        "return_rate": -0.25,
        "marketing_spend": -0.20,
        "margin_pct": 0.15,
    },
    "net_revenue": {
        "gross_revenue": 0.50,
        "return_rate": -0.30,
        "refunds": -0.20,
    },
}

KPI_LABELS = {
    "traffic": "Traffic volume",
    "conversion_rate": "Conversion rate",
    "avg_order_value": "Average order value",
    "return_rate": "Return rate",
    "net_revenue": "Net revenue",
    "gross_revenue": "Gross revenue",
    "marketing_spend": "Marketing spend",
    "margin_pct": "Gross margin %",
    "refunds": "Refunds",
    "orders": "Orders",
}

DIRECTION_LABELS = {
    1: "decline",
    -1: "improvement",
}


def compute_driver_scores(
    current_period: pd.DataFrame,
    previous_period: pd.DataFrame,
    target_kpi: str = "gross_revenue",
) -> list[dict]:
    """
    Compute ranked driver relevance scores for a target KPI.

    Method:
    1. Measure % change in each driver metric (current vs previous).
    2. Multiply by the dependency weight.
    3. Normalise into [0, 1] relevance scores.
    4. Return ranked list with direction context.
    """
    if target_kpi not in DEPENDENCY_MAP:
        return []

    current_agg = aggregate_period(current_period)
    previous_agg = aggregate_period(previous_period)

    if current_agg.empty or previous_agg.empty:
        return []

    weights = DEPENDENCY_MAP[target_kpi]
    raw_scores = {}

    for driver, weight in weights.items():
        c_val = current_agg.get(driver, 0)
        p_val = previous_agg.get(driver, 0)
        delta = pct_change(c_val, p_val)

        # Weighted impact: magnitude of change × dependency weight
        # Sign of weight encodes direction of relationship
        impact = delta * abs(weight)

        # For negatively-weighted drivers (return_rate, spend),
        # an increase in the driver is a negative impact on target
        if weight < 0:
            impact = -impact

        raw_scores[driver] = {
            "delta": delta,
            "weight": weight,
            "weighted_impact": impact,
        }

    # Normalise absolute weighted impacts to sum to 1
    total_abs = sum(abs(v["weighted_impact"]) for v in raw_scores.values())
    if total_abs == 0:
        return []

    results = []
    for driver, data in raw_scores.items():
        relevance = abs(data["weighted_impact"]) / total_abs
        delta = data["delta"]

        # Direction: did this driver move in a way that hurt the target?
        weight = data["weight"]
        if weight > 0:
            hurting = delta < 0
        else:
            hurting = delta > 0

        results.append({
            "driver": driver,
            "label": KPI_LABELS.get(driver, driver),
            "current_value": float(current_agg.get(driver, 0)),
            "previous_value": float(previous_agg.get(driver, 0)),
            "pct_change": delta,
            "relevance": round(relevance, 3),
            "impact_direction": "negative" if hurting else "positive",
            "weight": weight,
        })

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results


def get_narrative_summary(drivers: list[dict], target_kpi: str) -> str:
    """
    Build a one-sentence plain-English narrative of top 3 drivers.
    This is used as input to the LLM summary — not final user output.
    """
    if not drivers:
        return "No significant drivers identified."

    top = drivers[:3]
    parts = []
    for d in top:
        direction = "declined" if d["impact_direction"] == "negative" else "improved"
        parts.append(
            f"{d['label']} {direction} by {abs(d['pct_change'])*100:.1f}% "
            f"(relevance: {d['relevance']:.0%})"
        )

    return (
        f"For {target_kpi.replace('_', ' ')}, the primary contributing factors were: "
        + "; ".join(parts) + "."
    )

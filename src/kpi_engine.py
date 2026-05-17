"""
kpi_engine.py
Computes KPI summaries, period-over-period changes, and alert flags.
Designed to work on aggregated (filtered) data slices.
"""

import pandas as pd
import numpy as np
from src.utils import load_config, pct_change

CONFIG = load_config()

KPI_COLUMNS = [
    "traffic", "orders", "conversion_rate", "avg_order_value",
    "gross_revenue", "marketing_spend", "return_rate", "refunds",
    "net_revenue", "margin_pct", "gross_margin", "roas", "cac_proxy",
]

DISPLAY_KPIS = [
    ("gross_revenue",   "Gross Revenue",    "currency"),
    ("net_revenue",     "Net Revenue",      "currency"),
    ("traffic",         "Traffic",          "number"),
    ("orders",          "Orders",           "number"),
    ("conversion_rate", "Conversion Rate",  "percent"),
    ("avg_order_value", "Avg Order Value",  "currency"),
    ("gross_margin",    "Gross Margin",     "currency"),
    ("return_rate",     "Return Rate",      "percent"),
    ("marketing_spend", "Marketing Spend",  "currency"),
    ("roas",            "ROAS",             "ratio"),
    ("cac_proxy",       "CAC Proxy",        "currency"),
]

ALERT_THRESHOLDS = {
    kpi["name"]: kpi["alert_threshold"]
    for kpi in CONFIG["kpis"]["primary"]
}


def aggregate_period(df: pd.DataFrame) -> pd.Series:
    """Aggregate a filtered dataframe into a single-period summary."""
    if df.empty:
        return pd.Series(dtype=float)

    total_traffic = df["traffic"].sum()
    total_orders = df["orders"].sum()
    total_gross_revenue = df["gross_revenue"].sum()
    total_marketing_spend = df["marketing_spend"].sum()
    total_refunds = df["refunds"].sum()
    total_net_revenue = df["net_revenue"].sum()
    total_gross_margin = df["gross_margin"].sum()

    conversion_rate = total_orders / total_traffic if total_traffic > 0 else 0
    avg_order_value = total_gross_revenue / total_orders if total_orders > 0 else 0
    return_rate = total_refunds / total_gross_revenue if total_gross_revenue > 0 else 0
    margin_pct = total_gross_margin / total_net_revenue if total_net_revenue > 0 else 0
    roas = total_gross_revenue / total_marketing_spend if total_marketing_spend > 0 else 0
    cac_proxy = total_marketing_spend / total_orders if total_orders > 0 else 0

    return pd.Series({
        "traffic": total_traffic,
        "orders": total_orders,
        "gross_revenue": total_gross_revenue,
        "marketing_spend": total_marketing_spend,
        "refunds": total_refunds,
        "net_revenue": total_net_revenue,
        "gross_margin": total_gross_margin,
        "conversion_rate": conversion_rate,
        "avg_order_value": avg_order_value,
        "return_rate": return_rate,
        "margin_pct": margin_pct,
        "roas": roas,
        "cac_proxy": cac_proxy,
    })


def compute_kpi_comparison(
    current_period: pd.DataFrame,
    previous_period: pd.DataFrame,
) -> list[dict]:
    """
    Compare current vs previous period for each KPI.
    Returns a list of dicts with: name, label, format, current, previous,
    pct_change, status (ok / alert / warning).
    """
    current_agg = aggregate_period(current_period)
    previous_agg = aggregate_period(previous_period)

    results = []
    for name, label, fmt in DISPLAY_KPIS:
        current_val = current_agg.get(name, 0)
        previous_val = previous_agg.get(name, 0)
        delta = pct_change(current_val, previous_val)

        threshold = ALERT_THRESHOLDS.get(name)
        status = "ok"
        if threshold is not None:
            # For return rate, marketing spend: alert when ABOVE threshold
            if name in ("return_rate", "marketing_spend"):
                if delta >= abs(threshold):
                    status = "alert"
                elif delta >= abs(threshold) * 0.5:
                    status = "warning"
            else:
                # Alert when BELOW threshold (negative)
                if delta <= threshold:
                    status = "alert"
                elif delta <= threshold * 0.5:
                    status = "warning"

        results.append({
            "name": name,
            "label": label,
            "format": fmt,
            "current": current_val,
            "previous": previous_val,
            "pct_change": delta,
            "status": status,
        })

    return results


def get_weekly_trend(df: pd.DataFrame, kpi: str) -> pd.DataFrame:
    """Return weekly aggregated trend for a given KPI."""
    if kpi in ("conversion_rate", "return_rate", "margin_pct", "roas"):
        # Rate metrics: weighted average
        grouped = df.groupby("date").apply(
            lambda g: aggregate_period(g)[kpi]
        ).reset_index()
    else:
        grouped = df.groupby("date")[kpi].sum().reset_index()

    grouped.columns = ["date", kpi]
    grouped = grouped.sort_values("date")
    return grouped


def get_top_alerts(kpi_comparison: list[dict]) -> list[dict]:
    """Return only KPIs with alert or warning status, sorted by severity."""
    alerts = [k for k in kpi_comparison if k["status"] in ("alert", "warning")]
    alerts.sort(key=lambda x: (x["status"] == "alert", abs(x["pct_change"])), reverse=True)
    return alerts

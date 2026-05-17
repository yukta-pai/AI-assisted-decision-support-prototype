"""
anomaly_detection.py
Detects unusual KPI movements using rolling statistics and z-score logic.
Designed to surface meaningful business signals, not just noise.
"""

import pandas as pd
import numpy as np
from src.kpi_engine import get_weekly_trend
from src.utils import load_config

CONFIG = load_config()
ROLLING_WINDOW = CONFIG["anomaly"]["rolling_window"]
ZSCORE_THRESHOLD = CONFIG["anomaly"]["zscore_threshold"]

MONITORED_KPIS = [
    "gross_revenue", "traffic", "conversion_rate",
    "gross_margin", "return_rate", "marketing_spend",
]


def compute_zscore_anomalies(
    df: pd.DataFrame,
    kpi: str,
    window: int = ROLLING_WINDOW,
) -> pd.DataFrame:
    """
    For a given KPI trend, compute z-scores using a rolling window.
    Returns rows where the absolute z-score exceeds the threshold.
    """
    trend = get_weekly_trend(df, kpi)
    if trend.empty or len(trend) < window + 1:
        return pd.DataFrame()

    trend = trend.sort_values("date").copy()
    trend["rolling_mean"] = trend[kpi].rolling(window=window, min_periods=2).mean()
    trend["rolling_std"] = trend[kpi].rolling(window=window, min_periods=2).std()
    trend["zscore"] = (trend[kpi] - trend["rolling_mean"]) / (trend["rolling_std"] + 1e-9)

    anomalies = trend[trend["zscore"].abs() >= ZSCORE_THRESHOLD].copy()
    anomalies["kpi"] = kpi
    anomalies["direction"] = anomalies["zscore"].apply(
        lambda z: "spike" if z > 0 else "drop"
    )
    return anomalies[["date", "kpi", kpi, "rolling_mean", "zscore", "direction"]]


def detect_all_anomalies(df: pd.DataFrame) -> list[dict]:
    """
    Run anomaly detection across all monitored KPIs.
    Returns a list of anomaly records for the UI to display.
    """
    all_anomalies = []

    for kpi in MONITORED_KPIS:
        result = compute_zscore_anomalies(df, kpi)
        if result.empty:
            continue
        for _, row in result.iterrows():
            all_anomalies.append({
                "date": row["date"],
                "kpi": kpi,
                "value": row[kpi],
                "expected": row["rolling_mean"],
                "zscore": round(row["zscore"], 2),
                "direction": row["direction"],
                "severity": "high" if abs(row["zscore"]) >= 3.0 else "medium",
            })

    # Sort by date descending, then by abs z-score
    all_anomalies.sort(
        key=lambda x: (x["date"], -abs(x["zscore"])), reverse=True
    )
    return all_anomalies

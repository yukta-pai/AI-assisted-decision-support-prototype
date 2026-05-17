"""
utils.py
Shared utility functions used across modules.
"""

import yaml
import pandas as pd
import numpy as np
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def fmt_currency(value: float, decimals: int = 0) -> str:
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif abs(value) >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:,.{decimals}f}"


def fmt_percent(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def fmt_number(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.1f}K"
    return f"{value:,.0f}"


def fmt_delta(value: float, format_type: str = "percent") -> str:
    sign = "+" if value > 0 else ""
    if format_type == "currency":
        return f"{sign}{fmt_currency(value)}"
    return f"{sign}{value*100:.1f}%"


def pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / abs(previous)


def load_data(path: str = None) -> pd.DataFrame:
    if path is None:
        path = Path(__file__).parent.parent / "data" / "synthetic_kpi_data.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    return df


def filter_data(
    df: pd.DataFrame,
    regions: list = None,
    categories: list = None,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    if regions:
        df = df[df["region"].isin(regions)]
    if categories:
        df = df[df["category"].isin(categories)]
    if start_date:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["date"] <= pd.Timestamp(end_date)]
    return df

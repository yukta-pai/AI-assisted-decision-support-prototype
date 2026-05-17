"""
charts.py
Plotly chart builders for the Streamlit UI.
All charts share a coherent visual style: dark background, amber/slate palette.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Visual theme ────────────────────────────────────────────────────────────
THEME = dict(
    bg="#0F1117",
    surface="#1A1D27",
    border="#2A2D3E",
    text="#E8E9EE",
    text_muted="#8B8FA8",
    accent="#F59E0B",       # amber
    accent_soft="#FCD34D",  # light amber
    green="#10B981",
    red="#EF4444",
    blue="#3B82F6",
    purple="#8B5CF6",
)

LAYOUT_BASE = dict(
    paper_bgcolor=THEME["bg"],
    plot_bgcolor=THEME["surface"],
    font=dict(family="'IBM Plex Mono', monospace", color=THEME["text"], size=12),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(
        gridcolor=THEME["border"],
        linecolor=THEME["border"],
        tickfont=dict(color=THEME["text_muted"]),
    ),
    yaxis=dict(
        gridcolor=THEME["border"],
        linecolor=THEME["border"],
        tickfont=dict(color=THEME["text_muted"]),
    ),
)


def _apply_layout(fig, **kwargs):
    fig.update_layout(**LAYOUT_BASE, **kwargs)
    return fig


# ── KPI Trend Line ───────────────────────────────────────────────────────────
def trend_line(
    trend_df: pd.DataFrame,
    kpi: str,
    label: str,
    fmt: str = "currency",
    comparison_df: pd.DataFrame = None,
) -> go.Figure:
    """Single KPI time series with optional comparison overlay."""
    fig = go.Figure()

    # Current period
    fig.add_trace(go.Scatter(
        x=trend_df["date"],
        y=trend_df[kpi],
        mode="lines",
        name="Current",
        line=dict(color=THEME["accent"], width=2.5),
        fill="tozeroy",
        fillcolor="rgba(245,158,11,0.08)",
        hovertemplate=f"<b>%{{x|%b %d}}</b><br>{label}: %{{y:,.0f}}<extra></extra>",
    ))

    if comparison_df is not None and not comparison_df.empty:
        fig.add_trace(go.Scatter(
            x=comparison_df["date"],
            y=comparison_df[kpi],
            mode="lines",
            name="Prior period",
            line=dict(color=THEME["text_muted"], width=1.5, dash="dot"),
            hovertemplate=f"<b>Prior %{{x|%b %d}}</b><br>{label}: %{{y:,.0f}}<extra></extra>",
        ))

    _apply_layout(fig, title=label, height=260, showlegend=comparison_df is not None)
    return fig


# ── Driver Bar Chart ─────────────────────────────────────────────────────────
def driver_bar(drivers: list[dict]) -> go.Figure:
    """Horizontal bar chart showing driver relevance scores."""
    if not drivers:
        return go.Figure()

    labels = [d["label"] for d in drivers]
    scores = [d["relevance"] for d in drivers]
    colors = [
        THEME["red"] if d["impact_direction"] == "negative" else THEME["green"]
        for d in drivers
    ]

    fig = go.Figure(go.Bar(
        x=scores,
        y=labels,
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{s:.0%}" for s in scores],
        textposition="outside",
        textfont=dict(color=THEME["text"], size=11),
        hovertemplate="<b>%{y}</b><br>Relevance: %{x:.1%}<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor=THEME["bg"],
        plot_bgcolor=THEME["surface"],
        font=dict(family="'IBM Plex Mono', monospace", color=THEME["text"], size=12),
        margin=dict(l=40, r=20, t=40, b=40),
        title="Driver Relevance (contribution to KPI movement)",
        xaxis=dict(
            tickformat=".0%",
            range=[0, max(scores) * 1.35] if scores else [0, 1],
            gridcolor=THEME["border"],
            linecolor=THEME["border"],
            tickfont=dict(color=THEME["text_muted"]),
        ),
        yaxis=dict(
            categoryorder="total ascending",
            gridcolor=THEME["border"],
            linecolor=THEME["border"],
            tickfont=dict(color=THEME["text"]),
        ),
        height=280,
        showlegend=False,
    )
    return fig


# ── Scenario Waterfall ───────────────────────────────────────────────────────
def scenario_waterfall(scenario: dict) -> go.Figure:
    """Waterfall chart: baseline → projected gross revenue breakdown."""
    if not scenario:
        return go.Figure()

    base_rev = scenario["baseline"].get("gross_revenue", 0)
    proj_rev = scenario["projected"].get("gross_revenue", 0)
    delta = proj_rev - base_rev

    assumptions = scenario.get("assumptions", {})
    steps = []

    label_map = {
        "traffic_change": "Traffic",
        "conversion_change": "Conversion",
        "aov_change": "Avg Order Value",
        "return_rate_change": "Return Rate",
        "marketing_change": "Marketing",
        "margin_change": "Margin %",
    }

    # Distribute the total delta across active levers proportionally
    active = {k: v for k, v in assumptions.items() if v != 0.0}
    total_weight = sum(abs(v) for v in active.values()) or 1

    for key, val in active.items():
        share = (abs(val) / total_weight) * delta
        if "return" in key or "marketing" in key:
            # Negative lever: increasing these is bad
            share = -share * np.sign(val)
        steps.append((label_map.get(key, key), share))

    x_labels = ["Baseline"] + [s[0] for s in steps] + ["Projected"]
    measures = ["absolute"] + ["relative"] * len(steps) + ["total"]
    y_values = [base_rev] + [s[1] for s in steps] + [proj_rev]

    colors = [THEME["text_muted"]]
    for _, val in steps:
        colors.append(THEME["green"] if val >= 0 else THEME["red"])
    colors.append(THEME["accent"])

    fig = go.Figure(go.Waterfall(
        name="Revenue",
        orientation="v",
        measure=measures,
        x=x_labels,
        y=y_values,
        connector=dict(line=dict(color=THEME["border"], width=1)),
        increasing=dict(marker=dict(color=THEME["green"])),
        decreasing=dict(marker=dict(color=THEME["red"])),
        totals=dict(marker=dict(color=THEME["accent"])),
        texttemplate="%{y:$,.0f}",
        textposition="outside",
        textfont=dict(color=THEME["text"], size=10),
    ))

    _apply_layout(
        fig,
        title="Revenue Impact: Baseline vs. Scenario",
        yaxis=dict(
            tickprefix="$",
            tickformat=",.0f",
            gridcolor=THEME["border"],
            linecolor=THEME["border"],
            tickfont=dict(color=THEME["text_muted"]),
        ),
        height=350,
        showlegend=False,
    )
    return fig


# ── KPI Sparkline Grid ────────────────────────────────────────────────────────
def kpi_sparkline(trend_df: pd.DataFrame, kpi: str) -> go.Figure:
    """Tiny inline sparkline for a KPI card."""
    fig = go.Figure(go.Scatter(
        x=trend_df["date"],
        y=trend_df[kpi],
        mode="lines",
        line=dict(color=THEME["accent"], width=2),
        fill="tozeroy",
        fillcolor="rgba(245,158,11,0.10)",
        hoverinfo="skip",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=60,
        showlegend=False,
    )
    return fig


# ── Multi-KPI Comparison ──────────────────────────────────────────────────────
def multi_kpi_trend(df: pd.DataFrame, kpis: list[str]) -> go.Figure:
    """Multi-line chart for comparing several KPIs over time (normalised)."""
    colors = [THEME["accent"], THEME["green"], THEME["blue"], THEME["purple"], THEME["red"]]
    fig = go.Figure()

    for i, kpi in enumerate(kpis):
        if kpi not in df.columns:
            continue
        col = df[kpi]
        normed = (col / col.iloc[0]) * 100 if col.iloc[0] != 0 else col
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=normed,
            mode="lines",
            name=kpi.replace("_", " ").title(),
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate=f"<b>%{{x|%b %d}}</b><br>{kpi}: %{{y:.1f}} (indexed)<extra></extra>",
        ))

    _apply_layout(
        fig,
        title="KPI Trends (Indexed to 100)",
        height=320,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(color=THEME["text_muted"], size=10),
        ),
    )
    return fig
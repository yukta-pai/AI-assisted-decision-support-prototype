"""
ui.py
Streamlit UI component builders.
Each function renders a distinct section of the dashboard.
"""

import streamlit as st
import pandas as pd
import numpy as np
from src.utils import fmt_currency, fmt_percent, fmt_number, fmt_delta
from app.charts import (
    trend_line, driver_bar, scenario_waterfall,
    kpi_sparkline, multi_kpi_trend
)

STATUS_COLORS = {
    "alert":   "#EF4444",
    "warning": "#F59E0B",
    "ok":      "#10B981",
}

STATUS_ICONS = {
    "alert":   "🔴",
    "warning": "🟡",
    "ok":      "🟢",
}

PRIORITY_COLORS = {
    "Critical":       "#EF4444",
    "High priority":  "#F59E0B",
    "Medium priority": "#3B82F6",
    "Low priority":   "#8B8FA8",
}


def _fmt_value(value: float, fmt: str) -> str:
    if fmt == "currency":
        return fmt_currency(value)
    elif fmt == "percent":
        return fmt_percent(value)
    elif fmt == "ratio":
        return f"{value:.2f}x"
    return fmt_number(value)


# ── Section: KPI Cards ────────────────────────────────────────────────────────
def render_kpi_cards(kpi_comparison: list[dict], trend_data: dict):
    """Render a grid of KPI metric cards with sparklines."""
    primary_kpis = [
        k for k in kpi_comparison
        if k["name"] in ("gross_revenue", "net_revenue", "traffic",
                         "conversion_rate", "gross_margin", "return_rate")
    ]

    cols = st.columns(3)
    for i, kpi in enumerate(primary_kpis):
        col = cols[i % 3]
        with col:
            status = kpi["status"]
            color = STATUS_COLORS[status]
            delta = kpi["pct_change"]
            delta_sign = "+" if delta > 0 else ""
            delta_color = "#10B981" if delta > 0 else "#EF4444"
            # Return rate: inverse logic
            if kpi["name"] == "return_rate":
                delta_color = "#EF4444" if delta > 0 else "#10B981"

            current_fmt = _fmt_value(kpi["current"], kpi["format"])
            previous_fmt = _fmt_value(kpi["previous"], kpi["format"])

            st.markdown(f"""
<div style="
    background: #1A1D27;
    border: 1px solid {color if status != 'ok' else '#2A2D3E'};
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 12px;
    position: relative;
">
    <div style="
        font-size: 11px;
        color: #8B8FA8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-family: 'IBM Plex Mono', monospace;
        margin-bottom: 4px;
    ">{STATUS_ICONS[status]} {kpi['label']}</div>
    <div style="
        font-size: 28px;
        font-weight: 700;
        color: #E8E9EE;
        font-family: 'IBM Plex Mono', monospace;
        line-height: 1.1;
    ">{current_fmt}</div>
    <div style="
        font-size: 12px;
        color: {delta_color};
        margin-top: 4px;
        font-family: 'IBM Plex Mono', monospace;
    ">{delta_sign}{delta*100:.1f}% vs prior &nbsp;|&nbsp; <span style="color:#8B8FA8">prev: {previous_fmt}</span></div>
</div>
""", unsafe_allow_html=True)


# ── Section: Alert Panel ──────────────────────────────────────────────────────
def render_alert_panel(kpi_comparison: list[dict]):
    """Show only the flagged KPIs with brief context."""
    alerts = [k for k in kpi_comparison if k["status"] in ("alert", "warning")]
    if not alerts:
        st.markdown("""
<div style="background:#1A1D27;border:1px solid #2A2D3E;border-radius:8px;padding:16px;">
    <span style="color:#10B981;font-family:monospace;">✓ No KPI alerts in the selected period.</span>
</div>""", unsafe_allow_html=True)
        return

    for a in alerts:
        color = STATUS_COLORS[a["status"]]
        delta_str = f"{'+' if a['pct_change'] > 0 else ''}{a['pct_change']*100:.1f}%"
        st.markdown(f"""
<div style="
    background:#1A1D27;
    border-left: 4px solid {color};
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 8px;
">
    <span style="font-weight:700;color:#E8E9EE;font-family:monospace;">{a['label']}</span>
    <span style="color:{color};margin-left:12px;font-family:monospace;">{delta_str}</span>
    <span style="color:#8B8FA8;font-size:11px;margin-left:8px;font-family:monospace;">
        vs prior period · status: <strong style="color:{color}">{a['status'].upper()}</strong>
    </span>
</div>""", unsafe_allow_html=True)


# ── Section: Driver Analysis ──────────────────────────────────────────────────
def render_driver_analysis(drivers: list[dict]):
    """Render the driver attribution panel with bar chart and detail table."""
    if not drivers:
        st.info("No driver data available. Ensure a prior period exists for comparison.")
        return

    st.plotly_chart(driver_bar(drivers), use_container_width=True)

    # Detail table
    rows = []
    for d in drivers:
        direction = "↓ Negative" if d["impact_direction"] == "negative" else "↑ Positive"
        rows.append({
            "Driver": d["label"],
            "Change vs prior": f"{d['pct_change']*100:+.1f}%",
            "Relevance": f"{d['relevance']:.0%}",
            "Impact direction": direction,
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


# ── Section: Scenario Simulation ─────────────────────────────────────────────
def render_scenario_results(scenario: dict):
    """Render the waterfall chart + comparison table from scenario output."""
    if not scenario:
        return

    st.plotly_chart(scenario_waterfall(scenario), use_container_width=True)

    base = scenario["baseline"]
    proj = scenario["projected"]
    d_pct = scenario["delta_pct"]

    display = [
        ("gross_revenue",   "Gross Revenue",   "currency"),
        ("net_revenue",     "Net Revenue",      "currency"),
        ("orders",          "Orders",           "number"),
        ("gross_margin",    "Gross Margin",     "currency"),
        ("conversion_rate", "Conversion Rate",  "percent"),
        ("roas",            "ROAS",             "ratio"),
        ("return_rate",     "Return Rate",      "percent"),
        ("marketing_spend", "Marketing Spend",  "currency"),
    ]

    rows = []
    for col, label, fmt in display:
        pct = d_pct.get(col, 0)
        arrow = "▲" if pct > 0 else "▼"
        color_tag = "green" if pct > 0 else "red"
        if col == "return_rate":
            color_tag = "red" if pct > 0 else "green"
        rows.append({
            "KPI": label,
            "Baseline": _fmt_value(base.get(col, 0), fmt),
            "Projected": _fmt_value(proj.get(col, 0), fmt),
            "Δ %": f"{pct*100:+.1f}%",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Section: Recommendations ──────────────────────────────────────────────────
def render_recommendations(recommendations: list[dict]):
    """Render prioritised recommendation cards."""
    if not recommendations:
        st.markdown("""
<div style="background:#1A1D27;border:1px solid #2A2D3E;border-radius:8px;padding:16px;">
    <span style="color:#8B8FA8;font-family:monospace;">No recommendations triggered — KPI performance is within expected ranges.</span>
</div>""", unsafe_allow_html=True)
        return

    for rec in recommendations:
        p_color = PRIORITY_COLORS.get(rec["priority_tag"], "#8B8FA8")
        actions_html = "".join(
            f'<li style="color:#B0B4CC;margin-bottom:3px;">{a}</li>'
            for a in rec["actions"]
        )

        st.markdown(f"""
<div style="
    background:#1A1D27;
    border:1px solid #2A2D3E;
    border-radius:10px;
    padding:18px 20px;
    margin-bottom:14px;
">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
            <span style="
                background:{p_color}22;
                color:{p_color};
                font-size:10px;
                font-family:monospace;
                padding:2px 8px;
                border-radius:4px;
                border:1px solid {p_color}44;
                text-transform:uppercase;
                letter-spacing:0.06em;
            ">{rec['priority_tag']}</span>
            <span style="
                background:#2A2D3E;
                color:#8B8FA8;
                font-size:10px;
                font-family:monospace;
                padding:2px 8px;
                border-radius:4px;
                margin-left:6px;
            ">{rec['category']}</span>
        </div>
        <span style="color:#8B8FA8;font-size:11px;font-family:monospace;">
            Confidence: {rec['confidence']:.0%} · Effort: {rec['effort']}
        </span>
    </div>
    <div style="
        font-size:16px;
        font-weight:700;
        color:#E8E9EE;
        margin:10px 0 6px 0;
        font-family:monospace;
    ">{rec['title']}</div>
    <div style="color:#8B8FA8;font-size:13px;margin-bottom:10px;line-height:1.5;">
        {rec['rationale']}
    </div>
    <div style="color:#F59E0B;font-size:11px;font-family:monospace;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.06em;">
        Suggested actions
    </div>
    <ul style="margin:0;padding-left:20px;font-size:13px;line-height:1.7;">
        {actions_html}
    </ul>
</div>
""", unsafe_allow_html=True)


# ── Section: Executive Summary ────────────────────────────────────────────────
def render_executive_summary(summary_text: str, is_loading: bool = False):
    if is_loading:
        st.markdown("""
<div style="background:#1A1D27;border:1px solid #F59E0B44;border-radius:10px;padding:20px 24px;">
    <span style="color:#8B8FA8;font-family:monospace;">Generating executive summary…</span>
</div>""", unsafe_allow_html=True)
        return

    st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #1A1D27 0%, #1F2235 100%);
    border: 1px solid #F59E0B44;
    border-left: 4px solid #F59E0B;
    border-radius: 10px;
    padding: 24px 28px;
    margin-top: 8px;
">
    <div style="
        font-size: 10px;
        color: #F59E0B;
        font-family: monospace;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 14px;
    ">AI-Generated Executive Summary</div>
    <div style="
        color: #C8CAD8;
        font-size: 14px;
        line-height: 1.8;
        font-family: 'Georgia', serif;
    ">{summary_text.replace(chr(10), '<br>')}</div>
    <div style="
        color: #4B4F6B;
        font-size: 10px;
        font-family: monospace;
        margin-top: 16px;
        border-top: 1px solid #2A2D3E;
        padding-top: 10px;
    ">Generated from structured decision engine outputs. Numbers are pre-computed — not estimated by the model.</div>
</div>
""", unsafe_allow_html=True)

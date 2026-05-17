"""
main.py
Entry point for the AI Decision Support Prototype.
Assembles filters, runs the decision engine layers, and renders the UI.
"""

import os
import sys
import pandas as pd
import streamlit as st

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import load_data, filter_data, load_config, fmt_currency, fmt_percent
from src.kpi_engine import compute_kpi_comparison, get_weekly_trend, get_top_alerts, aggregate_period
from src.driver_analysis import compute_driver_scores
from src.scenario_simulator import run_scenario
from src.recommendation_engine import generate_recommendations
from src.summary_generator import generate_summary
from app.ui import (
    render_kpi_cards, render_alert_panel, render_driver_analysis,
    render_scenario_results, render_recommendations, render_executive_summary,
)
from app.charts import trend_line, multi_kpi_trend

CONFIG = load_config()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Decision Support",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    background-color: #0F1117;
    color: #E8E9EE;
    font-family: 'IBM Plex Sans', sans-serif;
}
.stSidebar {
    background-color: #13151F !important;
    border-right: 1px solid #2A2D3E !important;
}
.block-container { padding: 1.5rem 2rem !important; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; color: #E8E9EE !important; }
.stButton > button {
    background: #F59E0B !important;
    color: #0F1117 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 6px !important;
}
.stSelectbox label, .stMultiSelect label, .stSlider label, .stDateInput label {
    color: #8B8FA8 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}
.section-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: #8B8FA8;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    border-bottom: 1px solid #2A2D3E;
    padding-bottom: 8px;
    margin: 28px 0 16px 0;
}
.section-header span {
    color: #F59E0B;
    margin-right: 8px;
}
div[data-testid="stHorizontalBlock"] { gap: 1rem; }
</style>
""", unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_cached_data():
    return load_data()

df_all = load_cached_data()
all_dates = sorted(df_all["date"].unique())
all_regions = sorted(df_all["region"].unique())
all_categories = sorted(df_all["category"].unique())


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="padding: 8px 0 20px 0;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:#F59E0B;">◈ Decision Support</div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#4B4F6B;margin-top:2px;">
        AI-ASSISTED KPI MANAGEMENT · v2.0
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="section-header"><span>◎</span>Filters</div>', unsafe_allow_html=True)

    selected_regions = st.multiselect(
        "Region",
        options=all_regions,
        default=all_regions,
        key="regions",
    )

    selected_categories = st.multiselect(
        "Category",
        options=all_categories,
        default=all_categories,
        key="categories",
    )

    st.markdown('<div class="section-header"><span>◎</span>Time Window</div>', unsafe_allow_html=True)

    # Default: last 8 weeks vs prior 8 weeks
    max_date = pd.Timestamp(all_dates[-1])
    default_end = max_date
    default_start = max_date - pd.Timedelta(weeks=8)
    default_prior_start = default_start - pd.Timedelta(weeks=8)
    default_prior_end = default_start - pd.Timedelta(days=1)

    current_start = st.date_input("Current period start", value=default_start.date())
    current_end = st.date_input("Current period end", value=default_end.date())

    compare_enabled = st.toggle("Compare with prior period", value=True)
    if compare_enabled:
        prior_start = st.date_input("Prior period start", value=default_prior_start.date())
        prior_end = st.date_input("Prior period end", value=default_prior_end.date())

    st.markdown('<div class="section-header"><span>◎</span>AI Summary</div>', unsafe_allow_html=True)
    api_key = st.text_input(
        "Anthropic API Key (optional)",
        type="password",
        placeholder="sk-ant-...",
        help="Leave blank to use the rule-based fallback summary.",
    )
    target_kpi = st.selectbox(
        "Primary KPI for driver analysis",
        options=["gross_revenue", "gross_margin", "net_revenue"],
        format_func=lambda x: x.replace("_", " ").title(),
    )


# ── Data slicing ──────────────────────────────────────────────────────────────
df_current = filter_data(
    df_all,
    regions=selected_regions,
    categories=selected_categories,
    start_date=current_start,
    end_date=current_end,
)

df_prior = pd.DataFrame()
if compare_enabled:
    df_prior = filter_data(
        df_all,
        regions=selected_regions,
        categories=selected_categories,
        start_date=prior_start,
        end_date=prior_end,
    )


# ── Decision engine ───────────────────────────────────────────────────────────
kpi_comparison = compute_kpi_comparison(df_current, df_prior)
drivers = compute_driver_scores(df_current, df_prior, target_kpi=target_kpi)
alerts = get_top_alerts(kpi_comparison)
recommendations = generate_recommendations(kpi_comparison)


# ── Page header ───────────────────────────────────────────────────────────────
period_label = f"{current_start} → {current_end}"
st.markdown(f"""
<div style="margin-bottom:24px;">
    <h1 style="font-size:26px;margin-bottom:2px;">AI Decision Support</h1>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#8B8FA8;">
        Period: <strong style="color:#F59E0B;">{period_label}</strong>
        &nbsp;·&nbsp; {len(selected_regions)} region(s) &nbsp;·&nbsp; {len(selected_categories)} category(s)
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: KPI Health
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header"><span>01</span>KPI Health Overview</div>', unsafe_allow_html=True)
render_kpi_cards(kpi_comparison, trend_data={})


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: What Changed
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header"><span>02</span>What Changed — Issue Detection</div>', unsafe_allow_html=True)

col_alert, col_trend = st.columns([1, 2])
with col_alert:
    render_alert_panel(kpi_comparison)

with col_trend:
    # Show primary KPI trend
    primary_trend = get_weekly_trend(df_all, "gross_revenue")
    prior_trend = None
    if compare_enabled and not df_prior.empty:
        prior_trend = get_weekly_trend(df_prior, "gross_revenue")

    st.plotly_chart(
        trend_line(
            get_weekly_trend(df_current, "gross_revenue"),
            "gross_revenue",
            "Gross Revenue",
            fmt="currency",
        ),
        use_container_width=True,
    )

# Multi-KPI indexed view
with st.expander("View normalised KPI trends (indexed to 100)", expanded=False):
    trend_df_agg = df_current.groupby("date").agg({
        "gross_revenue": "sum",
        "traffic": "sum",
        "orders": "sum",
    }).reset_index()
    trend_df_agg["conversion_rate"] = trend_df_agg["orders"] / trend_df_agg["traffic"]

    st.plotly_chart(
        multi_kpi_trend(trend_df_agg, ["gross_revenue", "traffic", "conversion_rate"]),
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Why It Happened — Driver Attribution
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(
    f'<div class="section-header"><span>03</span>Why It Happened — Driver Attribution for {target_kpi.replace("_"," ").title()}</div>',
    unsafe_allow_html=True,
)

if not compare_enabled or df_prior.empty:
    st.info("Enable prior period comparison to run driver attribution.")
else:
    render_driver_analysis(drivers)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: What If — Scenario Simulation
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header"><span>04</span>What If — Scenario Simulation</div>', unsafe_allow_html=True)

with st.container():
    st.markdown(
        "<p style='color:#8B8FA8;font-size:13px;margin-bottom:16px;'>"
        "Adjust the levers below to project the revenue and margin impact of business changes. "
        "All outputs are formula-derived from the current period baseline.</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        traffic_chg = st.slider("Traffic change (%)", -30, 30, 0, step=1) / 100
        aov_chg = st.slider("Avg order value change (%)", -20, 20, 0, step=1) / 100
    with col2:
        conv_chg = st.slider("Conversion change (pp)", -2.0, 2.0, 0.0, step=0.1) / 100
        return_chg = st.slider("Return rate change (pp)", -5.0, 5.0, 0.0, step=0.1) / 100
    with col3:
        spend_chg = st.slider("Marketing spend change (%)", -30, 30, 0, step=1) / 100
        margin_chg = st.slider("Margin % change (pp)", -5.0, 5.0, 0.0, step=0.1) / 100

    has_changes = any([traffic_chg, conv_chg, aov_chg, spend_chg, return_chg, margin_chg])

    if has_changes:
        scenario = run_scenario(
            baseline_df=df_current,
            traffic_change=traffic_chg,
            conversion_change=conv_chg,
            aov_change=aov_chg,
            marketing_change=spend_chg,
            return_rate_change=return_chg,
            margin_change=margin_chg,
        )
        render_scenario_results(scenario)
    else:
        st.markdown("""
<div style="background:#1A1D27;border:1px solid #2A2D3E;border-radius:8px;padding:16px;text-align:center;">
    <span style="color:#4B4F6B;font-family:monospace;font-size:13px;">
        Adjust at least one slider to run a scenario simulation.
    </span>
</div>""", unsafe_allow_html=True)
        scenario = {}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: What To Do — Recommendations + AI Summary
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header"><span>05</span>What To Do — Prioritised Recommendations</div>', unsafe_allow_html=True)

render_recommendations(recommendations)

st.markdown('<div class="section-header"><span>06</span>Executive Summary</div>', unsafe_allow_html=True)

if st.button("Generate Executive Summary", type="primary"):
    with st.spinner("Generating summary…"):
        summary = generate_summary(
            kpi_comparison=kpi_comparison,
            drivers=drivers,
            scenario=scenario,
            recommendations=recommendations,
            period_label=period_label,
            api_key=api_key or None,
        )
    st.session_state["summary"] = summary

if "summary" in st.session_state:
    render_executive_summary(st.session_state["summary"])
else:
    st.markdown("""
<div style="background:#1A1D27;border:1px solid #2A2D3E;border-radius:8px;padding:16px;text-align:center;">
    <span style="color:#4B4F6B;font-family:monospace;font-size:13px;">
        Click "Generate Executive Summary" to produce a management-ready narrative.
    </span>
</div>""", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    margin-top:48px;
    padding-top:20px;
    border-top:1px solid #2A2D3E;
    font-family:monospace;
    font-size:10px;
    color:#4B4F6B;
    text-align:center;
">
    AI Decision Support Prototype · v2.0 · Synthetic data — for demonstration purposes only<br>
    KPI calculations are formula-derived. AI summary is grounded in structured engine outputs.
</div>
""", unsafe_allow_html=True)

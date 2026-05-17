"""
recommendation_engine.py
Maps detected KPI issues and driver patterns to prioritized business actions.
Each recommendation is structured, not free-text from an LLM.
"""

from src.kpi_engine import compute_kpi_comparison


# Action library: keyed by issue pattern
ACTION_LIBRARY = [
    {
        "id": "traffic_acquisition",
        "trigger_kpi": "traffic",
        "trigger_direction": "negative",
        "trigger_threshold": -0.08,
        "title": "Review acquisition channel efficiency",
        "rationale": "Traffic accounts for the largest share of revenue exposure. "
                     "A sustained drop suggests either budget reduction, auction "
                     "competition, or channel-level quality issues.",
        "actions": [
            "Audit paid channel performance by campaign and audience segment",
            "Review keyword-level quality scores and bid strategies",
            "Check organic traffic via Search Console for ranking losses",
            "Assess channel mix — over-reliance on a single source increases fragility",
        ],
        "impact": "high",
        "effort": "medium",
        "urgency": "high",
        "confidence": 0.82,
        "category": "Acquisition",
    },
    {
        "id": "conversion_funnel",
        "trigger_kpi": "conversion_rate",
        "trigger_direction": "negative",
        "trigger_threshold": -0.05,
        "title": "Diagnose conversion funnel drop-off",
        "rationale": "Conversion rate decline can signal landing page "
                     "friction, pricing perception issues, or a mismatch "
                     "between acquisition traffic quality and intent.",
        "actions": [
            "Run session recording analysis on key landing pages",
            "Review checkout abandonment funnel stage by stage",
            "A/B test pricing display, trust signals, and CTA placement",
            "Segment conversion by device type and traffic source",
        ],
        "impact": "high",
        "effort": "medium",
        "urgency": "high",
        "confidence": 0.79,
        "category": "Conversion",
    },
    {
        "id": "aov_uplift",
        "trigger_kpi": "avg_order_value",
        "trigger_direction": "negative",
        "trigger_threshold": -0.05,
        "title": "Investigate average order value erosion",
        "rationale": "AOV decline may reflect category mix shift, "
                     "promotional discounting, or a loss of high-value customers.",
        "actions": [
            "Analyse order mix — are lower-priced SKUs gaining share?",
            "Review bundle and upsell recommendation performance",
            "Check if promo/discount usage has increased disproportionately",
            "Identify top revenue SKUs and assess their trend separately",
        ],
        "impact": "medium",
        "effort": "low",
        "urgency": "medium",
        "confidence": 0.71,
        "category": "Pricing & AOV",
    },
    {
        "id": "returns_quality",
        "trigger_kpi": "return_rate",
        "trigger_direction": "positive",
        "trigger_threshold": 0.03,
        "title": "Investigate returns spike — potential quality or expectation issue",
        "rationale": "An elevated return rate above baseline is a leading "
                     "indicator of customer dissatisfaction, product quality "
                     "issues, or misleading product content.",
        "actions": [
            "Analyse returns by SKU, category, and return reason code",
            "Review recent product imagery and descriptions for accuracy",
            "Check NPS and post-purchase survey data for patterns",
            "Assess supplier quality if concentrated in specific products",
        ],
        "impact": "high",
        "effort": "medium",
        "urgency": "high",
        "confidence": 0.85,
        "category": "Retention & Quality",
    },
    {
        "id": "margin_efficiency",
        "trigger_kpi": "gross_margin",
        "trigger_direction": "negative",
        "trigger_threshold": -0.10,
        "title": "Reassess marketing spend efficiency",
        "rationale": "Margin compression despite stable or growing revenue "
                     "typically points to escalating marketing costs "
                     "or unfavourable return rate pressure.",
        "actions": [
            "Calculate contribution margin by channel, not just ROAS",
            "Identify marginal campaigns with ROAS below break-even",
            "Evaluate spend reallocation to higher-margin categories",
            "Review return rate impact on net revenue contribution",
        ],
        "impact": "high",
        "effort": "medium",
        "urgency": "medium",
        "confidence": 0.74,
        "category": "Cost Efficiency",
    },
    {
        "id": "spend_escalation",
        "trigger_kpi": "marketing_spend",
        "trigger_direction": "positive",
        "trigger_threshold": 0.15,
        "title": "Validate marketing spend increase against incremental return",
        "rationale": "A significant spend increase without proportional "
                     "revenue or traffic improvement signals diminishing "
                     "returns or budget allocation errors.",
        "actions": [
            "Run incrementality test on increased budget allocation",
            "Review attribution model — are assisted conversions inflated?",
            "Compare ROAS trend vs. spend trajectory over 8+ weeks",
            "Identify if spend increase was planned (seasonal) or reactive",
        ],
        "impact": "medium",
        "effort": "low",
        "urgency": "medium",
        "confidence": 0.68,
        "category": "Cost Efficiency",
    },
]

PRIORITY_MATRIX = {
    ("high", "high", "high"):   "Critical",
    ("high", "high", "medium"): "High priority",
    ("high", "medium", "high"): "High priority",
    ("high", "low", "high"):    "High priority",
    ("medium", "high", "high"): "High priority",
    ("medium", "medium", "medium"): "Medium priority",
    ("low", "low", "low"):      "Low priority",
}


def compute_priority_tag(impact: str, urgency: str, confidence: float) -> str:
    conf_band = "high" if confidence >= 0.75 else ("medium" if confidence >= 0.60 else "low")
    key = (impact, urgency, conf_band)
    return PRIORITY_MATRIX.get(key, "Medium priority")


def generate_recommendations(
    kpi_comparison: list[dict],
) -> list[dict]:
    """
    Match detected KPI issues to the action library.
    Returns prioritised recommendations.
    """
    triggered = []
    kpi_lookup = {k["name"]: k for k in kpi_comparison}

    for action in ACTION_LIBRARY:
        kpi_name = action["trigger_kpi"]
        kpi_data = kpi_lookup.get(kpi_name)
        if not kpi_data:
            continue

        delta = kpi_data["pct_change"]
        threshold = action["trigger_threshold"]
        direction = action["trigger_direction"]

        matched = False
        if direction == "negative" and delta <= threshold:
            matched = True
        elif direction == "positive" and delta >= threshold:
            matched = True

        if matched:
            rec = dict(action)
            rec["observed_delta"] = delta
            rec["kpi_label"] = kpi_data["label"]
            rec["priority_tag"] = compute_priority_tag(
                action["impact"], action["urgency"], action["confidence"]
            )
            triggered.append(rec)

    # Sort: Critical > High priority > Medium priority, then by confidence
    priority_order = {"Critical": 0, "High priority": 1, "Medium priority": 2, "Low priority": 3}
    triggered.sort(key=lambda x: (priority_order.get(x["priority_tag"], 9), -x["confidence"]))

    return triggered

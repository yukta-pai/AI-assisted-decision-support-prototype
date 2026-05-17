"""
summary_generator.py
Generates a management-style executive summary using the Anthropic API.
The LLM receives structured, pre-computed results — it does NOT compute numbers.
"""

import os
import json
from src.utils import fmt_currency, fmt_percent


def build_prompt(
    kpi_comparison: list[dict],
    drivers: list[dict],
    scenario: dict,
    recommendations: list[dict],
    period_label: str = "the current period",
) -> str:
    """
    Build a structured, grounded prompt from pre-computed outputs.
    The LLM's job is translation into business language — not analysis.
    """

    # KPI snapshot
    alerts = [k for k in kpi_comparison if k["status"] in ("alert", "warning")]
    kpi_lines = []
    for k in alerts[:5]:
        direction = "declined" if k["pct_change"] < 0 else "increased"
        kpi_lines.append(
            f"- {k['label']}: {direction} by {abs(k['pct_change'])*100:.1f}%"
            f" (status: {k['status']})"
        )

    # Drivers
    driver_lines = []
    for d in drivers[:4]:
        direction = "negatively" if d["impact_direction"] == "negative" else "positively"
        driver_lines.append(
            f"- {d['label']}: changed {d['pct_change']*100:.1f}%, "
            f"relevance score {d['relevance']:.0%} ({direction} impacting revenue)"
        )

    # Scenario
    scenario_note = ""
    if scenario:
        proj = scenario.get("projected", {})
        base = scenario.get("baseline", {})
        assumptions = scenario.get("assumptions", {})
        rev_delta = (proj.get("gross_revenue", 0) - base.get("gross_revenue", 0))
        margin_delta = (proj.get("gross_margin", 0) - base.get("gross_margin", 0))
        active = [
            f"{k.replace('_change','').replace('_',' ')}: {v*100:+.1f}{'pp' if 'rate' in k or 'conversion' in k else '%'}"
            for k, v in assumptions.items() if v != 0.0
        ]
        if active:
            scenario_note = (
                f"A scenario was tested with: {', '.join(active)}. "
                f"Projected revenue impact: {fmt_currency(rev_delta)}. "
                f"Projected margin impact: {fmt_currency(margin_delta)}."
            )

    # Top recommendations
    rec_lines = []
    for r in recommendations[:3]:
        rec_lines.append(
            f"- {r['title']} ({r['priority_tag']}, confidence: {r['confidence']:.0%})"
        )

    prompt = f"""You are a senior business performance analyst writing a concise executive summary for a management audience.

You have been provided with structured, pre-computed performance results. Your task is ONLY to translate them into clear, professional management language. Do NOT invent numbers, add speculation, or introduce any data that is not in the inputs below.

=== PERFORMANCE INPUTS ===

KPI STATUS ({period_label}):
{chr(10).join(kpi_lines) if kpi_lines else '- No significant KPI alerts detected.'}

LIKELY DRIVERS OF PERFORMANCE CHANGE:
{chr(10).join(driver_lines) if driver_lines else '- Driver analysis inconclusive.'}

SCENARIO ANALYSIS:
{scenario_note if scenario_note else 'No scenario tested.'}

PRIORITY RECOMMENDATIONS:
{chr(10).join(rec_lines) if rec_lines else '- No recommendations triggered.'}

=== YOUR TASK ===

Write a concise executive summary (3–4 paragraphs, 150–200 words total) that:
1. States clearly what happened to performance and the key KPI changes
2. Explains the most likely reasons based on the driver analysis
3. If a scenario was tested, briefly note what it implies about recovery levers
4. Closes with the 1–2 highest-priority actions management should consider

Tone: factual, measured, business-oriented. Avoid jargon, avoid hedging excessively, avoid bullet points in the output. Write in flowing prose as if for a board or leadership team.

Do NOT say "based on the data provided" or any similar meta-language. Just write the summary directly."""

    return prompt


def generate_summary(
    kpi_comparison: list[dict],
    drivers: list[dict],
    scenario: dict,
    recommendations: list[dict],
    period_label: str = "the current period",
    api_key: str = None,
) -> str:
    """
    Call the Anthropic API to generate the executive summary.
    Falls back to a rule-based summary if API key is not available.
    """
    prompt = build_prompt(kpi_comparison, drivers, scenario, recommendations, period_label)

    try:
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return _fallback_summary(kpi_comparison, drivers, recommendations)

        client = anthropic.Anthropic(api_key=key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    except Exception as e:
        return _fallback_summary(kpi_comparison, drivers, recommendations)


def _fallback_summary(
    kpi_comparison: list[dict],
    drivers: list[dict],
    recommendations: list[dict],
) -> str:
    """
    Rule-based fallback summary when the API is unavailable.
    Guarantees the UI always shows something meaningful.
    """
    alerts = [k for k in kpi_comparison if k["status"] == "alert"]
    warnings = [k for k in kpi_comparison if k["status"] == "warning"]

    if not alerts and not warnings:
        return (
            "Performance across the selected period is broadly within expected ranges. "
            "No KPI alerts have been triggered. Continue monitoring key metrics, "
            "with particular attention to conversion rate and margin efficiency "
            "as leading indicators of demand quality."
        )

    # Revenue headline
    rev = next((k for k in kpi_comparison if k["name"] == "gross_revenue"), None)
    rev_line = ""
    if rev:
        direction = "declined" if rev["pct_change"] < 0 else "grew"
        rev_line = (
            f"Gross revenue {direction} by {abs(rev['pct_change'])*100:.1f}% "
            "versus the comparison period. "
        )

    # Top driver
    driver_line = ""
    if drivers:
        top = drivers[0]
        driver_direction = "lower" if top["impact_direction"] == "negative" else "higher"
        driver_line = (
            f"The primary identified driver is {driver_line}{top['label'].lower()}, "
            f"which moved {top['pct_change']*100:.1f}% and carries a relevance "
            f"score of {top['relevance']:.0%} against the target metric. "
        )

    # Top recommendation
    rec_line = ""
    if recommendations:
        top_rec = recommendations[0]
        rec_line = (
            f"The highest-priority action is: {top_rec['title'].lower()}. "
        )

    alert_count = len(alerts)
    summary = (
        f"{rev_line}"
        f"The period shows {alert_count} KPI{'s' if alert_count > 1 else ''} in alert status, "
        f"with {len(warnings)} additional warning-level signals. "
        f"{driver_line}"
        f"{rec_line}"
        "Management attention is recommended before committing additional resources "
        "without resolving the underlying performance drivers."
    )
    return summary

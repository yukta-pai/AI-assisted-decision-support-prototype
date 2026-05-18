# ◈ AI Decision Support Prototype

**From Reporting to Action** — a structured decision-support system that moves business users beyond KPI dashboards toward root-cause understanding, scenario testing, and prioritised action.

---

## What This Is

Most analytics tools answer *"What happened?"* A dashboard shows revenue dropped 12%. That's the end of the story.

This prototype answers the next three questions:

| Question | Layer |
|---|---|
| Why did it happen? | Driver attribution engine |
| What should we do? | Recommendation engine |
| What could happen next? | Scenario simulator |

The AI component (executive summary) sits on top of *structured, pre-computed outputs* — it translates results into management language. It does not perform the analysis. That distinction matters architecturally.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI (app/)                  │
│         Filters · Cards · Charts · Sliders · Summary    │
└──────────────────────────┬──────────────────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │        Decision Engine (src/)   │
          │                                 │
          │  Layer 1: KPI Monitoring        │
          │  · Period-over-period comparison│
          │  · Alert threshold flagging     │
          │                                 │
          │  Layer 2: Driver Attribution    │
          │  · Metric dependency map        │
          │  · Weighted relevance scoring   │
          │  · Ranked driver output         │
          │                                 │
          │  Layer 3: Scenario Simulation   │
          │  · Deterministic formula engine │
          │  · 6 adjustable levers          │
          │  · Full downstream recomputation│
          │                                 │
          │  Layer 4: Recommendation Engine │
          │  · Pattern-matched action library│
          │  · Priority matrix (impact ×    │
          │    urgency × confidence)        │
          └────────────────┬────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │        AI Summary Layer         │
          │      Anthropic Claude API       │
          │      Grounded prompt from       │
          │     structured engine outputs   │
          │      Rule-based fallback if     │
          │       no API key provided       │
          └─────────────────────────────────┘
```

---

## Features

### KPI Monitoring
Tracks 11 e-commerce KPIs with period-over-period comparison and threshold-based alert flagging (alert / warning / ok). Primary metrics: gross revenue, net revenue, traffic, orders, conversion rate, AOV, gross margin, return rate, ROAS, CAC proxy, marketing spend.

### Driver Attribution
Identifies likely causes behind KPI movement using a weighted dependency map. Returns ranked relevance scores — not a single explanation. Example output for a revenue decline:

```
Traffic volume         → relevance: 0.49  (negative impact)
Conversion rate        → relevance: 0.33  (negative impact)
Return rate            → relevance: 0.18  (negative impact)
```

### Scenario Simulation
Six independently adjustable levers: traffic, conversion rate, AOV, marketing spend, return rate, margin %. All downstream metrics (orders, gross revenue, net revenue, gross margin, ROAS, CAC) are recomputed using the same formulae as the core dataset. Output includes waterfall chart and comparison table.

### Recommendation Engine
Maps detected patterns to a structured action library. Each recommendation carries: title, rationale, suggested actions, impact/effort/urgency ratings, confidence score, and priority tag. Prioritisation uses a 3-dimension matrix (impact × urgency × confidence band).

### AI Executive Summary
Passes pre-computed structured results to Claude via the Anthropic API. The prompt explicitly instructs the model to translate outputs into management language — not to compute or invent numbers. Falls back to a rule-based summary if no API key is provided.

---

## Data Design

Synthetic dataset generated via `src/data_generator.py`. All metric relationships are formula-consistent:

```
orders          = traffic × conversion_rate
gross_revenue   = orders × avg_order_value
refunds         = gross_revenue × return_rate
net_revenue     = gross_revenue − refunds
gross_margin    = (net_revenue × margin_pct) − marketing_spend
roas            = gross_revenue / marketing_spend
cac_proxy       = marketing_spend / orders
```

**Coverage:** 104 weeks (2 years) × 4 regions × 5 categories = 2,080 rows  
**Grain:** Weekly, per region/category  
**Anomalies:** 3 injected business shocks (channel outage, competitor promo, returns spike)  
**Assumptions:** Documented in `data/assumptions.yaml`

---

## Project Structure

```
decision-support-prototype/
├── app/
│   ├── main.py           # Streamlit entry point
│   ├── ui.py             # UI component library
│   └── charts.py         # Plotly chart builders
│
├── src/
│   ├── data_generator.py     # Synthetic dataset generation
│   ├── kpi_engine.py         # KPI aggregation, alerts, trends
│   ├── anomaly_detection.py  # Z-score anomaly detection
│   ├── driver_analysis.py    # Weighted driver attribution
│   ├── scenario_simulator.py # Deterministic what-if engine
│   ├── recommendation_engine.py  # Pattern-matched actions
│   ├── summary_generator.py  # LLM summary + fallback
│   └── utils.py              # Shared helpers
│
├── data/
│   ├── synthetic_kpi_data.csv
│   └── assumptions.yaml
│
├── tests/
│   ├── test_driver_analysis.py   # 11 tests
│   ├── test_kpi_engine.py        # 15 tests
│   ├── test_recommendations.py   # 16 tests
│   └── test_scenarios.py         # 14 tests
│
├── config.yaml           # KPI thresholds, weights, settings
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

## Quick Start

### Local

```bash
git clone <repo>
cd decision-support-prototype

pip install -r requirements.txt

# Generate synthetic dataset
python src/data_generator.py

# Optional: add your Anthropic API key for AI summaries
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...

streamlit run app/main.py
```

### Docker

```bash
docker build -t decision-support .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=sk-ant-... decision-support
```

App runs at `http://localhost:8501`

---

## Running Tests

```bash
python -m pytest tests/ -v
```

54 tests across all decision engine layers. All pass on Python 3.12.

---

## Stack

| Component | Technology |
|---|---|
| App framework | Streamlit |
| Data processing | Pandas, NumPy |
| Charts | Plotly |
| AI summary | Anthropic Claude API |
| Packaging | Docker |
| Tests | pytest |
| Config | YAML |

---

## Design Decisions

**Why deterministic simulation, not ML?** The scenario engine uses explicit formulas rather than a regression model. This makes outputs auditable, a business user can trace exactly why projected revenue changed. A black-box model would undermine trust in a decision-support context.

**Why structured prompt for the LLM?** The AI layer receives pre-computed numbers and rankings. It cannot invent figures. This is the correct separation: engine computes, model communicates. It also makes the summary consistent with what the charts show.

**Why synthetic data?** Because the data relationships — not the source — are what demonstrate analytical capability. All assumptions are stated in `data/assumptions.yaml`. A real dataset would make the project harder to share and harder to explain without NDA concerns.

**Why one business domain?** Scope discipline. Five features done well in one domain beat ten features done poorly across three.

---

## Limitations

- Return rate in the driver map uses a simplified directional model. A proper attribution would require per-order-level data.
- The scenario simulation is deterministic and does not model second-order effects (e.g., how increased spend affects traffic quality, not just volume).
- Anomaly detection uses a rolling z-score. Seasonal patterns are not explicitly removed before scoring, which can generate false positives in high-variance periods.
- The recommendation engine matches patterns to a fixed library. It does not learn from outcome data.

---

*Prototype built for portfolio demonstration. Data is synthetic. All formula relationships and assumptions are documented.*

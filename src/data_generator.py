"""
data_generator.py
Generates a synthetic but mathematically coherent e-commerce KPI dataset.
All metric relationships are formula-consistent, not randomly assembled.
"""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

ASSUMPTIONS_PATH = Path(__file__).parent.parent / "data" / "assumptions.yaml"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "synthetic_kpi_data.csv"


def load_assumptions() -> dict:
    with open(ASSUMPTIONS_PATH) as f:
        return yaml.safe_load(f)


def get_seasonality_index(date: pd.Timestamp) -> float:
    """Return a week-level seasonality multiplier based on time of year."""
    month = date.month
    week_of_year = date.isocalendar()[1]

    # Quarterly base
    if month <= 3:
        base = 0.88
    elif month <= 6:
        base = 0.95
    elif month <= 9:
        base = 1.02
    else:
        base = 1.28

    # Black Friday / Cyber Monday spike (weeks 47-49)
    if 47 <= week_of_year <= 49:
        base *= 1.45

    # Christmas week
    if week_of_year == 51 or week_of_year == 52:
        base *= 1.20

    # January dip
    if week_of_year <= 2:
        base *= 0.75

    return base


def inject_anomaly(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """
    Inject 2–4 realistic anomaly events into the dataset.
    These are intentional shocks that the detection layer should surface.
    """
    events = [
        {
            "label": "Paid channel outage",
            "weeks": 2,
            "traffic_shock": -0.30,
            "conversion_shock": -0.05,
            "spend_shock": -0.20,
        },
        {
            "label": "Competitor promo",
            "weeks": 3,
            "traffic_shock": -0.12,
            "conversion_shock": -0.15,
            "spend_shock": 0.10,
        },
        {
            "label": "Returns surge (quality issue)",
            "weeks": 2,
            "traffic_shock": 0.0,
            "conversion_shock": 0.0,
            "return_shock": 0.12,
        },
    ]

    dates = df["date"].unique()
    # Pick random non-overlapping start weeks for events
    used = set()
    for event in events:
        candidates = [
            d for d in dates[8:-8]
            if d not in used
        ]
        if not candidates:
            continue
        start = rng.choice(candidates)
        idx_start = list(dates).index(start)
        event_dates = dates[idx_start: idx_start + event["weeks"]]
        used.update(event_dates)

        mask = df["date"].isin(event_dates)
        if "traffic_shock" in event:
            df.loc[mask, "_traffic_shock"] = 1 + event["traffic_shock"]
        if "conversion_shock" in event:
            df.loc[mask, "_conv_shock"] = 1 + event["conversion_shock"]
        if "spend_shock" in event:
            df.loc[mask, "_spend_shock"] = 1 + event["spend_shock"]
        if "return_shock" in event:
            df.loc[mask, "_return_shock"] = event["return_shock"]

    return df


def generate_dataset(
    start_date: str = "2023-01-02",
    periods: int = 104,  # 2 years of weekly data
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a weekly e-commerce KPI dataset.

    Returns a DataFrame with one row per (date, region, category).
    All metrics satisfy the formula constraints defined in assumptions.yaml.
    """
    rng = np.random.default_rng(seed)
    assumptions = load_assumptions()

    dates = pd.date_range(start=start_date, periods=periods, freq="W-MON")
    regions = list(assumptions["region_multipliers"].keys())
    categories = list(assumptions["category_multipliers"].keys())

    rows = []

    for region in regions:
        r_mult = assumptions["region_multipliers"][region]
        for category in categories:
            c_mult = assumptions["category_multipliers"][category]
            scale = r_mult * c_mult

            # Initialise shock columns
            _df_chunk = pd.DataFrame({"date": dates})
            _df_chunk["_traffic_shock"] = 1.0
            _df_chunk["_conv_shock"] = 1.0
            _df_chunk["_spend_shock"] = 1.0
            _df_chunk["_return_shock"] = 0.0
            _df_chunk["region"] = region
            _df_chunk["category"] = category
            _df_chunk = inject_anomaly(_df_chunk, rng)

            for _, row in _df_chunk.iterrows():
                date = row["date"]
                seas = get_seasonality_index(date)

                # --- Traffic ---
                base_traffic = (
                    assumptions["baseline"]["traffic_weekly"]
                    * scale
                    * seas
                    * row["_traffic_shock"]
                )
                noise_t = rng.normal(1.0, assumptions["noise"]["traffic_std"])
                traffic = max(int(base_traffic * noise_t), 100)

                # --- Conversion rate ---
                base_conv = (
                    assumptions["baseline"]["conversion_rate"]
                    * row["_conv_shock"]
                )
                noise_c = rng.normal(0, assumptions["noise"]["conversion_std"])
                conversion_rate = float(np.clip(base_conv + noise_c, 0.005, 0.20))

                # --- Orders (deterministic from traffic * conv) ---
                orders = int(traffic * conversion_rate)

                # --- AOV ---
                base_aov = assumptions["baseline"]["avg_order_value"] * (
                    1 + rng.normal(0, assumptions["noise"]["aov_std"])
                )
                # Electronics have higher AOV
                if category == "Electronics":
                    base_aov *= 2.8
                elif category == "Apparel":
                    base_aov *= 0.85
                elif category == "Health & Beauty":
                    base_aov *= 0.70
                avg_order_value = max(float(base_aov), 10.0)

                # --- Revenue (deterministic) ---
                gross_revenue = orders * avg_order_value

                # --- Marketing spend ---
                base_spend = (
                    assumptions["baseline"]["marketing_spend_weekly"]
                    * scale
                    * seas
                    * row["_spend_shock"]
                )
                noise_s = rng.normal(1.0, assumptions["noise"]["marketing_std"])
                marketing_spend = max(float(base_spend * noise_s), 100.0)

                # --- Return rate ---
                base_return = assumptions["baseline"]["return_rate"]
                base_return += row["_return_shock"]
                # Electronics / Apparel have higher returns
                if category in ("Electronics", "Apparel"):
                    base_return *= 1.2
                return_rate = float(np.clip(
                    base_return + rng.normal(0, 0.008), 0.01, 0.35
                ))

                # --- Refunds & net revenue (deterministic) ---
                refunds = gross_revenue * return_rate
                net_revenue = gross_revenue - refunds

                # --- Margin ---
                base_margin = assumptions["baseline"]["margin_pct"]
                noise_m = rng.normal(0, 0.02)
                margin_pct = float(np.clip(base_margin + noise_m, 0.10, 0.65))
                gross_margin = (net_revenue * margin_pct) - marketing_spend

                # --- Derived ---
                roas = gross_revenue / marketing_spend if marketing_spend > 0 else 0
                cac_proxy = marketing_spend / orders if orders > 0 else 0

                # Seasonality index for reference
                seasonality_index = round(seas, 3)

                rows.append({
                    "date": date,
                    "region": region,
                    "category": category,
                    "traffic": traffic,
                    "conversion_rate": round(conversion_rate, 4),
                    "orders": orders,
                    "avg_order_value": round(avg_order_value, 2),
                    "gross_revenue": round(gross_revenue, 2),
                    "marketing_spend": round(marketing_spend, 2),
                    "return_rate": round(return_rate, 4),
                    "refunds": round(refunds, 2),
                    "net_revenue": round(net_revenue, 2),
                    "margin_pct": round(margin_pct, 4),
                    "gross_margin": round(gross_margin, 2),
                    "roas": round(roas, 4),
                    "cac_proxy": round(cac_proxy, 4),
                    "seasonality_index": seasonality_index,
                })

    df = pd.DataFrame(rows)
    df = df.sort_values(["date", "region", "category"]).reset_index(drop=True)
    return df


if __name__ == "__main__":
    print("Generating synthetic KPI dataset...")
    df = generate_dataset()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df):,} rows to {OUTPUT_PATH}")
    print("\nSample:")
    print(df.head(3).to_string())
    print(f"\nDate range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"Regions: {df['region'].unique().tolist()}")
    print(f"Categories: {df['category'].unique().tolist()}")

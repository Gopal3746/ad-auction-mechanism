from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "warehouse" / "auction_analytics.duckdb"
ARTIFACTS = ROOT / "artifacts"

st.set_page_config(page_title="Ad Auction Mechanism Simulator", layout="wide")
st.title("Ad Auction Mechanism Simulator")
st.caption("Controlled synthetic experiment: first-price, second-price, and sample-reserve auctions")

if not DATABASE.exists():
    st.error("Warehouse not found. Run `auction-sim --auctions 10000 --seed 42` first.")
    st.stop()

with duckdb.connect(str(DATABASE), read_only=True) as connection:
    kpis = connection.execute("SELECT * FROM v_mechanism_kpis ORDER BY revenue_per_auction DESC").df()
    daily = connection.execute("SELECT * FROM v_daily_fill_rate").df()
    shading = connection.execute("SELECT * FROM v_bid_shading_by_depth").df()
    depth = connection.execute("SELECT * FROM v_auction_depth_distribution").df()
    placement = connection.execute("SELECT * FROM v_placement_mechanism_kpis").df()
    revenue_sample = connection.execute(
        """
        SELECT mechanism, seller_revenue
        FROM fact_auction_outcomes
        WHERE split = 'evaluation'
        USING SAMPLE 15000 ROWS
        """
    ).df()

mechanism = st.selectbox("Inspect a mechanism", kpis["mechanism"].tolist())
selected = kpis[kpis["mechanism"] == mechanism].iloc[0]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Revenue / auction", f"{selected.revenue_per_auction:.3f} CPM")
col2.metric("Fill rate", f"{selected.fill_rate:.1%}")
col3.metric("Average bid spread", f"{selected.avg_bid_spread:.3f}")
col4.metric("Mean shading ratio", f"{selected.avg_shading_ratio:.1%}")

st.subheader("Mechanism comparison")
st.dataframe(
    kpis.style.format(
        {
            "fill_rate": "{:.1%}",
            "revenue_per_auction": "{:.3f}",
            "avg_bid_spread": "{:.3f}",
            "avg_shading_ratio": "{:.1%}",
            "avg_winner_surplus": "{:.3f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Daily fill rate")
daily_pivot = daily.pivot(index="event_date", columns="mechanism", values="fill_rate")
st.line_chart(daily_pivot)

left, right = st.columns(2)
with left:
    st.subheader("Revenue distribution")
    st.bar_chart(
        revenue_sample.groupby("mechanism")["seller_revenue"].mean().sort_values(ascending=False)
    )
    st.caption("Bar height is mean revenue per auction; detailed distributions remain in DuckDB.")
with right:
    st.subheader("Auction depth")
    st.bar_chart(depth.set_index("auction_depth")["auction_count"])

st.subheader("Bid shading by auction depth")
filtered_shading = shading[shading["mechanism"] == mechanism].set_index("auction_depth")
st.line_chart(filtered_shading[["avg_shading_ratio"]])

st.subheader("Placement-level KPIs")
st.dataframe(
    placement[placement["mechanism"] == mechanism],
    use_container_width=True,
    hide_index=True,
)

summary_path = ARTIFACTS / "executive_summary.md"
if summary_path.exists():
    st.subheader("Executive summary")
    st.markdown(summary_path.read_text(encoding="utf-8"))

hypothesis_path = ARTIFACTS / "hypothesis_tests.csv"
if hypothesis_path.exists():
    st.subheader("Hypothesis tests")
    st.dataframe(pd.read_csv(hypothesis_path), use_container_width=True, hide_index=True)

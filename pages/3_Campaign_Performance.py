import streamlit as st
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.transforms import combine_primary_data
from src.filters import render_sidebar, apply_global_filters
from src.metrics import summarize
from src.charts import metric_trend_line, campaign_performance_scatter, top_n_bar
from src.tables import render_table


st.set_page_config(page_title="Campaign Performance | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Campaign Performance")
st.caption("Campaign and ad group optimization view focused on cost, outcomes, and quality.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation)
campaign = apply_global_filters(campaign, filters)

if campaign.empty:
    st.warning("No campaign performance data is available.")
    st.stop()

ad_group_filter = []
if "ad_group" in campaign.columns:
    ad_group_filter = st.multiselect("Ad group", sorted(campaign["ad_group"].dropna().unique()))
    if ad_group_filter:
        campaign = campaign[campaign["ad_group"].isin(ad_group_filter)]

st.plotly_chart(metric_trend_line(campaign, "spend", "Campaign spend trend"), use_container_width=True)
st.plotly_chart(campaign_performance_scatter(campaign, "quality_cpa", "Spend vs quality CPA"), use_container_width=True)

tab1, tab2, tab3, tab4 = st.tabs(["Highest spend", "Highest conversions", "Highest CPA", "Zero conversions"])
summary_cols = ["objective", "campaign"] + (["ad_group"] if "ad_group" in campaign.columns else [])
perf = summarize(campaign, summary_cols)
with tab1:
    render_table(perf.sort_values("spend", ascending=False).head(50), "Highest spend", "Where budget is concentrated.", key="highest_spend")
with tab2:
    render_table(perf.sort_values("quality_conversions", ascending=False).head(50), "Highest quality conversions", "Campaigns and ad groups producing quality outcomes.", key="highest_conversions")
with tab3:
    meaningful = perf[(perf["spend"] > 0) & (perf["conversions"] > 0)].sort_values("cpa", ascending=False)
    render_table(meaningful.head(50), "Highest CPA with conversion volume", "Rows with measurable conversion activity but inefficient cost.", key="highest_cpa")
with tab4:
    zero = perf[(perf["spend"] > 0) & (perf["conversions"] == 0)].sort_values("spend", ascending=False)
    render_table(zero.head(50), "Spend with zero conversions", "Immediate candidates for targeting, query, or budget review.", key="zero_conversions")

st.plotly_chart(top_n_bar(campaign, "campaign", "spend", 15, "Top campaigns by spend"), use_container_width=True)
render_table(perf, "Campaign performance table", "Full campaign/ad group decision table.", key="campaign_perf")

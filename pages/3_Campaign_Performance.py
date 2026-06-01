import pandas as pd
import streamlit as st

from src.campaign_decisions import build_campaign_decisions, missing_optional_campaign_fields
from src.charts import (
    campaign_conversion_mix_bar,
    campaign_priority_cpa_bar,
    campaign_spend_priority_scatter,
    campaign_status_spend_bar,
)
from src.filters import apply_global_filters, render_sidebar
from src.formatting import PRIORITY_CONVERSIONS_HELP, apply_page_style, kpi_card, money, number, render_conversion_model_debug
from src.google_sheets import load_workbook
from src.metrics import summarize
from src.tables import render_table
from src.transforms import combine_primary_data


ACTION_COLUMNS = [
    "status", "priority_score", "objective", "campaign", "spend", "priority_conversions",
    "priority_cpa", "primary_issue", "recommended_action", "rationale",
]
DECISION_COLUMNS = [
    "status", "objective", "campaign", "ad_group", "spend", "spend_share", "impressions",
    "clicks", "ctr", "cpc", "total_conversions", "priority_conversions", "priority_cpa",
    "enrollment_apply_now_clicks", "enrollment_forms", "applications_submitted", "career_clicks",
    "other_micro_conversions", "cvr", "cpa",
    "primary_issue", "recommended_action",
]


st.set_page_config(page_title="Campaign Performance | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Campaign Performance")
st.caption("Campaign-management decision dashboard focused on HCZ priority outcomes, budget alignment, and the next best action.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation, thresholds=True)
campaign = apply_global_filters(campaign, filters)

if campaign.empty:
    st.warning("No campaign performance data is available with the current filters.")
    st.stop()

missing_optional = missing_optional_campaign_fields(campaign)
if missing_optional:
    st.warning(
        "Some optional campaign fields are unavailable, so safe fallbacks are being used: "
        + ", ".join(missing_optional)
        + "."
    )

ad_group_filter = []
if "ad_group" in campaign.columns:
    ad_group_filter = st.multiselect("Ad group", sorted(campaign["ad_group"].dropna().unique()))
    if ad_group_filter:
        campaign = campaign[campaign["ad_group"].isin(ad_group_filter)]

thresholds = filters["thresholds"]
campaign_level = build_campaign_decisions(campaign, thresholds, include_ad_group=False)
decision_table = build_campaign_decisions(campaign, thresholds, include_ad_group=True)
totals = summarize(campaign).iloc[0]

cols = st.columns(6)
with cols[0]: kpi_card("Total spend", money(totals["spend"]))
with cols[1]: kpi_card("Priority conversions", number(totals["priority_conversions"], 1), help_text=PRIORITY_CONVERSIONS_HELP)
with cols[2]: kpi_card("Priority CPA", money(totals["priority_cpa"]), help_text=PRIORITY_CONVERSIONS_HELP)
with cols[3]: kpi_card("Campaigns to investigate", number((campaign_level["status"] == "Investigate").sum()))
with cols[4]: kpi_card("Campaigns to optimize", number((campaign_level["status"] == "Optimize").sum()))
with cols[5]: kpi_card("Campaigns eligible to scale", number((campaign_level["status"] == "Scale").sum()))

st.subheader("Recommended campaign actions")
st.caption("Prioritized, rule-based actions. Mapping and investigation work surfaces before budget expansion.")
render_table(
    campaign_level,
    "Action queue",
    "Start at the top: priority reflects decision urgency and spend exposure.",
    sort_by="priority_score",
    key="campaign_actions",
    display_columns=ACTION_COLUMNS,
)

st.subheader("Spend and priority outcome alignment")
st.caption("Campaigns should move up and to the right. Bubble size reflects click volume; hover for the reason behind each status.")
st.plotly_chart(campaign_spend_priority_scatter(campaign_level), use_container_width=True)

st.subheader("Campaign diagnostic charts")
left, right = st.columns(2)
with left:
    priority_cpa_chart = campaign_priority_cpa_bar(campaign_level, thresholds["min_spend"], thresholds["min_priority_conversions"])
    st.plotly_chart(priority_cpa_chart, use_container_width=True)
with right:
    st.plotly_chart(campaign_status_spend_bar(campaign_level), use_container_width=True)

mix_chart = campaign_conversion_mix_bar(campaign_level)
if mix_chart.data:
    st.plotly_chart(mix_chart, use_container_width=True)
else:
    st.info("Conversion mix chart is unavailable because detailed conversion outcome columns are not present.")

st.subheader("Campaign decision table")
st.caption("Use status and primary issue together: status says what to do next, while the issue explains why.")
render_table(
    decision_table,
    "Campaign and ad group decisions",
    "Full decision view with HCZ priority outcomes before efficiency metrics.",
    sort_by="priority_score",
    key="campaign_decisions",
    display_columns=DECISION_COLUMNS,
)

with st.expander("Supporting campaign views", expanded=False):
    tab1, tab2, tab3, tab4 = st.tabs(["Highest spend", "Highest priority conversions", "High Priority CPA", "Zero priority conversions"])
    with tab1:
        render_table(campaign_level.sort_values("spend", ascending=False).head(50), "Highest spend", key="highest_spend")
    with tab2:
        render_table(campaign_level.sort_values("priority_conversions", ascending=False).head(50), "Highest priority conversions", key="highest_priority_conversions")
    with tab3:
        meaningful = campaign_level[(campaign_level["spend"] >= thresholds["min_spend"]) & (campaign_level["priority_conversions"] > 0)]
        render_table(meaningful.sort_values("priority_cpa", ascending=False).head(50), "High Priority CPA", key="high_priority_cpa")
    with tab4:
        zero_priority = campaign_level[(campaign_level["spend"] > 0) & (campaign_level["priority_conversions"] == 0)]
        render_table(zero_priority.sort_values("spend", ascending=False).head(50), "Zero priority conversions", key="zero_priority_conversions")

with st.expander("Debug conversion outcome join", expanded=False):
    render_conversion_model_debug(campaign)

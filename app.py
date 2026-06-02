import pandas as pd
import streamlit as st
from src.benchmarks import (
    RECRUITMENT_CAVEAT,
    UNAVAILABLE_MESSAGE,
    get_campaign_type_benchmarks,
    latest_complete_benchmarks,
    priority_cpa_display,
    recruitment_caveat_present,
)
from src.benchmark_cards import render_metric_grid
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.transforms import combine_primary_data
from src.filters import render_sidebar, apply_global_filters
from src.metrics import summarize, period_delta, share_columns
from src.formatting import PRIORITY_CONVERSIONS_HELP, money, number, percent, signed_percent, kpi_card, render_data_source_debug
from src.charts import spend_vs_conversions_bar_line, objective_mix_bar, top_n_bar
from src.tables import render_table


st.set_page_config(page_title="HCZ Google Ads Dashboard", layout="wide")
apply_page_style()

st.title("HCZ Google Ads Executive Summary")
st.caption("Internal reporting dashboard for spend, traffic, priority outcomes, and optimization priorities.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet.")
    st.info("Check that .streamlit/secrets.toml contains a valid service account and that the service account email has access to the workbook.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation)
campaign = apply_global_filters(campaign, filters)
search = apply_global_filters(search, filters)
landing = apply_global_filters(landing, filters)

summary = summarize(campaign)
if summary.empty or campaign.empty:
    st.warning("No campaign performance data is available yet. Add a model_performance_canonical tab or another supported campaign tab.")
    st.stop()

row = summary.iloc[0]
deltas = {}
if filters.get("date_range") and len(filters["date_range"]) == 2:
    deltas = period_delta(campaign, pd.to_datetime(filters["date_range"][0]), pd.to_datetime(filters["date_range"][1]))

cols = st.columns(5)
with cols[0]: kpi_card("Spend", money(row.spend), signed_percent(deltas.get("spend")), "Media cost in selected period.")
with cols[1]: kpi_card("Impressions", number(row.impressions), None)
with cols[2]: kpi_card("Clicks", number(row.clicks), signed_percent(deltas.get("clicks")))
with cols[3]: kpi_card("CTR", percent(row.ctr), signed_percent(deltas.get("ctr")))
with cols[4]: kpi_card("CPC", money(row.cpc, 2), None)
cols = st.columns(4)
with cols[0]: kpi_card("Total conversions", number(row.total_conversions, 1), signed_percent(deltas.get("conversions")))
with cols[1]: kpi_card("CPA", money(row.cpa), signed_percent(deltas.get("cpa")))
with cols[2]: kpi_card("Priority conversions", number(row.priority_conversions, 1), None, PRIORITY_CONVERSIONS_HELP)
with cols[3]: kpi_card("Priority CPA", priority_cpa_display(row.priority_cpa, row.priority_conversions), None, PRIORITY_CONVERSIONS_HELP)

st.plotly_chart(spend_vs_conversions_bar_line(campaign), use_container_width=True)

left, right = st.columns(2)
with left:
    st.plotly_chart(objective_mix_bar(campaign, "spend", "Spend by objective"), use_container_width=True)
with right:
    st.plotly_chart(objective_mix_bar(campaign, "priority_conversions", "Priority conversions by objective"), use_container_width=True)

objective = share_columns(summarize(campaign, ["objective"])).sort_values("spend", ascending=False)
campaign_summary = summarize(campaign, ["objective", "campaign"]).sort_values("spend", ascending=False)

st.subheader("What to look at")
notes = []
if not campaign_summary.empty:
    top = campaign_summary.iloc[0]
    spend_share = top.spend / campaign_summary.spend.sum() if campaign_summary.spend.sum() else 0
    notes.append(f"Spend is concentrated in {top.campaign}, which accounts for {percent(spend_share)} of filtered spend.")
if "Enrollment" in objective.get("objective", []).values:
    enroll = objective[objective.objective.eq("Enrollment")].iloc[0]
    notes.append(f"Enrollment accounts for {percent(enroll.priority_conversions_share)} of priority conversions.")
zero_priority = campaign_summary[(campaign_summary.spend > 0) & (campaign_summary.priority_conversions == 0)]
if not zero_priority.empty:
    notes.append(f"{len(zero_priority)} campaigns have spend but no priority conversions.")
if not search.empty and "objective" in search.columns:
    unmapped_spend = search.loc[search.objective.eq("Other / Unmapped"), "spend"].sum()
    total_spend = search["spend"].sum()
    notes.append(f"{percent(unmapped_spend / total_spend if total_spend else 0)} of search term spend is currently unmapped.")
for note in notes or ["Load more model data to populate automated diagnostic readouts."]:
    st.write(f"- {note}")

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(top_n_bar(campaign, "campaign", "spend", 10, "Top campaigns by spend"), use_container_width=True)
with col2:
    st.plotly_chart(top_n_bar(campaign, "campaign", "priority_conversions", 10, "Top campaigns by priority conversions"), use_container_width=True)

render_table(objective, "Objective split", "Spend, traffic, and efficiency by objective.", key="objective_split")
render_table(campaign_summary.head(50), "Campaign diagnostics", "Top campaign rows sorted by spend.", key="campaign_diagnostics")

st.subheader("Performance vs Benchmarks")
st.caption("Benchmark cards use the latest complete month to avoid comparing partial current-month data against full historical periods.")
benchmarks = get_campaign_type_benchmarks(data)
latest, benchmark_month_used, used_incomplete_fallback = latest_complete_benchmarks(benchmarks)
if latest.empty:
    st.info(UNAVAILABLE_MESSAGE)
else:
    if used_incomplete_fallback:
        st.warning("No complete benchmark month is available. Benchmark cards are using the latest available month, which may be partial.")
    st.caption(f"Benchmark month: {benchmark_month_used:%b %Y}")
    preferred_cards = [("Nonbrand Search", "Enrollment"), ("Nonbrand Search", "Recruitment")]
    if st.checkbox("Show Performance Max benchmark cards", value=False):
        preferred_cards += [("Performance Max", "Enrollment"), ("Performance Max", "Recruitment")]
    rendered = False
    for campaign_type, objective_name in preferred_cards:
        matched = latest[
            latest["campaign_type"].astype(str).str.casefold().eq(campaign_type.casefold())
            & latest["objective"].astype(str).str.casefold().eq(objective_name.casefold())
        ]
        if not matched.empty:
            rendered = True
            st.markdown(f"**{campaign_type} / {objective_name}**")
            render_metric_grid(matched.iloc[0], objective_name)
    if not rendered:
        st.info("The latest benchmark month does not include the featured campaign type and objective combinations.")
    if recruitment_caveat_present(latest):
        st.warning(
            f"{RECRUITMENT_CAVEAT}: Applications Submitted was not consistently tracked before July 2025, "
            "so Recruitment YoY priority-conversion comparisons should be treated cautiously."
        )

with st.expander("Data Source Debug", expanded=False):
    render_data_source_debug(campaign)

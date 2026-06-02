import pandas as pd
import streamlit as st
from src.benchmarks import (
    RECRUITMENT_CAVEAT,
    UNAVAILABLE_MESSAGE,
    get_campaign_type_benchmarks,
    get_latest_complete_benchmark_month,
    latest_complete_benchmarks,
    priority_cpa_display,
    recruitment_caveat_present,
    yoy_percentage_display,
)
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
latest_available_month = benchmarks["month"].max() if not benchmarks.empty else None
latest_complete_month = get_latest_complete_benchmark_month(benchmarks)
latest, benchmark_month_used, used_incomplete_fallback = latest_complete_benchmarks(benchmarks)
current_month = pd.Timestamp.today().to_period("M").start_time
current_month_rows_excluded = (
    not benchmarks.empty
    and benchmarks["month"].dt.to_period("M").dt.start_time.eq(current_month).any()
    and benchmark_month_used != current_month
)
if latest.empty:
    st.info(UNAVAILABLE_MESSAGE)
else:
    if used_incomplete_fallback:
        st.warning("No complete benchmark month is available. Benchmark cards are using the latest available month, which may be partial.")
    preferred_cards = [
        ("Nonbrand Search", "Enrollment"),
        ("Nonbrand Search", "Recruitment"),
        ("Performance Max", "Enrollment"),
        ("Performance Max", "Recruitment"),
    ]
    card_rows = []
    for campaign_type, objective_name in preferred_cards:
        matched = latest[
            latest["campaign_type"].astype(str).str.casefold().eq(campaign_type.casefold())
            & latest["objective"].astype(str).str.casefold().eq(objective_name.casefold())
        ]
        if not matched.empty:
            card_rows.append(matched.iloc[0])
    if card_rows:
        cols = st.columns(len(card_rows))
        for col, benchmark in zip(cols, card_rows):
            with col:
                st.markdown(f"**{benchmark['campaign_type']} / {benchmark['objective']}**")
                kpi_card("Priority CPA", priority_cpa_display(benchmark.get("priority_cpa"), benchmark.get("priority_conversions")))
                st.caption(f"3Mo Benchmark Status: {benchmark.get('benchmark_status', '-')}")
                st.caption(f"YoY Benchmark Status: {benchmark.get('yoy_benchmark_status', '-')}")
                st.caption(f"Priority CPA YoY: {yoy_percentage_display(benchmark, 'priority_cpa_yoy_pct')}")
                st.caption(f"Priority Conversions YoY: {yoy_percentage_display(benchmark, 'priority_conversions_yoy_pct')}")
    else:
        st.info("The latest benchmark month does not include the featured campaign type and objective combinations.")
    if recruitment_caveat_present(latest):
        st.warning(
            f"{RECRUITMENT_CAVEAT}: Applications Submitted was not consistently tracked before July 2025, "
            "so Recruitment YoY priority-conversion comparisons should be treated cautiously."
        )
    takeaway_columns = [
        "campaign_type", "objective", "benchmark_status", "yoy_benchmark_status",
        "priority_cpa", "prior_year_priority_cpa", "yoy_benchmark_note",
    ]
    render_table(
        latest,
        "Biggest Benchmark Takeaways",
        "Latest campaign-type benchmark readout from the Google Sheet.",
        sort_by=None,
        key="executive_benchmark_takeaways",
        display_columns=takeaway_columns,
    )
    with st.expander("Benchmark card debug", expanded=False):
        selected_date_range = filters.get("date_range")
        st.write(f"Selected dashboard date range: `{selected_date_range or 'All available dates'}`")
        st.write(f"Benchmark month used: `{benchmark_month_used:%b %Y}`")
        st.write(f"Latest available benchmark month: `{latest_available_month:%b %Y}`")
        st.write(f"Latest complete benchmark month: `{latest_complete_month.strftime('%b %Y') if latest_complete_month is not None else 'None available'}`")
        st.write(f"Current month rows excluded: `{'Yes' if current_month_rows_excluded else 'No'}`")
        st.caption("Rows used for the benchmark cards")
        st.dataframe(pd.DataFrame(card_rows), use_container_width=True, hide_index=True)

with st.expander("Data Source Debug", expanded=False):
    render_data_source_debug(campaign)

import pandas as pd
import streamlit as st
from src.benchmarks import (
    RECRUITMENT_CAVEAT,
    UNAVAILABLE_MESSAGE,
    get_campaign_type_benchmarks,
    latest_complete_benchmarks,
    recruitment_caveat_present,
)
from src.benchmark_cards import render_metric_grid
from src.formatting import apply_page_style
from src.google_sheets import clear_data_cache, load_workbook
from src.transforms import combine_primary_data
from src.filters import multiselect_if_available, show_validation
from src.metrics import summarize, share_columns
from src.periods import (
    DATE_PRESETS,
    calculate_metric_delta,
    calculate_period_metrics,
    format_delta,
    get_comparison_range,
    get_date_range_from_preset,
    metric_direction,
)
from src.formatting import PRIORITY_CONVERSIONS_HELP, money, number, percent, render_data_source_debug
from src.charts import spend_vs_conversions_bar_line, objective_mix_bar, top_n_bar
from src.tables import render_table


ACCOUNT_CARDS = [
    ("Spend", "spend", "money", None),
    ("Impressions", "impressions", "number", None),
    ("Clicks", "clicks", "number", None),
    ("CTR", "ctr", "percent", None),
    ("CPC", "cpc", "money2", "clicks"),
    ("Total Conversions", "total_conversions", "number1", None),
    ("CPA", "cpa", "money", "total_conversions"),
    ("Priority Conversions", "priority_conversions", "number1", None),
    ("Priority CPA", "priority_cpa", "money", "priority_conversions"),
]
ENROLLMENT_CARDS = [
    ("Enrollment Apply Now Clicks", "enrollment_apply_now_clicks", "number1", None),
    ("Enrollment Forms", "enrollment_forms", "number1", None),
    ("Priority Conversions", "enrollment_priority_conversions", "number1", None),
    ("Priority CPA", "priority_cpa", "money", "enrollment_priority_conversions"),
    ("Cost / Enrollment Form", "cost_per_enrollment_form", "money", "enrollment_forms"),
    ("Form Share of Priority", "form_share_of_priority", "percent", "enrollment_priority_conversions"),
]
RECRUITMENT_CARDS = [
    ("Career Clicks", "career_clicks", "number1", None),
    ("Applications Submitted", "applications_submitted", "number1", None),
    ("Priority Conversions", "recruitment_priority_conversions", "number1", None),
    ("Priority CPA", "priority_cpa", "money", "recruitment_priority_conversions"),
    ("Cost / Application Submitted", "cost_per_application_submitted", "money", "applications_submitted"),
    ("Career Clicks per Application", "career_clicks_per_application", "ratio", "applications_submitted"),
]


def render_executive_sidebar(campaign, validation):
    st.sidebar.header("Filters")
    if st.sidebar.button("Refresh data", use_container_width=True):
        clear_data_cache()
        st.rerun()
    today = pd.Timestamp.today().normalize()
    if "date" in campaign.columns and campaign["date"].notna().any():
        today = min(today, campaign["date"].max().normalize())
    preset = st.sidebar.selectbox("Date preset", DATE_PRESETS, index=0)
    if preset == "Custom range" and "date" in campaign.columns and campaign["date"].notna().any():
        min_date, max_date = campaign["date"].min().date(), campaign["date"].max().date()
        selected = st.sidebar.date_input("Custom range", (min_date, max_date), min_value=min_date, max_value=max_date)
        start, end = (pd.Timestamp(selected[0]), pd.Timestamp(selected[1])) if len(selected) == 2 else (pd.Timestamp(min_date), pd.Timestamp(max_date))
    else:
        start, end = get_date_range_from_preset(preset, today)
    st.sidebar.caption(f"Current period: {start:%b %d, %Y} - {end:%b %d, %Y}")
    comp_start, comp_end, comparison_label = get_comparison_range(start, end, preset)
    st.sidebar.caption(f"Comparison: {comp_start:%b %d, %Y} - {comp_end:%b %d, %Y}")
    filters = {
        "campaign": multiselect_if_available("Campaign", campaign, "campaign"),
        "network": multiselect_if_available("Network", campaign, "network"),
        "device": multiselect_if_available("Device", campaign, "device"),
    }
    show_validation(validation)
    return preset, start, end, comp_start, comp_end, comparison_label, filters


def filtered_period_df(df, start, end, filters):
    if df.empty or "date" not in df.columns:
        return df
    out = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))].copy()
    for col in ["campaign", "network", "device"]:
        selected = filters.get(col) or []
        if selected and col in out.columns:
            out = out[out[col].isin(selected)]
    return out


def format_value(metrics, key, kind, denominator_key=None):
    value = metrics.get(key)
    if denominator_key and metrics.get(denominator_key, 0) <= 0:
        return "\u2014"
    if value is None or pd.isna(value):
        return "\u2014"
    if kind == "money":
        return money(value)
    if kind == "money2":
        return money(value, 2)
    if kind == "percent":
        return percent(value)
    if kind == "number1":
        return number(value, 1)
    if kind == "ratio":
        return number(value, 1)
    return number(value)


def render_period_cards(title, current_metrics, comparison_metrics, card_specs, comparison_label, columns=3):
    st.subheader(title)
    cols = st.columns(columns)
    for index, (label, metric, kind, denominator) in enumerate(card_specs):
        current = current_metrics.get(metric)
        comparison = comparison_metrics.get(metric)
        direction = metric_direction(metric)
        delta = calculate_metric_delta(current, comparison, direction)
        delta_text, delta_color, helper = format_delta(delta, comparison_label, direction)
        with cols[index % columns]:
            st.metric(
                label,
                format_value(current_metrics, metric, kind, denominator),
                delta=delta_text,
                delta_color=delta_color,
                help=PRIORITY_CONVERSIONS_HELP if metric in {"priority_conversions", "priority_cpa"} else None,
            )
            st.caption(f"{comparison_label}: {format_value(comparison_metrics, metric, kind, denominator)}")
            if helper:
                st.caption(helper)


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
preset, start_date, end_date, comp_start, comp_end, comparison_label, filters = render_executive_sidebar(campaign, validation)
current_campaign = filtered_period_df(campaign, start_date, end_date, filters)
current_search = filtered_period_df(search, start_date, end_date, filters)

summary = summarize(current_campaign)
if summary.empty or current_campaign.empty:
    st.warning("No campaign performance data is available yet. Add a model_performance_canonical tab or another supported campaign tab.")
    st.stop()

current_metrics = calculate_period_metrics(campaign, start_date, end_date, filters)
comparison_metrics = calculate_period_metrics(campaign, comp_start, comp_end, filters)
enrollment_current = calculate_period_metrics(campaign[campaign["objective"].eq("Enrollment")], start_date, end_date, filters)
enrollment_comparison = calculate_period_metrics(campaign[campaign["objective"].eq("Enrollment")], comp_start, comp_end, filters)
recruitment_current = calculate_period_metrics(campaign[campaign["objective"].eq("Recruitment")], start_date, end_date, filters)
recruitment_comparison = calculate_period_metrics(campaign[campaign["objective"].eq("Recruitment")], comp_start, comp_end, filters)

render_period_cards("Account Overview", current_metrics, comparison_metrics, ACCOUNT_CARDS, comparison_label, columns=3)
render_period_cards("Enrollment Performance", enrollment_current, enrollment_comparison, ENROLLMENT_CARDS, comparison_label, columns=3)
render_period_cards("Recruitment Performance", recruitment_current, recruitment_comparison, RECRUITMENT_CARDS, comparison_label, columns=3)

st.plotly_chart(spend_vs_conversions_bar_line(current_campaign), use_container_width=True)

left, right = st.columns(2)
with left:
    st.plotly_chart(objective_mix_bar(current_campaign, "spend", "Spend by objective"), use_container_width=True)
with right:
    st.plotly_chart(objective_mix_bar(current_campaign, "priority_conversions", "Priority conversions by objective"), use_container_width=True)

objective = share_columns(summarize(current_campaign, ["objective"])).sort_values("spend", ascending=False)
campaign_summary = summarize(current_campaign, ["objective", "campaign"]).sort_values("spend", ascending=False)

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
if not current_search.empty and "objective" in current_search.columns:
    unmapped_spend = current_search.loc[current_search.objective.eq("Other / Unmapped"), "spend"].sum()
    total_spend = current_search["spend"].sum()
    notes.append(f"{percent(unmapped_spend / total_spend if total_spend else 0)} of search term spend is currently unmapped.")
for note in notes or ["Load more model data to populate automated diagnostic readouts."]:
    st.write(f"- {note}")

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(top_n_bar(current_campaign, "campaign", "spend", 10, "Top campaigns by spend"), use_container_width=True)
with col2:
    st.plotly_chart(top_n_bar(current_campaign, "campaign", "priority_conversions", 10, "Top campaigns by priority conversions"), use_container_width=True)

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
    render_data_source_debug(current_campaign)

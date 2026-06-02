import pandas as pd
import streamlit as st

from src.benchmarks import (
    BENCHMARK_TABLE_COLUMNS,
    RECRUITMENT_CAVEAT,
    SUPPRESSED_YOY_STATUSES,
    UNAVAILABLE_MESSAGE,
    add_fallback_yoy_status,
    comparable_yoy_rows,
    get_campaign_type_benchmarks,
    get_default_benchmark_month,
    get_latest_complete_benchmark_month,
    priority_cpa_display,
    yoy_percentage_display,
)
from src.benchmark_cards import render_metric_grid, text_or_empty
from src.filters import render_sidebar
from src.formatting import apply_page_style, kpi_card, money, number
from src.google_sheets import load_workbook
from src.tables import render_table


RECRUITMENT_CAVEAT_MESSAGE = (
    "YoY priority-conversion comparisons are caveated because Applications Submitted "
    "was not consistently tracked before July 2025."
)


def filter_benchmarks(df):
    out = df.copy()
    st.sidebar.header("Benchmark filters")
    for label, column in [("Campaign type", "campaign_type"), ("Objective", "objective")]:
        if column in out.columns:
            selected = st.sidebar.multiselect(label, sorted(out[column].dropna().astype(str).unique()))
            if selected:
                out = out[out[column].astype(str).isin(selected)]
    return out


def display_percent(value):
    if value is None or pd.isna(value):
        return "-"
    return f"{value * 100:+,.1f}%"


def render_campaign_type_cards(df, objective):
    rows = df[df["objective"].astype(str).str.casefold().eq(objective.casefold())]
    st.header(f"{objective} Benchmarks")
    if rows.empty:
        st.info(f"No {objective.lower()} benchmark rows are available for this month.")
        return
    helper = (
        "Priority Conversions combine Apply Now clicks and Enrollment Forms. Forms are the stronger downstream action."
        if objective == "Enrollment"
        else "Applications Submitted are the priority outcome. Career Clicks are shown as a diagnostic intent signal."
    )
    st.caption(helper)
    for _, row in rows.sort_values("campaign_type").iterrows():
        st.subheader(f"{row.get('campaign_type', '')} / {row.get('objective', '')}")
        render_metric_grid(row, objective)
        notes = [text_or_empty(row.get("benchmark_note")), text_or_empty(row.get("yoy_benchmark_note"))]
        notes = [note for note in notes if note]
        if row.get("yoy_benchmark_status") == RECRUITMENT_CAVEAT:
            notes.insert(0, RECRUITMENT_CAVEAT_MESSAGE)
        if notes:
            with st.expander(f"Show notes for {row.get('campaign_type', '')}", expanded=False):
                for note in dict.fromkeys(notes):
                    st.write(f"- {note}")


def benchmark_takeaways(df):
    bullets = []
    for _, row in df.iterrows():
        label = f"{row.get('campaign_type', '')} / {row.get('objective', '')}"
        yoy_status = text_or_empty(row.get("yoy_benchmark_status"))
        recent_status = text_or_empty(row.get("benchmark_status"))
        if yoy_status == RECRUITMENT_CAVEAT:
            bullets.append(RECRUITMENT_CAVEAT_MESSAGE)
        elif row.get("objective") == "Enrollment" and yoy_status == "Better":
            bullets.append(
                f"{label} improved YoY: Priority CPA {yoy_percentage_display(row, 'priority_cpa_yoy_pct')} "
                f"and Priority Conversions {yoy_percentage_display(row, 'priority_conversions_yoy_pct')}."
            )
        elif yoy_status == "Underperforming":
            bullets.append(f"{label} worsened YoY based on the sheet benchmark status.")
        if row.get("objective") == "Enrollment":
            apply_now_clicks = row.get("enrollment_apply_now_clicks")
            enrollment_forms = row.get("enrollment_forms")
            if (
                apply_now_clicks is not None
                and enrollment_forms is not None
                and not pd.isna(apply_now_clicks)
                and not pd.isna(enrollment_forms)
                and apply_now_clicks > 0
                and enrollment_forms / apply_now_clicks < 0.25
            ):
                bullets.append(
                    f"{label} has fewer Enrollment Forms than Apply Now clicks, which may indicate form completion friction."
                )
        if row.get("objective") == "Recruitment":
            career_clicks = row.get("career_clicks")
            applications_submitted = row.get("applications_submitted")
            if (
                career_clicks is not None
                and applications_submitted is not None
                and not pd.isna(career_clicks)
                and not pd.isna(applications_submitted)
                and career_clicks > 0
                and (applications_submitted == 0 or career_clicks / applications_submitted >= 3)
            ):
                bullets.append(
                    f"{label} has Career Clicks that are not translating into Applications Submitted, which may indicate recruitment funnel drop-off."
                )
        if recent_status == "Better":
            bullets.append(f"{label} improved versus its trailing 3-month benchmark.")
        elif recent_status in {"Watch", "Underperforming"}:
            bullets.append(f"{label} deteriorated versus its trailing 3-month benchmark.")
    return list(dict.fromkeys(bullets))


st.set_page_config(page_title="Benchmarking | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Benchmarking")
st.caption("Compare current performance against recent historical norms and prior-year benchmarks by campaign type and objective.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

_ = render_sidebar([], validation)
benchmarks = get_campaign_type_benchmarks(data)
if benchmarks.empty:
    st.info(UNAVAILABLE_MESSAGE)
    st.stop()

benchmarks = filter_benchmarks(benchmarks)
available_months = sorted(benchmarks["month"].dropna().unique(), reverse=True)
if not available_months:
    st.info("No benchmark rows are available with the current filters.")
    st.stop()

default_month = get_default_benchmark_month(benchmarks)
latest_complete_month = get_latest_complete_benchmark_month(benchmarks)
default_index = available_months.index(default_month) if default_month in available_months else 0
selected_month = st.selectbox(
    "Benchmark month",
    available_months,
    index=default_index,
    format_func=lambda value: pd.Timestamp(value).strftime("%b %Y"),
)
selected_month = pd.Timestamp(selected_month)
current_month = pd.Timestamp.today().to_period("M").start_time
if latest_complete_month is None:
    st.warning("No complete benchmark month is available. The latest available month is selected and may be partial.")
if selected_month.to_period("M").start_time == current_month:
    st.warning("This is a partial-month benchmark period and may not be comparable to full historical periods.")

selected = add_fallback_yoy_status(benchmarks[benchmarks["month"].eq(selected_month)].copy())
if selected.empty:
    st.info("No benchmark rows are available for the selected month.")
    st.stop()

st.header("Benchmark Summary Cards")
total_spend = selected.get("spend", pd.Series(dtype=float)).sum()
total_priority_conversions = selected.get("priority_conversions", pd.Series(dtype=float)).sum()
blended_priority_cpa = total_spend / total_priority_conversions if total_priority_conversions else 0
comparable = comparable_yoy_rows(selected)
statuses = comparable.get("yoy_benchmark_status", pd.Series("", index=comparable.index))
comparable = comparable[~statuses.isin(SUPPRESSED_YOY_STATUSES)]
if "priority_cpa_yoy_pct" in comparable.columns:
    improvement = comparable[comparable["priority_cpa_yoy_pct"] < 0].nsmallest(1, "priority_cpa_yoy_pct")
    watchout = comparable[comparable["priority_cpa_yoy_pct"] > 0].nlargest(1, "priority_cpa_yoy_pct")
else:
    improvement, watchout = pd.DataFrame(), pd.DataFrame()
cols = st.columns(6)
with cols[0]: kpi_card("Latest complete benchmark month", latest_complete_month.strftime("%b %Y") if latest_complete_month is not None else "-")
with cols[1]: kpi_card("Total spend", money(total_spend))
with cols[2]: kpi_card("Total priority conversions", number(total_priority_conversions, 1))
with cols[3]: kpi_card("Blended Priority CPA", priority_cpa_display(blended_priority_cpa, total_priority_conversions))
with cols[4]: kpi_card("Biggest YoY improvement", "-" if improvement.empty else f"{improvement.iloc[0].get('campaign_type', '')} / {improvement.iloc[0].get('objective', '')}")
with cols[5]: kpi_card("Biggest YoY watchout", "-" if watchout.empty else f"{watchout.iloc[0].get('campaign_type', '')} / {watchout.iloc[0].get('objective', '')}")

render_campaign_type_cards(selected, "Enrollment")
render_campaign_type_cards(selected, "Recruitment")

st.header("Benchmark Takeaways")
takeaways = benchmark_takeaways(selected)
for takeaway in takeaways:
    st.write(f"- {takeaway}")
if not takeaways:
    st.info("No benchmark takeaways were generated for the selected month.")

with st.expander("Show benchmark source table", expanded=False):
    render_table(
        benchmarks,
        "Benchmark Source Table",
        "Sheet-provided benchmark outputs grouped by month, campaign type, and objective.",
        sort_by=None,
        key="benchmark_source_table",
        display_columns=BENCHMARK_TABLE_COLUMNS,
    )

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
    columns = st.columns(min(len(rows), 4))
    for index, (_, row) in enumerate(rows.sort_values("campaign_type").iterrows()):
        with columns[index % len(columns)]:
            st.markdown(f"**{row.get('campaign_type', '')} / {row.get('objective', '')}**")
            kpi_card("Priority CPA", priority_cpa_display(row.get("priority_cpa"), row.get("priority_conversions")))
            st.caption(f"Priority conversions: {number(row.get('priority_conversions'), 1)}")
            st.caption(f"3Mo Benchmark Status: {row.get('benchmark_status', '-')}")
            st.caption(f"Priority CPA vs 3Mo Median: {display_percent(row.get('priority_cpa_vs_3mo_median'))}")
            st.caption(f"YoY Benchmark Status: {row.get('yoy_benchmark_status', '-')}")
            st.caption(f"Priority CPA YoY: {yoy_percentage_display(row, 'priority_cpa_yoy_pct')}")
            st.caption(f"Priority Conversions YoY: {yoy_percentage_display(row, 'priority_conversions_yoy_pct')}")
            note = str(row.get("yoy_benchmark_note", "") or "").strip()
            if row.get("yoy_benchmark_status") == RECRUITMENT_CAVEAT:
                st.warning(RECRUITMENT_CAVEAT_MESSAGE)
            elif note:
                st.caption(f"YoY note: {note}")


def benchmark_takeaways(df):
    bullets = []
    for _, row in df.iterrows():
        label = f"{row.get('campaign_type', '')} / {row.get('objective', '')}"
        yoy_status = str(row.get("yoy_benchmark_status", "") or "").strip()
        recent_status = str(row.get("benchmark_status", "") or "").strip()
        if yoy_status == RECRUITMENT_CAVEAT:
            bullets.append(RECRUITMENT_CAVEAT_MESSAGE)
        elif row.get("objective") == "Enrollment" and yoy_status == "Better":
            bullets.append(
                f"{label} improved YoY: Priority CPA {yoy_percentage_display(row, 'priority_cpa_yoy_pct')} "
                f"and Priority Conversions {yoy_percentage_display(row, 'priority_conversions_yoy_pct')}."
            )
        elif yoy_status == "Underperforming":
            bullets.append(f"{label} worsened YoY based on the sheet benchmark status.")
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

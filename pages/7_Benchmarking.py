import pandas as pd
import plotly.express as px
import streamlit as st

from src.benchmarks import (
    ACTION_QUEUE_COLUMNS,
    BENCHMARK_TABLE_COLUMNS,
    RECRUITMENT_CAVEAT,
    UNAVAILABLE_MESSAGE,
    comparable_yoy_rows,
    get_benchmark_action_queue,
    get_campaign_type_benchmarks,
    latest_benchmarks,
    recruitment_caveat_present,
)
from src.filters import render_sidebar
from src.formatting import apply_page_style, kpi_card, money, number, signed_percent
from src.google_sheets import load_workbook
from src.tables import render_table


def filter_benchmarks(df):
    out = df.copy()
    st.sidebar.header("Benchmark filters")
    for label, column in [("Campaign type", "campaign_type"), ("Objective", "objective")]:
        if column in out.columns:
            selected = st.sidebar.multiselect(label, sorted(out[column].dropna().astype(str).unique()))
            if selected:
                out = out[out[column].astype(str).isin(selected)]
    return out


def benchmark_bar(df, current_col, benchmark_col, title):
    required = {"campaign_type", "objective", current_col, benchmark_col}
    if df.empty or not required.issubset(df.columns):
        return None
    chart = df.copy()
    chart["campaign_type_objective"] = chart["campaign_type"].astype(str) + " / " + chart["objective"].astype(str)
    chart = chart.melt(
        id_vars="campaign_type_objective",
        value_vars=[current_col, benchmark_col],
        var_name="series",
        value_name="value",
    )
    return px.bar(chart, x="campaign_type_objective", y="value", color="series", barmode="group", title=title)


def yoy_bar(df, metric, title):
    required = {"campaign_type", "objective", metric}
    if df.empty or not required.issubset(df.columns):
        return None
    chart = df.copy()
    chart["campaign_type_objective"] = chart["campaign_type"].astype(str) + " / " + chart["objective"].astype(str)
    fig = px.bar(chart, x="campaign_type_objective", y=metric, color="objective", title=title)
    fig.update_yaxes(tickformat=".1%")
    return fig


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

render_sidebar([], validation)
benchmarks = get_campaign_type_benchmarks(data)
if benchmarks.empty:
    st.info(UNAVAILABLE_MESSAGE)
    st.stop()

benchmarks = filter_benchmarks(benchmarks)
latest = latest_benchmarks(benchmarks)
if latest.empty:
    st.info("No benchmark rows are available with the current filters.")
    st.stop()

st.header("Benchmark Summary Cards")
latest_month = latest["month"].max()
latest_spend = latest.get("spend", pd.Series(dtype=float)).sum()
latest_priority_conversions = latest.get("priority_conversions", pd.Series(dtype=float)).sum()
latest_priority_cpa = latest_spend / latest_priority_conversions if latest_priority_conversions else 0
comparable = comparable_yoy_rows(latest)
if "priority_cpa_yoy_pct" in comparable.columns:
    improvement = comparable[comparable["priority_cpa_yoy_pct"] < 0].nsmallest(1, "priority_cpa_yoy_pct")
    watchout = comparable[comparable["priority_cpa_yoy_pct"] > 0].nlargest(1, "priority_cpa_yoy_pct")
else:
    improvement, watchout = pd.DataFrame(), pd.DataFrame()
cols = st.columns(6)
with cols[0]: kpi_card("Latest month", latest_month.strftime("%b %Y"))
with cols[1]: kpi_card("Spend", money(latest_spend))
with cols[2]: kpi_card("Priority conversions", number(latest_priority_conversions, 1))
with cols[3]: kpi_card("Priority CPA", money(latest_priority_cpa))
with cols[4]:
    if improvement.empty:
        kpi_card("Biggest YoY improvement", "-")
    else:
        row = improvement.iloc[0]
        kpi_card("Biggest YoY improvement", f"{row.get('campaign_type', '')} / {row.get('objective', '')}", signed_percent(row.get("priority_cpa_yoy_pct")))
with cols[5]:
    if watchout.empty:
        kpi_card("Biggest YoY watchout", "-")
    else:
        row = watchout.iloc[0]
        kpi_card("Biggest YoY watchout", f"{row.get('campaign_type', '')} / {row.get('objective', '')}", signed_percent(row.get("priority_cpa_yoy_pct")))

if recruitment_caveat_present(latest):
    st.warning(
        f"{RECRUITMENT_CAVEAT}: Applications Submitted was not consistently tracked before July 2025, "
        "so Recruitment YoY priority-conversion comparisons should be treated cautiously."
    )

st.header("Campaign Type Benchmark Summary")
render_table(benchmarks, "Benchmark Summary", "Sheet-provided benchmark outputs grouped by month, campaign type, and objective.", sort_by=None, key="benchmark_summary", display_columns=BENCHMARK_TABLE_COLUMNS)

st.header("Current vs Trailing 3-Month Benchmark")
left, right = st.columns(2)
with left:
    fig = benchmark_bar(latest, "priority_cpa", "trailing_3mo_median_priority_cpa", "Priority CPA vs trailing 3Mo median")
    st.plotly_chart(fig, use_container_width=True) if fig is not None else st.info("Priority CPA benchmark chart is unavailable.")
with right:
    fig = benchmark_bar(latest, "priority_conversions", "trailing_3mo_median_priority_conversions", "Priority conversions vs trailing 3Mo median")
    st.plotly_chart(fig, use_container_width=True) if fig is not None else st.info("Priority conversion benchmark chart is unavailable.")

st.header("Current vs Prior Year")
left, right = st.columns(2)
with left:
    fig = yoy_bar(latest, "priority_cpa_yoy_pct", "Priority CPA YoY %")
    st.plotly_chart(fig, use_container_width=True) if fig is not None else st.info("Priority CPA YoY chart is unavailable.")
with right:
    fig = yoy_bar(latest, "priority_conversions_yoy_pct", "Priority conversions YoY %")
    st.plotly_chart(fig, use_container_width=True) if fig is not None else st.info("Priority conversions YoY chart is unavailable.")
if {"spend_yoy_pct", "priority_conversions_yoy_pct", "campaign_type", "objective"}.issubset(latest.columns):
    scatter = px.scatter(
        latest,
        x="spend_yoy_pct",
        y="priority_conversions_yoy_pct",
        color="objective",
        hover_name="campaign_type",
        title="Spend YoY % vs priority conversions YoY %",
    )
    scatter.update_xaxes(tickformat=".1%")
    scatter.update_yaxes(tickformat=".1%")
    st.plotly_chart(scatter, use_container_width=True)
else:
    st.info("Spend vs priority conversions YoY scatterplot is unavailable.")

st.header("Benchmark Action Queue")
queue = get_benchmark_action_queue(data, benchmarks)
render_table(queue, "Benchmark Action Queue", "Uses model_benchmark_flags when available; otherwise derives a review queue from Sheet benchmark statuses.", sort_by=None, key="benchmark_action_queue", display_columns=ACTION_QUEUE_COLUMNS)

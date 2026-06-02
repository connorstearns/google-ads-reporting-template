import pandas as pd
import streamlit as st

from .benchmarks import RECRUITMENT_CAVEAT
from .formatting import money, number


ENROLLMENT_METRICS = [
    {"label": "Enrollment Apply Now Clicks", "metric": "enrollment_apply_now_clicks", "kind": "volume", "trailing_benchmark": "trailing_3mo_median_apply_now_clicks", "trailing_delta": "apply_now_clicks_vs_3mo_median", "yoy_benchmark": "prior_year_apply_now_clicks", "yoy_delta": "apply_now_clicks_yoy_pct"},
    {"label": "Enrollment Forms", "metric": "enrollment_forms", "kind": "volume", "trailing_benchmark": "trailing_3mo_median_enrollment_forms", "trailing_delta": "enrollment_forms_vs_3mo_median", "yoy_benchmark": "prior_year_enrollment_forms", "yoy_delta": "enrollment_forms_yoy_pct"},
    {"label": "Priority CPA", "metric": "priority_cpa", "kind": "cost", "denominator": "priority_conversions", "zero_helper": "No priority conversions this period", "trailing_benchmark": "trailing_3mo_median_priority_cpa", "trailing_delta": "priority_cpa_vs_3mo_median", "yoy_benchmark": "prior_year_priority_cpa", "yoy_delta": "priority_cpa_yoy_pct"},
    {"label": "Cost / Enrollment Form", "metric": "cost_per_enrollment_form", "kind": "cost", "denominator": "enrollment_forms", "zero_helper": "No forms this period", "trailing_benchmark": "trailing_3mo_median_cost_per_enrollment_form", "trailing_delta": "cost_per_enrollment_form_vs_3mo_median", "yoy_benchmark": "prior_year_cost_per_enrollment_form", "yoy_delta": "cost_per_enrollment_form_yoy_pct"},
]

RECRUITMENT_METRICS = [
    {"label": "Career Clicks", "metric": "career_clicks", "kind": "volume", "trailing_benchmark": "trailing_3mo_median_career_clicks", "trailing_delta": "career_clicks_vs_3mo_median", "yoy_benchmark": "prior_year_career_clicks", "yoy_delta": "career_clicks_yoy_pct"},
    {"label": "Applications Submitted", "metric": "applications_submitted", "kind": "volume", "trailing_benchmark": "trailing_3mo_median_applications_submitted", "trailing_delta": "applications_submitted_vs_3mo_median", "yoy_benchmark": "prior_year_applications_submitted", "yoy_delta": "applications_submitted_yoy_pct", "recruitment_caveat": True},
    {"label": "Priority CPA", "metric": "priority_cpa", "kind": "cost", "denominator": "priority_conversions", "zero_helper": "No priority conversions this period", "trailing_benchmark": "trailing_3mo_median_priority_cpa", "trailing_delta": "priority_cpa_vs_3mo_median", "yoy_benchmark": "prior_year_priority_cpa", "yoy_delta": "priority_cpa_yoy_pct", "recruitment_caveat": True},
    {"label": "Cost / Application Submitted", "metric": "cost_per_application_submitted", "kind": "cost", "denominator": "applications_submitted", "zero_helper": "No applications this period", "trailing_benchmark": "trailing_3mo_median_cost_per_application_submitted", "trailing_delta": "cost_per_application_submitted_vs_3mo_median", "yoy_benchmark": "prior_year_cost_per_application_submitted", "yoy_delta": "cost_per_application_submitted_yoy_pct", "recruitment_caveat": True},
]


def valid_number(value):
    return value is not None and not pd.isna(value)


def text_or_empty(value):
    return "" if value is None or pd.isna(value) else str(value).strip()


def current_metric_value(row, spec):
    value = row.get(spec["metric"])
    denominator = row.get(spec.get("denominator")) if spec.get("denominator") else None
    if spec.get("denominator") and (not valid_number(denominator) or denominator <= 0):
        return None
    return value if valid_number(value) else None


def benchmark_metric_value(row, spec, period):
    value = row.get(spec[f"{period}_benchmark"])
    return value if valid_number(value) and value > 0 else None


def format_metric_value(value, kind):
    if not valid_number(value):
        return "\u2014"
    return money(value) if kind == "cost" else number(value, 1)


def benchmark_delta(delta, benchmark, unavailable_label):
    if not valid_number(benchmark) or benchmark <= 0 or not valid_number(delta):
        return unavailable_label
    relation = "above" if delta >= 0 else "below"
    return f"{abs(delta) * 100:,.1f}% {relation} benchmark"


def render_metric_card(row, spec):
    current = current_metric_value(row, spec)
    trailing = benchmark_metric_value(row, spec, "trailing")
    yoy = benchmark_metric_value(row, spec, "yoy")
    yoy_status = text_or_empty(row.get("yoy_benchmark_status"))
    trailing_variance = row.get(spec["trailing_delta"])
    trailing_delta = benchmark_delta(trailing_variance, trailing, "Insufficient 3Mo history").replace(" benchmark", " 3Mo benchmark")
    yoy_delta = (
        "YoY tracking caveat"
        if spec.get("recruitment_caveat") and yoy_status == RECRUITMENT_CAVEAT
        else benchmark_delta(row.get(spec["yoy_delta"]), yoy, "No YoY benchmark").replace(" benchmark", " YoY benchmark")
    )
    delta_color = "off" if not valid_number(trailing) or not valid_number(trailing_variance) else ("inverse" if spec["kind"] == "cost" else "normal")
    st.metric(spec["label"], format_metric_value(current, spec["kind"]), delta=trailing_delta, delta_color=delta_color)
    if current is None and spec.get("zero_helper"):
        st.caption(spec["zero_helper"])
    st.caption(f"YoY: {yoy_delta}")
    st.caption(f"3Mo benchmark: {format_metric_value(trailing, spec['kind'])}")
    st.caption(f"YoY benchmark: {format_metric_value(yoy, spec['kind'])}")
    if yoy_delta == "YoY tracking caveat":
        st.warning("YoY tracking caveat")


def render_metric_grid(row, objective):
    specs = ENROLLMENT_METRICS if objective == "Enrollment" else RECRUITMENT_METRICS
    columns = st.columns(4)
    for column, spec in zip(columns, specs):
        with column:
            render_metric_card(row, spec)

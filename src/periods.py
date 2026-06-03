import pandas as pd

from .metrics import safe_divide, summarize


DATE_PRESETS = [
    "Last 7 days",
    "Last week",
    "Last 30 days",
    "Last month",
    "Month to date",
    "Last quarter",
    "Quarter to date",
    "Year to date",
    "Custom range",
]

HIGHER_IS_BETTER = {
    "impressions", "clicks", "total_conversions", "priority_conversions",
    "enrollment_apply_now_clicks", "enrollment_forms", "career_clicks",
    "applications_submitted", "form_share_of_priority",
    "enrollment_priority_conversions", "recruitment_priority_conversions",
    "ctr", "cvr", "apply_now_rate", "form_completion_rate", "click_to_form_rate",
    "career_click_rate", "application_completion_rate", "click_to_application_rate",
    "conversion_quality_ratio", "campaigns_eligible_to_scale",
}
LOWER_IS_BETTER = {
    "cpc", "cpa", "priority_cpa", "cost_per_enrollment_form",
    "cost_per_apply_now_click", "cost_per_enrollment_apply_click",
    "cost_per_application_submitted", "cost_per_application",
    "cost_per_career_click", "career_clicks_per_application",
    "campaigns_to_investigate", "campaigns_to_optimize",
    "campaigns_with_quality_issues", "budget_limited_search_campaigns",
}
NEUTRAL_METRICS = {"spend"}


def get_date_range_from_preset(preset, today):
    today = pd.Timestamp(today).normalize()
    if preset == "Last 7 days":
        return today - pd.Timedelta(days=6), today
    if preset == "Last week":
        current_week_start = today - pd.Timedelta(days=today.weekday())
        start = current_week_start - pd.Timedelta(days=7)
        return start, start + pd.Timedelta(days=6)
    if preset == "Last 30 days":
        return today - pd.Timedelta(days=29), today
    if preset == "Last month":
        start = today.replace(day=1) - pd.DateOffset(months=1)
        end = today.replace(day=1) - pd.Timedelta(days=1)
        return start.normalize(), end.normalize()
    if preset == "Month to date":
        return today.replace(day=1), today
    if preset == "Last quarter":
        current_q_start = pd.Timestamp(year=today.year, month=((today.month - 1) // 3) * 3 + 1, day=1)
        start = current_q_start - pd.DateOffset(months=3)
        end = current_q_start - pd.Timedelta(days=1)
        return start.normalize(), end.normalize()
    if preset == "Quarter to date":
        start = pd.Timestamp(year=today.year, month=((today.month - 1) // 3) * 3 + 1, day=1)
        return start, today
    if preset == "Year to date":
        return pd.Timestamp(year=today.year, month=1, day=1), today
    return None, None


def get_comparison_range(start_date, end_date, preset):
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    if preset in {"Last 7 days", "Last 30 days", "Custom range"}:
        days = (end - start).days + 1
        comp_end = start - pd.Timedelta(days=1)
        return comp_end - pd.Timedelta(days=days - 1), comp_end, "WoW" if preset == "Last 7 days" else ("Previous 30D" if preset == "Last 30 days" else "Prior Period")
    if preset == "Last week":
        return start - pd.Timedelta(days=7), end - pd.Timedelta(days=7), "WoW"
    if preset == "Last month":
        comp_start = start - pd.DateOffset(months=1)
        comp_end = start - pd.Timedelta(days=1)
        return comp_start.normalize(), comp_end.normalize(), "MoM"
    if preset == "Month to date":
        days = (end - start).days
        comp_start = start - pd.DateOffset(months=1)
        comp_end = comp_start + pd.Timedelta(days=days)
        prior_month_end = start - pd.Timedelta(days=1)
        return comp_start.normalize(), min(comp_end.normalize(), prior_month_end.normalize()), "Prior MTD"
    if preset == "Last quarter":
        return (start - pd.DateOffset(months=3)).normalize(), (end - pd.DateOffset(months=3)).normalize(), "QoQ"
    if preset == "Quarter to date":
        days = (end - start).days
        comp_start = (start - pd.DateOffset(months=3)).normalize()
        return comp_start, comp_start + pd.Timedelta(days=days), "Prior QTD"
    if preset == "Year to date":
        return (start - pd.DateOffset(years=1)).normalize(), (end - pd.DateOffset(years=1)).normalize(), "YoY"
    return None, None, "Prior Period"


def calculate_period_metrics(df, start_date, end_date, filters=None):
    if df.empty or "date" not in df.columns:
        return {}
    filters = filters or {}
    out = df.copy()
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out[(out["date"] >= start) & (out["date"] <= end)]
    for col in ["objective", "campaign", "network", "device"]:
        selected = filters.get(col) or []
        if selected and col in out.columns:
            out = out[out[col].isin(selected)]
    if out.empty:
        return _empty_metrics()
    row = summarize(out).iloc[0].to_dict()
    return _derive_section_metrics(row)


def top_kpi_deltas(df, filters, metrics):
    if df.empty or "date" not in df.columns or not filters.get("date_range"):
        return {}
    start, end, comp_start, comp_end, comparison_label = get_filter_comparison_range(filters)
    if start is None or end is None or comp_start is None or comp_end is None:
        return {}
    current = calculate_period_metrics(df, start, end, filters)
    comparison = calculate_period_metrics(df, comp_start, comp_end, filters)
    deltas = {}
    for metric in metrics:
        delta = calculate_metric_delta(current.get(metric), comparison.get(metric), metric_direction(metric))
        text, _, _ = format_delta(delta, f"vs {comparison_label}", metric_direction(metric))
        deltas[metric] = text
    return deltas


def get_filter_comparison_range(filters, preset="Custom range"):
    dates = filters.get("date_range")
    if not dates or len(dates) != 2:
        return None, None, None, None, None
    start = pd.Timestamp(dates[0]).normalize()
    end = pd.Timestamp(dates[1]).normalize()
    preset = infer_comparison_preset(start, end, preset)
    comp_start, comp_end, label = get_comparison_range(start, end, preset)
    return start, end, comp_start, comp_end, comparison_label(label)


def infer_comparison_preset(start, end, preset):
    if preset != "Custom range":
        return preset
    if start.day == 1 and end == (start + pd.offsets.MonthEnd(0)).normalize():
        return "Last month"
    if start.day == 1 and start.to_period("M") == end.to_period("M"):
        return "Month to date"
    return preset


def comparison_label(label):
    labels = {
        "MoM": "prior month",
        "WoW": "prior week",
        "QoQ": "prior quarter",
        "YoY": "same period last year",
        "Previous 30D": "previous 30 days",
        "Prior MTD": "prior month-to-date",
        "Prior QTD": "prior quarter-to-date",
        "Prior Period": "prior period",
    }
    return labels.get(label, str(label or "prior period"))


def calculate_metric_delta(current_value, comparison_value, metric_direction):
    if comparison_value is None or pd.isna(comparison_value) or comparison_value == 0:
        return None
    if current_value is None or pd.isna(current_value):
        return None
    return (current_value - comparison_value) / comparison_value


def format_delta(delta, comparison_label, metric_direction):
    if delta is None or pd.isna(delta):
        return None, "off", "No comparison data"
    color = "off"
    if metric_direction == "higher":
        color = "normal"
    elif metric_direction == "lower":
        color = "inverse"
    return f"{delta * 100:+,.1f}% {comparison_label}", color, None


def metric_direction(metric):
    if metric in HIGHER_IS_BETTER:
        return "higher"
    if metric in LOWER_IS_BETTER:
        return "lower"
    return "neutral"


def _empty_metrics():
    return _derive_section_metrics({})


def _derive_section_metrics(row):
    def numeric(key, fallback=0):
        value = row.get(key, fallback)
        numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return 0 if pd.isna(numeric_value) else numeric_value

    spend = numeric("spend")
    clicks = numeric("clicks")
    enrollment_apply = numeric("enrollment_apply_now_clicks", row.get("enrollment_apply_clicks", 0))
    enrollment_forms = numeric("enrollment_forms")
    applications = numeric("applications_submitted")
    career_clicks = numeric("career_clicks")
    enrollment_priority = enrollment_apply + enrollment_forms
    recruitment_priority = applications
    metrics = dict(row)
    metrics["enrollment_priority_conversions"] = enrollment_priority
    metrics["recruitment_priority_conversions"] = recruitment_priority
    metrics["cost_per_apply_now_click"] = float(safe_divide(spend, enrollment_apply))
    metrics["cost_per_enrollment_apply_click"] = metrics["cost_per_apply_now_click"]
    metrics["cost_per_enrollment_form"] = float(safe_divide(spend, enrollment_forms))
    metrics["cost_per_career_click"] = float(safe_divide(spend, career_clicks))
    metrics["cost_per_application_submitted"] = float(safe_divide(spend, applications))
    metrics["cost_per_application"] = metrics["cost_per_application_submitted"]
    metrics["apply_now_rate"] = float(safe_divide(enrollment_apply, clicks))
    metrics["form_completion_rate"] = float(safe_divide(enrollment_forms, enrollment_apply))
    metrics["click_to_form_rate"] = float(safe_divide(enrollment_forms, clicks))
    metrics["career_click_rate"] = float(safe_divide(career_clicks, clicks))
    metrics["application_completion_rate"] = float(safe_divide(applications, career_clicks))
    metrics["click_to_application_rate"] = float(safe_divide(applications, clicks))
    metrics["form_share_of_priority"] = float(safe_divide(enrollment_forms, enrollment_priority))
    metrics["career_clicks_per_application"] = float(safe_divide(career_clicks, applications))
    return metrics

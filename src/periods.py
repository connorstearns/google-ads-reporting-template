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
}
LOWER_IS_BETTER = {
    "cpc", "cpa", "priority_cpa", "cost_per_enrollment_form",
    "cost_per_application_submitted", "career_clicks_per_application",
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
    dates = filters.get("date_range")
    if len(dates) != 2:
        return {}
    start = pd.Timestamp(dates[0]).normalize()
    end = pd.Timestamp(dates[1]).normalize()
    days = (end - start).days + 1
    comp_end = start - pd.Timedelta(days=1)
    comp_start = comp_end - pd.Timedelta(days=days - 1)
    current = calculate_period_metrics(df, start, end, filters)
    comparison = calculate_period_metrics(df, comp_start, comp_end, filters)
    deltas = {}
    for metric in metrics:
        delta = calculate_metric_delta(current.get(metric), comparison.get(metric), metric_direction(metric))
        text, _, _ = format_delta(delta, "prior period", metric_direction(metric))
        deltas[metric] = text
    return deltas


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
    spend = row.get("spend", 0)
    enrollment_apply = row.get("enrollment_apply_now_clicks", row.get("enrollment_apply_clicks", 0))
    enrollment_forms = row.get("enrollment_forms", 0)
    applications = row.get("applications_submitted", 0)
    career_clicks = row.get("career_clicks", 0)
    enrollment_priority = enrollment_apply + enrollment_forms
    recruitment_priority = applications
    metrics = dict(row)
    metrics["enrollment_priority_conversions"] = enrollment_priority
    metrics["recruitment_priority_conversions"] = recruitment_priority
    metrics["cost_per_enrollment_form"] = float(safe_divide(spend, enrollment_forms))
    metrics["cost_per_application_submitted"] = float(safe_divide(spend, applications))
    metrics["form_share_of_priority"] = float(safe_divide(enrollment_forms, enrollment_priority))
    metrics["career_clicks_per_application"] = float(safe_divide(career_clicks, applications))
    return metrics

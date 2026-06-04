import math

import pandas as pd


FLAT_THRESHOLD = 0.05
MEANINGFUL_THRESHOLD = 0.05


def _safe_number(value):
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def pct_change(current, previous):
    current_value = _safe_number(current)
    previous_value = _safe_number(previous)
    if current_value is None or previous_value is None or previous_value == 0:
        return None
    return (current_value - previous_value) / previous_value


def direction_label(metric_name, delta, lower_is_better=False):
    if delta is None or pd.isna(delta):
        return "unavailable"
    if abs(delta) <= FLAT_THRESHOLD:
        return "stable"
    if lower_is_better:
        return "improved" if delta < 0 else "worsened"
    return "improved" if delta > 0 else "worsened"


def _trend(current_metrics, comparison_metrics, metric):
    return pct_change(_metric(current_metrics, metric), _metric(comparison_metrics, metric))


def _metric(metrics, metric):
    if not metrics:
        return None
    if hasattr(metrics, "get"):
        return metrics.get(metric)
    return None


def _is_up(delta):
    return delta is not None and delta > MEANINGFUL_THRESHOLD


def _is_down(delta):
    return delta is not None and delta < -MEANINGFUL_THRESHOLD


def _is_flat_or_down(delta):
    return delta is not None and delta <= MEANINGFUL_THRESHOLD


def _is_flat_or_up(delta):
    return delta is not None and delta >= -MEANINGFUL_THRESHOLD


def _is_flat_or_down_or_missing(delta):
    return delta is None or delta <= MEANINGFUL_THRESHOLD


def _add_takeaway(takeaways, key, severity, text, priority):
    if key in {takeaway["key"] for takeaway in takeaways}:
        return
    takeaways.append({
        "key": key,
        "severity": severity,
        "text": text,
        "priority": priority,
    })


def _has_comparison_data(comparison_metrics, metrics):
    if not comparison_metrics:
        return False
    return any(_safe_number(_metric(comparison_metrics, metric)) not in (None, 0) for metric in metrics)


def _finalize_takeaways(takeaways, comparison_label):
    if not takeaways:
        return [{
            "severity": "neutral",
            "text": f"Performance was broadly stable versus {comparison_label}; continue monitoring tactic-level mix and conversion quality.",
        }]
    return [
        {"severity": takeaway["severity"], "text": takeaway["text"]}
        for takeaway in sorted(takeaways, key=lambda item: item["priority"])[:3]
    ]


def generate_objective_takeaways(objective_name, current_metrics, comparison_metrics, comparison_label):
    if objective_name == "Enrollment":
        return generate_enrollment_takeaways(current_metrics, comparison_metrics, comparison_label)
    if objective_name == "Recruitment":
        return generate_recruitment_takeaways(current_metrics, comparison_metrics, comparison_label)
    return [{"severity": "neutral", "text": "Comparison data is not available for this period."}]


def generate_enrollment_takeaways(current_metrics, comparison_metrics, comparison_label):
    metrics = [
        "spend", "clicks", "enrollment_apply_now_clicks", "enrollment_forms",
        "enrollment_priority_conversions", "apply_now_rate", "form_completion_rate",
        "click_to_form_rate", "cost_per_apply_now_click", "cost_per_enrollment_form",
        "priority_cpa",
    ]
    if not _has_comparison_data(comparison_metrics, metrics):
        return [{"severity": "neutral", "text": "Comparison data is not available for this period."}]

    spend = _trend(current_metrics, comparison_metrics, "spend")
    clicks = _trend(current_metrics, comparison_metrics, "clicks")
    apply_now_clicks = _trend(current_metrics, comparison_metrics, "enrollment_apply_now_clicks")
    forms = _trend(current_metrics, comparison_metrics, "enrollment_forms")
    form_completion = _trend(current_metrics, comparison_metrics, "form_completion_rate")
    click_to_form = _trend(current_metrics, comparison_metrics, "click_to_form_rate")
    cost_per_form = _trend(current_metrics, comparison_metrics, "cost_per_enrollment_form")

    takeaways = []
    if _is_up(forms) and _is_down(cost_per_form):
        _add_takeaway(takeaways, "strong_efficiency", "positive", f"Enrollment form volume increased while cost per form declined, indicating stronger enrollment efficiency versus {comparison_label}.", 1)
    if _is_up(cost_per_form):
        _add_takeaway(takeaways, "cpa_worsened", "warning", "Cost per enrollment form increased, so recent gains should be reviewed against landing page performance and query/campaign mix.", 1)
    if _is_up(apply_now_clicks) and (_is_flat_or_down_or_missing(forms) or _is_down(form_completion)):
        _add_takeaway(takeaways, "interest_lag", "warning", "Apply Now interest improved, but form submissions did not keep pace, suggesting potential friction in the form or landing page flow.", 2)
    if _is_down(click_to_form):
        _add_takeaway(takeaways, "funnel_deterioration", "warning", "Click-to-form rate declined, indicating a weaker path from traffic to completed enrollment action.", 2)
    if _is_up(clicks) and _is_flat_or_down_or_missing(apply_now_clicks):
        _add_takeaway(takeaways, "traffic_quality", "warning", "Traffic increased, but Apply Now clicks did not keep pace, suggesting traffic quality or landing page CTA alignment should be reviewed.", 3)
    if _is_up(forms) and _is_down(cost_per_form) and _is_flat_or_up(form_completion):
        _add_takeaway(takeaways, "scale_signal", "positive", "Enrollment performance shows a scale signal: form volume increased, efficiency improved, and completion rate held or strengthened.", 4)
    if _is_up(spend) and _is_up(forms) and _is_flat_or_down(cost_per_form):
        _add_takeaway(takeaways, "efficient_scaling", "positive", "Enrollment spend increased while form efficiency held or improved, suggesting the added budget is translating into qualified enrollment outcomes.", 4)
    if _is_down(spend) and _is_up(forms):
        _add_takeaway(takeaways, "spend_down_forms_up", "positive", "Enrollment forms increased despite lower spend, indicating the campaigns are reaching likely applicants more efficiently.", 4)

    return _finalize_takeaways(takeaways, comparison_label)


def generate_recruitment_takeaways(current_metrics, comparison_metrics, comparison_label):
    metrics = [
        "spend", "clicks", "career_clicks", "applications_submitted",
        "recruitment_priority_conversions", "career_click_rate",
        "application_completion_rate", "click_to_application_rate",
        "cost_per_career_click", "cost_per_application_submitted", "priority_cpa",
    ]
    if not _has_comparison_data(comparison_metrics, metrics):
        return [{"severity": "neutral", "text": "Comparison data is not available for this period."}]

    spend = _trend(current_metrics, comparison_metrics, "spend")
    clicks = _trend(current_metrics, comparison_metrics, "clicks")
    career_clicks = _trend(current_metrics, comparison_metrics, "career_clicks")
    applications = _trend(current_metrics, comparison_metrics, "applications_submitted")
    application_completion = _trend(current_metrics, comparison_metrics, "application_completion_rate")
    click_to_application = _trend(current_metrics, comparison_metrics, "click_to_application_rate")
    cost_per_application = _trend(current_metrics, comparison_metrics, "cost_per_application_submitted")

    takeaways = []
    if _is_up(applications) and _is_down(cost_per_application):
        _add_takeaway(takeaways, "strong_efficiency", "positive", f"Applications increased while cost per application declined, indicating stronger recruitment efficiency versus {comparison_label}.", 1)
    if _is_up(cost_per_application):
        _add_takeaway(takeaways, "cpa_worsened", "warning", "Cost per application increased, so recent recruitment gains should be reviewed against candidate quality, query mix, and application flow.", 1)
    if _is_up(career_clicks) and (_is_flat_or_down_or_missing(applications) or _is_down(application_completion)):
        _add_takeaway(takeaways, "interest_lag", "warning", "Career clicks increased, but submitted applications did not keep pace, suggesting potential friction in the job or application flow.", 2)
    if _is_down(click_to_application):
        _add_takeaway(takeaways, "funnel_deterioration", "warning", "Click-to-application rate declined, indicating a weaker path from traffic to submitted applications.", 2)
    if _is_up(clicks) and _is_flat_or_down_or_missing(career_clicks):
        _add_takeaway(takeaways, "traffic_quality", "warning", "Traffic increased, but career clicks did not keep pace, suggesting landing page relevance or CTA clarity should be reviewed.", 3)
    if _is_up(applications) and _is_down(cost_per_application) and _is_flat_or_up(application_completion):
        _add_takeaway(takeaways, "scale_signal", "positive", "Recruitment performance shows a scale signal: application volume increased, efficiency improved, and completion rate held or strengthened.", 4)
    if _is_up(spend) and _is_up(applications) and _is_flat_or_down(cost_per_application):
        _add_takeaway(takeaways, "efficient_scaling", "positive", "Recruitment spend increased while application efficiency held or improved, suggesting the added budget is producing qualified recruitment outcomes.", 4)
    if _is_down(spend) and _is_up(applications):
        _add_takeaway(takeaways, "spend_down_applications_up", "positive", "Applications increased despite lower spend, indicating the campaigns are reaching prospective candidates more efficiently.", 4)

    return _finalize_takeaways(takeaways, comparison_label)

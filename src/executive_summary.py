import pandas as pd
import streamlit as st

from src.benchmarks import (
    RECRUITMENT_CAVEAT,
    UNAVAILABLE_MESSAGE,
    get_campaign_type_benchmarks,
    latest_complete_benchmarks,
    recruitment_caveat_present,
)
from src.formatting import apply_page_style, get_delta_color_mode
from src.google_sheets import clear_data_cache, load_workbook
from src.transforms import combine_primary_data
from src.filters import multiselect_if_available, show_validation
from src.metrics import summarize
from src.periods import (
    DATE_PRESETS,
    calculate_metric_delta,
    calculate_period_metrics,
    format_delta,
    get_comparison_range,
    get_date_range_from_preset,
    latest_complete_month_range,
    metric_direction,
)
from src.formatting import render_data_source_debug


ACCOUNT_CARDS = [
    ("Spend", "spend", "currency", None),
    ("Impressions", "impressions", "number", None),
    ("Clicks", "clicks", "number", None),
    ("CTR", "ctr", "percent", None),
    ("CPC", "cpc", "currency2", "clicks"),
]
ENROLLMENT_CARDS = [
    ("Enrollment Apply Now Clicks", "enrollment_apply_now_clicks", "number1", None),
    ("Enrollment Forms", "enrollment_forms", "number1", None),
    ("Cost / Enrollment Form", "cost_per_enrollment_form", "currency", "enrollment_forms"),
    ("Form Share of Priority", "form_share_of_priority", "percent", "enrollment_priority_conversions"),
]
RECRUITMENT_CARDS = [
    ("Career Clicks", "career_clicks", "number1", None),
    ("Applications Submitted", "applications_submitted", "number1", None),
    ("Cost / Application Submitted", "cost_per_application_submitted", "currency", "applications_submitted"),
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
    min_date = campaign["date"].min().date() if "date" in campaign.columns and campaign["date"].notna().any() else today.date()
    max_date = campaign["date"].max().date() if "date" in campaign.columns and campaign["date"].notna().any() else today.date()
    latest_start, latest_end, latest_is_partial = latest_complete_month_range(max_date, min_date)
    preset = st.sidebar.selectbox("Date preset", DATE_PRESETS, index=0)
    if preset == "Custom range" and "date" in campaign.columns and campaign["date"].notna().any():
        selected = st.sidebar.date_input("Custom range", (latest_start.date(), latest_end.date()), min_value=min_date, max_value=max_date)
        start, end = (pd.Timestamp(selected[0]), pd.Timestamp(selected[1])) if len(selected) == 2 else (pd.Timestamp(min_date), pd.Timestamp(max_date))
    else:
        start, end = get_date_range_from_preset(preset, today, min_date)
    st.sidebar.caption(f"Current period: {start:%b %d, %Y} - {end:%b %d, %Y}")
    comp_start, comp_end, comparison_label = get_comparison_range(start, end, preset)
    st.sidebar.caption(f"Comparison: {comp_start:%b %d, %Y} - {comp_end:%b %d, %Y}")
    st.sidebar.caption(f"Data through {pd.Timestamp(max_date):%b %d, %Y}")
    with st.sidebar.expander("Data status", expanded=False):
        st.caption(f"Data through: {pd.Timestamp(max_date):%b %d, %Y}")
        st.caption(f"Latest complete month: {latest_start:%b %d, %Y} - {latest_end:%b %d, %Y}")
        if latest_is_partial:
            st.warning("Only partial current-month data is available; the default period is partial.")
        st.caption(f"Selected period: {start:%b %d, %Y} - {end:%b %d, %Y}")
        st.caption(f"Comparison period: {comp_start:%b %d, %Y} - {comp_end:%b %d, %Y}")
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


def as_number(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        numeric = pd.to_numeric(value, errors="coerce")
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return float(numeric)


def format_number(value, decimals=0):
    numeric = as_number(value)
    if numeric is None:
        return "\u2014"
    return f"{numeric:,.{decimals}f}"


def format_currency(value, decimals=0):
    numeric = as_number(value)
    if numeric is None:
        return "\u2014"
    return f"${numeric:,.{decimals}f}"


def format_percent(value, decimals=1):
    numeric = as_number(value)
    if numeric is None:
        return "\u2014"
    return f"{numeric * 100:,.{decimals}f}%"


def format_value(metrics, key, kind, denominator_key=None):
    value = metrics.get(key)
    if denominator_key and metrics.get(denominator_key, 0) <= 0:
        return "\u2014"
    if kind == "currency":
        return format_currency(value)
    if kind == "currency2":
        return format_currency(value, 2)
    if kind == "percent":
        return format_percent(value)
    if kind == "number1":
        return format_number(value, 1)
    if kind == "ratio":
        return format_number(value, 1)
    return format_number(value)


def render_period_cards(title, current_metrics, comparison_metrics, card_specs, comparison_label, columns=3):
    st.subheader(title)
    cols = st.columns(columns)
    for index, (label, metric, kind, denominator) in enumerate(card_specs):
        current = current_metrics.get(metric)
        comparison = comparison_metrics.get(metric)
        direction = metric_direction(metric)
        delta = calculate_metric_delta(current, comparison, direction)
        delta_text, _, helper = format_delta(delta, comparison_label, direction)
        delta_color = get_delta_color_mode(label, kind, direction == "lower", delta)
        with cols[index % columns]:
            st.metric(
                label,
                format_value(current_metrics, metric, kind, denominator),
                delta=delta_text,
                delta_color=delta_color,
            )
            st.caption(f"{comparison_label}: {format_value(comparison_metrics, metric, kind, denominator)}")
            if helper:
                st.caption(helper)


def is_material(delta, threshold=0.1):
    return delta is not None and not pd.isna(delta) and abs(delta) >= threshold


def callout_delta(current, comparison, metric, label, comparison_label, improved_text, worsened_text):
    delta = calculate_metric_delta(current, comparison, metric_direction(metric))
    if not is_material(delta):
        return None
    direction = metric_direction(metric)
    improved = delta < 0 if direction == "lower" else delta > 0
    direction_text = improved_text if improved else worsened_text
    return f"{label} {direction_text} ({delta * 100:+,.1f}% {comparison_label})."


def build_executive_callouts(current, comparison, enrollment_current, enrollment_comparison, recruitment_current, recruitment_comparison, comparison_label):
    candidates = [
        callout_delta(current.get("spend"), comparison.get("spend"), "spend", "Spend", comparison_label, "increased materially", "decreased materially"),
        callout_delta(current.get("cpc"), comparison.get("cpc"), "cpc", "CPC", comparison_label, "improved", "worsened"),
        callout_delta(enrollment_current.get("enrollment_forms"), enrollment_comparison.get("enrollment_forms"), "enrollment_forms", "Enrollment Forms", comparison_label, "increased", "decreased"),
        callout_delta(enrollment_current.get("cost_per_enrollment_form"), enrollment_comparison.get("cost_per_enrollment_form"), "cost_per_enrollment_form", "Cost / Enrollment Form", comparison_label, "improved", "worsened"),
        callout_delta(recruitment_current.get("applications_submitted"), recruitment_comparison.get("applications_submitted"), "applications_submitted", "Applications Submitted", comparison_label, "increased", "decreased"),
        callout_delta(recruitment_current.get("cost_per_application_submitted"), recruitment_comparison.get("cost_per_application_submitted"), "cost_per_application_submitted", "Cost / Application Submitted", comparison_label, "improved", "worsened"),
    ]
    if recruitment_current.get("career_clicks", 0) >= 10 and recruitment_current.get("applications_submitted", 0) <= 1:
        candidates.append("Career Clicks are high but Applications Submitted are weak, suggesting possible recruitment funnel drop-off.")
    return [item for item in candidates if item][:5]


def render_executive_callouts(current, comparison, enrollment_current, enrollment_comparison, recruitment_current, recruitment_comparison, comparison_label):
    st.subheader("Executive Callouts")
    callouts = build_executive_callouts(current, comparison, enrollment_current, enrollment_comparison, recruitment_current, recruitment_comparison, comparison_label)
    if not callouts:
        st.info("No major period-over-period callouts for the selected period.")
        return
    for item in callouts:
        st.write(f"- {item}")


def benchmark_value(row, metric):
    value = row.get(metric)
    if value is None or pd.isna(value):
        return "—"
    return f"{value * 100:+,.1f}%" if "pct" in metric or "vs_3mo" in metric else format_number(value, 1)


def render_compact_benchmark_snapshot(latest):
    st.caption("Latest complete benchmark month. These are benchmark deltas, separate from the period-over-period KPI deltas above.")
    targets = [
        ("Nonbrand Search", "Enrollment", [
            ("Enrollment Forms vs 3Mo", "enrollment_forms_vs_3mo_median"),
            ("Cost / Enrollment Form vs 3Mo", "cost_per_enrollment_form_vs_3mo_median"),
            ("Enrollment Forms YoY", "enrollment_forms_yoy_pct"),
            ("Cost / Enrollment Form YoY", "cost_per_enrollment_form_yoy_pct"),
        ]),
        ("Nonbrand Search", "Recruitment", [
            ("Applications Submitted vs 3Mo", "applications_submitted_vs_3mo_median"),
            ("Cost / Application Submitted vs 3Mo", "cost_per_application_submitted_vs_3mo_median"),
        ]),
    ]
    if latest["campaign_type"].astype(str).str.casefold().eq("performance max").any():
        targets += [
            ("Performance Max", "Enrollment", [
                ("Enrollment Forms vs 3Mo", "enrollment_forms_vs_3mo_median"),
                ("Cost / Enrollment Form vs 3Mo", "cost_per_enrollment_form_vs_3mo_median"),
                ("Enrollment Forms YoY", "enrollment_forms_yoy_pct"),
                ("Cost / Enrollment Form YoY", "cost_per_enrollment_form_yoy_pct"),
            ]),
            ("Performance Max", "Recruitment", [
                ("Applications Submitted vs 3Mo", "applications_submitted_vs_3mo_median"),
                ("Cost / Application Submitted vs 3Mo", "cost_per_application_submitted_vs_3mo_median"),
            ]),
        ]
    for campaign_type, objective, metrics in targets:
        matched = latest[
            latest["campaign_type"].astype(str).str.casefold().eq(campaign_type.casefold())
            & latest["objective"].astype(str).str.casefold().eq(objective.casefold())
        ]
        if matched.empty:
            continue
        row = matched.iloc[0]
        st.markdown(f"**{campaign_type} / {objective}**")
        cols = st.columns(len(metrics))
        for col, (label, metric) in zip(cols, metrics):
            with col:
                st.metric(label, benchmark_value(row, metric))
        if objective == "Recruitment" and row.get("yoy_benchmark_status") == RECRUITMENT_CAVEAT:
            st.warning("Recruitment YoY tracking caveat: Applications Submitted was not consistently tracked before July 2025.")


def summarize_campaigns(df):
    if df.empty:
        return pd.DataFrame()
    return summarize(df, ["objective", "campaign"]).sort_values("spend", ascending=False)


def build_campaign_watchouts(df):
    summary = summarize_campaigns(df)
    if summary.empty:
        return []
    watchouts = []
    top_spend = summary.iloc[0]
    watchouts.append(("Highest spend campaign", top_spend["campaign"], format_currency(top_spend["spend"])))
    enrollment = summary[summary["objective"].eq("Enrollment")].copy()
    if not enrollment.empty:
        best_forms = enrollment[enrollment["enrollment_forms"] > 0].sort_values("cost_per_enrollment_form").head(1)
        if not best_forms.empty:
            row = best_forms.iloc[0]
            watchouts.append(("Best cost / Enrollment Form", row["campaign"], format_currency(row["cost_per_enrollment_form"])))
    recruitment = summary[summary["objective"].eq("Recruitment")].copy()
    if not recruitment.empty:
        best_apps = recruitment[recruitment["applications_submitted"] > 0].sort_values("cost_per_application_submitted").head(1)
        if not best_apps.empty:
            row = best_apps.iloc[0]
            watchouts.append(("Best cost / Application Submitted", row["campaign"], format_currency(row["cost_per_application_submitted"])))
    weak = summary[(summary["spend"] > 0) & (summary["enrollment_forms"].fillna(0) + summary["applications_submitted"].fillna(0) == 0)].head(1)
    if not weak.empty:
        row = weak.iloc[0]
        watchouts.append(("High spend, low downstream outcomes", row["campaign"], format_currency(row["spend"])))
    weak_clicks = summary[(summary["clicks"] >= 20) & (summary["enrollment_forms"].fillna(0) + summary["applications_submitted"].fillna(0) == 0)].sort_values("clicks", ascending=False).head(1)
    if not weak_clicks.empty:
        row = weak_clicks.iloc[0]
        watchouts.append(("Clicks with weak form/application volume", row["campaign"], format_number(row["clicks"])))
    return watchouts[:5]


def render_campaign_watchouts(df):
    st.subheader("Campaign Watchouts")
    watchouts = build_campaign_watchouts(df)
    if not watchouts:
        st.info("No campaign watchouts for the selected period.")
        return
    cols = st.columns(min(len(watchouts), 3))
    for index, (label, campaign_name, value) in enumerate(watchouts):
        with cols[index % len(cols)]:
            st.metric(label, value)
            st.caption(campaign_name)


def main():
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
    render_executive_callouts(current_metrics, comparison_metrics, enrollment_current, enrollment_comparison, recruitment_current, recruitment_comparison, comparison_label)
    render_period_cards("Enrollment Performance", enrollment_current, enrollment_comparison, ENROLLMENT_CARDS, comparison_label, columns=3)
    render_period_cards("Recruitment Performance", recruitment_current, recruitment_comparison, RECRUITMENT_CARDS, comparison_label, columns=3)

    st.subheader("Performance vs Benchmarks")
    benchmarks = get_campaign_type_benchmarks(data)
    latest, benchmark_month_used, used_incomplete_fallback = latest_complete_benchmarks(benchmarks)
    if latest.empty:
        st.info(UNAVAILABLE_MESSAGE)
    else:
        if used_incomplete_fallback:
            st.warning("No complete benchmark month is available. Benchmark cards are using the latest available month, which may be partial.")
        st.caption(f"Benchmark month: {benchmark_month_used:%b %Y}")
        render_compact_benchmark_snapshot(latest)
        if recruitment_caveat_present(latest):
            st.warning(
                f"{RECRUITMENT_CAVEAT}: Applications Submitted was not consistently tracked before July 2025, "
                "so Recruitment YoY priority-conversion comparisons should be treated cautiously."
            )

    render_campaign_watchouts(current_campaign)

    with st.expander("Data Source Debug", expanded=False):
        render_data_source_debug(current_campaign)


if __name__ == "__main__":
    main()

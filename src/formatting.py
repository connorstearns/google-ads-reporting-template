import math
import pandas as pd
import streamlit as st


PRIORITY_CONVERSIONS_HELP = (
    "Priority Conversions are the main optimization actions for HCZ. Enrollment priority conversions are "
    "Apply Now clicks and Enrollment Forms. Recruitment priority conversions are Applications Submitted."
)


def money(value, decimals=0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"${value:,.{decimals}f}"


def number(value, decimals=0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value:,.{decimals}f}"


def percent(value, decimals=2):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value * 100:,.{decimals}f}%"


def signed_percent(value, decimals=1):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return f"{value * 100:+,.{decimals}f}%"


def apply_page_style():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 12px 14px;
        }
        .hcz-muted {color: #64748b; font-size: 0.95rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label, value, delta=None, help_text=None):
    st.metric(label=label, value=value, delta=delta, help=help_text)


def metric_column_config():
    return {
        "spend": st.column_config.NumberColumn("Spend", format="$%.0f"),
        "cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
        "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
        "cpa": st.column_config.NumberColumn("CPA", format="$%.0f"),
        "priority_cpa": st.column_config.NumberColumn("Priority CPA", format="$%.0f"),
        "campaign_type_priority_cpa_benchmark": st.column_config.NumberColumn("Campaign Type Priority CPA Benchmark", format="$%.0f"),
        "prior_year_priority_cpa": st.column_config.NumberColumn("Prior Year Priority CPA", format="$%.0f"),
        "trailing_3mo_median_priority_cpa": st.column_config.NumberColumn("Trailing 3Mo Median Priority CPA", format="$%.0f"),
        "trailing_3mo_median_priority_conversions": st.column_config.NumberColumn("Trailing 3Mo Median Priority Conversions", format="%.1f"),
        "cost_per_enrollment_apply_click": st.column_config.NumberColumn("Cost per Apply Now Click", format="$%.0f"),
        "cost_per_enrollment_form": st.column_config.NumberColumn("Cost per Enrollment Form", format="$%.0f"),
        "cost_per_application_submitted": st.column_config.NumberColumn("Cost per Application Submitted", format="$%.0f"),
        "cost_per_career_click": st.column_config.NumberColumn("Cost per Career Click", format="$%.0f"),
        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
        "cvr": st.column_config.NumberColumn("CVR", format="%.2f%%"),
        "spend_share": st.column_config.NumberColumn("Spend Share", format="%.1f%%"),
        "click_share": st.column_config.NumberColumn("Click Share", format="%.1f%%"),
        "conversion_share": st.column_config.NumberColumn("Conversion Share", format="%.1f%%"),
        "impressions": st.column_config.NumberColumn("Impressions", format="%d"),
        "clicks": st.column_config.NumberColumn("Clicks", format="%d"),
        "conversions": st.column_config.NumberColumn("Conversions", format="%.1f"),
        "reported_conversions": st.column_config.NumberColumn("Reported Conversions", format="%.1f"),
        "all_conversions": st.column_config.NumberColumn("All Conversions", format="%.1f"),
        "total_conversions": st.column_config.NumberColumn("Total Conversions", format="%.1f"),
        "priority_conversions": st.column_config.NumberColumn("Priority Conversions", format="%.1f"),
        "enrollment_apply_now_clicks": st.column_config.NumberColumn("Enrollment Apply Now Clicks", format="%.1f"),
        "enrollment_forms": st.column_config.NumberColumn("Enrollment Forms", format="%.1f"),
        "career_clicks": st.column_config.NumberColumn("Career Clicks", format="%.1f"),
        "applications_submitted": st.column_config.NumberColumn("Applications Submitted", format="%.1f"),
        "other_micro_conversions": st.column_config.NumberColumn("Other / Micro Conversions", format="%.1f"),
        "micro_conversions": st.column_config.NumberColumn("Micro Conversions", format="%.1f"),
        "all_to_reported_conversion_ratio": st.column_config.NumberColumn("All / Reported Conversion Ratio", format="%.2f"),
        "priority_score": st.column_config.NumberColumn("Priority Score", format="%d"),
        "spend_yoy_pct": st.column_config.NumberColumn("Spend YoY %", format="%.1f%%"),
        "clicks_yoy_pct": st.column_config.NumberColumn("Clicks YoY %", format="%.1f%%"),
        "priority_conversions_yoy_pct": st.column_config.NumberColumn("Priority Conversions YoY %", format="%.1f%%"),
        "priority_cpa_yoy_pct": st.column_config.NumberColumn("Priority CPA YoY %", format="%.1f%%"),
        "priority_cpa_vs_3mo_median": st.column_config.NumberColumn("Priority CPA vs 3Mo Median", format="%.1f%%"),
        "priority_cpa_vs_3mo_benchmark": st.column_config.NumberColumn("Priority CPA vs 3Mo Benchmark", format="%.1f%%"),
        "priority_conversions_vs_3mo_median": st.column_config.NumberColumn("Priority Conversions vs 3Mo Median", format="%.1f%%"),
        "apply_now_clicks_yoy_pct": st.column_config.NumberColumn("Apply Now Clicks YoY %", format="%.1f%%"),
        "apply_now_clicks_vs_3mo_median": st.column_config.NumberColumn("Apply Now Clicks vs 3Mo Median", format="%.1f%%"),
        "enrollment_forms_yoy_pct": st.column_config.NumberColumn("Enrollment Forms YoY %", format="%.1f%%"),
        "enrollment_forms_vs_3mo_median": st.column_config.NumberColumn("Enrollment Forms vs 3Mo Median", format="%.1f%%"),
        "cost_per_enrollment_form_yoy_pct": st.column_config.NumberColumn("Cost per Enrollment Form YoY %", format="%.1f%%"),
        "cost_per_enrollment_form_vs_3mo_median": st.column_config.NumberColumn("Cost per Enrollment Form vs 3Mo Median", format="%.1f%%"),
        "career_clicks_yoy_pct": st.column_config.NumberColumn("Career Clicks YoY %", format="%.1f%%"),
        "career_clicks_vs_3mo_median": st.column_config.NumberColumn("Career Clicks vs 3Mo Median", format="%.1f%%"),
        "applications_submitted_yoy_pct": st.column_config.NumberColumn("Applications Submitted YoY %", format="%.1f%%"),
        "applications_submitted_vs_3mo_median": st.column_config.NumberColumn("Applications Submitted vs 3Mo Median", format="%.1f%%"),
        "cost_per_application_submitted_yoy_pct": st.column_config.NumberColumn("Cost per Application Submitted YoY %", format="%.1f%%"),
        "cost_per_application_submitted_vs_3mo_median": st.column_config.NumberColumn("Cost per Application Submitted vs 3Mo Median", format="%.1f%%"),
        "variance_pct": st.column_config.NumberColumn("Variance %", format="%.1f%%"),
    }


def render_conversion_model_debug(campaign):
    debug = campaign.attrs.get("conversion_join_debug", {})
    audit = pd.DataFrame(campaign.attrs.get("conversion_audit", []))
    st.caption("Inspect the physical inputs, join grain, standardized outcome totals, and unmapped conversion actions.")
    st.write(f"Campaign media tab: `{debug.get('campaign_media_tab', 'Unknown')}`")
    st.write(f"Conversion outcomes tab: `{debug.get('conversion_outcomes_tab', 'Unknown')}`")
    st.write(f"Join keys: `{', '.join(debug.get('join_keys', [])) or 'No conversion outcome join'}`")
    st.write(f"Matched media rows: `{debug.get('matched_media_rows', 0)}` of `{debug.get('media_rows', len(campaign))}`")
    totals = campaign.reindex(columns=[
        "enrollment_apply_now_clicks", "enrollment_forms", "applications_submitted", "career_clicks", "priority_conversions"
    ], fill_value=0).sum()
    cols = st.columns(5)
    with cols[0]: st.metric("Apply Now Clicks", f"{totals['enrollment_apply_now_clicks']:,.1f}")
    with cols[1]: st.metric("Enrollment Forms", f"{totals['enrollment_forms']:,.1f}")
    with cols[2]: st.metric("Applications Submitted", f"{totals['applications_submitted']:,.1f}")
    with cols[3]: st.metric("Career Clicks", f"{totals['career_clicks']:,.1f}")
    with cols[4]: st.metric("Priority Conversions", f"{totals['priority_conversions']:,.1f}")
    issues = debug.get("business_rule_issues", [])
    if issues:
        for issue in issues:
            st.error(issue)
    else:
        st.success("Priority conversion sanity checks passed.")
    st.subheader("Top unmapped conversion actions")
    if audit.empty or "conversion_mapping_status" not in audit.columns:
        st.info("Conversion-action audit detail is not available.")
        return
    unmapped = audit[audit["conversion_mapping_status"].eq("Unmapped")].head(25)
    if unmapped.empty:
        st.success("No unmapped conversion actions are present.")
    else:
        st.dataframe(unmapped, use_container_width=True, hide_index=True)


def render_data_source_debug(campaign):
    debug = campaign.attrs.get("conversion_join_debug", {})
    totals = campaign.reindex(columns=[
        "spend", "reported_conversions", "all_conversions", "priority_conversions",
        "enrollment_apply_now_clicks", "enrollment_forms", "career_clicks",
        "applications_submitted", "micro_conversions",
    ], fill_value=0).sum(numeric_only=True)
    st.write(f"Campaign performance tab: `{debug.get('campaign_media_tab', 'Unknown')}`")
    st.write(f"Canonical fields found: `{debug.get('canonical_fields_found', False)}`")
    labels = {
        "spend": "Total Spend",
        "reported_conversions": "Total Reported Conversions",
        "all_conversions": "Total All Conversions",
        "priority_conversions": "Total Priority Conversions",
        "enrollment_apply_now_clicks": "Total Enrollment Apply Now Clicks",
        "enrollment_forms": "Total Enrollment Forms",
        "career_clicks": "Total Career Clicks",
        "applications_submitted": "Total Applications Submitted",
        "micro_conversions": "Total Micro Conversions",
    }
    for metric, label in labels.items():
        value = totals.get(metric, 0)
        st.write(f"{label}: `{value:,.2f}`")

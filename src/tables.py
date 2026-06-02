import pandas as pd
import streamlit as st
from .formatting import metric_column_config


IDENTITY_ORDER = ["date", "week", "month", "objective", "campaign", "ad_group", "search_term", "final_url", "conversion_action"]
METRIC_ORDER = ["spend", "impressions", "clicks", "ctr", "cpc", "total_conversions", "priority_conversions",
                "enrollment_apply_now_clicks", "enrollment_forms", "applications_submitted", "career_clicks",
                "other_micro_conversions", "cvr", "cpa", "priority_cpa", "cost_per_enrollment_apply_click",
                "cost_per_enrollment_form", "cost_per_application_submitted", "cost_per_career_click"]
FLAG_ORDER = ["status", "review_flag", "primary_issue", "issue_type", "priority_score", "recommended_action", "rationale", "notes"]


def ordered_columns(df):
    preferred = IDENTITY_ORDER + METRIC_ORDER + FLAG_ORDER
    cols = [c for c in preferred if c in df.columns]
    cols += [c for c in df.columns if c not in cols and not c.endswith("_raw")]
    return cols


def humanize_columns(df):
    out = df.copy()
    out.columns = [c.replace("_", " ").title().replace("Cpa", "CPA").replace("Cpc", "CPC").replace("Ctr", "CTR").replace("Cvr", "CVR") for c in out.columns]
    return out


def render_table(df, title, caption="", sort_by="spend", search_cols=None, key=None, display_columns=None):
    st.subheader(title)
    if caption:
        st.caption(caption)
    if df.empty:
        st.info("No rows available for this view with the current filters.")
        return
    shown = df.copy()
    search_cols = search_cols or [c for c in ["campaign", "ad_group", "search_term", "final_url"] if c in shown.columns]
    if search_cols:
        query = st.text_input("Search table", key=f"search_{key or title}")
        if query:
            mask = False
            for col in search_cols:
                mask = mask | shown[col].astype(str).str.contains(query, case=False, na=False)
            shown = shown[mask]
    if sort_by in shown.columns:
        shown = shown.sort_values(sort_by, ascending=False)
    shown = shown[[c for c in (display_columns or ordered_columns(shown)) if c in shown.columns]]
    for pct_col in [
        "ctr", "cvr", "spend_share", "click_share", "conversion_share", "spend_yoy_pct",
        "apply_now_rate", "form_completion_rate", "click_to_form_rate",
        "career_click_rate", "application_completion_rate", "click_to_application_rate",
        "conversion_quality_ratio", "micro_rate", "primary_rate",
        "priority_conversion_share", "search_impression_share", "search_top_impression_share",
        "search_absolute_top_impression_share", "search_lost_is_budget", "search_lost_is_rank",
        "clicks_yoy_pct", "priority_conversions_yoy_pct", "priority_cpa_yoy_pct",
        "priority_cpa_vs_3mo_median", "priority_cpa_vs_3mo_benchmark",
        "priority_conversions_vs_3mo_median", "apply_now_clicks_yoy_pct",
        "apply_now_clicks_vs_3mo_median", "enrollment_forms_yoy_pct",
        "enrollment_forms_vs_3mo_median", "cost_per_enrollment_form_yoy_pct",
        "cost_per_enrollment_form_vs_3mo_median", "career_clicks_yoy_pct",
        "career_clicks_vs_3mo_median", "applications_submitted_yoy_pct",
        "applications_submitted_vs_3mo_median", "cost_per_application_submitted_yoy_pct",
        "cost_per_application_submitted_vs_3mo_median", "variance_pct",
    ]:
        if pct_col in shown.columns:
            shown[pct_col] = shown[pct_col] * 100
    st.dataframe(shown, use_container_width=True, hide_index=True, column_config=metric_column_config())
    st.download_button("Download CSV", shown.to_csv(index=False).encode("utf-8"), file_name=f"{(key or title).lower().replace(' ', '_')}.csv", mime="text/csv")

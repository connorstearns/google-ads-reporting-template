import pandas as pd
import streamlit as st
from .formatting import metric_column_config


IDENTITY_ORDER = ["date", "week", "month", "objective", "campaign", "ad_group", "search_term", "final_url", "conversion_action"]
METRIC_ORDER = ["spend", "impressions", "clicks", "ctr", "cpc", "conversions", "career_clicks", "applications",
                "enrollment_apply_now_clicks", "enrollment_forms", "quality_conversions", "cvr", "cpa", "quality_cpa"]
FLAG_ORDER = ["status", "review_flag", "issue_type", "priority_score", "recommended_action", "notes"]


def ordered_columns(df):
    preferred = IDENTITY_ORDER + METRIC_ORDER + FLAG_ORDER
    cols = [c for c in preferred if c in df.columns]
    cols += [c for c in df.columns if c not in cols and not c.endswith("_raw")]
    return cols


def humanize_columns(df):
    out = df.copy()
    out.columns = [c.replace("_", " ").title().replace("Cpa", "CPA").replace("Cpc", "CPC").replace("Ctr", "CTR").replace("Cvr", "CVR") for c in out.columns]
    return out


def render_table(df, title, caption="", sort_by="spend", search_cols=None, key=None):
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
    shown = shown[ordered_columns(shown)]
    for pct_col in ["ctr", "cvr", "spend_share", "click_share", "conversion_share"]:
        if pct_col in shown.columns:
            shown[pct_col] = shown[pct_col] * 100
    st.dataframe(shown, use_container_width=True, hide_index=True, column_config=metric_column_config())
    st.download_button("Download CSV", shown.to_csv(index=False).encode("utf-8"), file_name=f"{(key or title).lower().replace(' ', '_')}.csv", mime="text/csv")

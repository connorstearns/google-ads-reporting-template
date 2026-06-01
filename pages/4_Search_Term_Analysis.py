import pandas as pd
import streamlit as st

from src.filters import apply_global_filters, multiselect_if_available, render_sidebar
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.metrics import safe_divide
from src.tables import render_table
from src.transforms import combine_primary_data


ACTION_QUEUE_COLUMNS = [
    "action_flag", "recommended_action", "review_priority_score", "search_term", "keyword",
    "match_type", "campaign", "ad_group_cleaned", "objective", "search_objective_group",
    "query_theme", "intent_level", "relevance", "brand_nonbrand", "cost", "impressions",
    "clicks", "conversions", "ctr", "cpc", "cpa", "negative_keyword_candidate",
    "keyword_expansion_candidate",
]
MISMATCH_COLUMNS = [
    "search_term", "campaign", "objective", "search_objective_group", "query_theme",
    "cost", "clicks", "conversions", "recommended_action",
]
THEME_COLUMNS = [
    "objective", "search_objective_group", "query_theme", "intent_level", "relevance",
    "search_term_count", "cost", "impressions", "clicks", "conversions", "ctr", "cpc", "cpa",
]
MATCH_TYPE_COLUMNS = ["objective", "match_type", "cost", "clicks", "conversions", "ctr", "cpc", "cpa"]


def truthy(series):
    return series.fillna("").astype(str).str.strip().str.lower().isin({"true", "yes", "y", "1", "x"})


def add_generic_metrics(df):
    out = df.copy()
    for col in ["spend", "impressions", "clicks", "conversions", "review_priority_score"]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["ctr"] = safe_divide(out["clicks"], out["impressions"])
    out["cpc"] = safe_divide(out["spend"], out["clicks"])
    out["cvr"] = safe_divide(out["conversions"], out["clicks"])
    out["cpa"] = safe_divide(out["spend"], out["conversions"])
    out["cost"] = out["spend"]
    return out


def summarize_queries(df, group_cols, count_terms=False):
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby(group_cols, dropna=False, as_index=False).agg(
        spend=("spend", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        conversions=("conversions", "sum"),
        **({"search_term_count": ("search_term", "nunique")} if count_terms else {}),
    )
    return add_generic_metrics(grouped)


def objective_mismatch(row):
    objective = str(row.get("objective", "")).lower()
    search_group = str(row.get("search_objective_group", "")).lower()
    return ("enroll" in objective and "recruit" in search_group) or (
        "recruit" in objective and "enroll" in search_group
    )


st.set_page_config(page_title="Search Term Analysis | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Search Term Analysis")
st.caption("Query management workflow for search relevance, negative keyword review, expansion opportunities, and objective alignment.")
st.info("This page uses row-level search-term media metrics and generic conversions. Priority outcomes currently live at campaign level unless more granular conversion-action data becomes available.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation)
search = apply_global_filters(search, filters)

if search.empty or "search_term" not in search.columns:
    st.info("Search term data is not available yet. Add a model_search_terms or report_search_terms tab.")
    st.stop()

st.sidebar.header("Query workflow filters")
for label, column in [
    ("Query theme", "query_theme"),
    ("Intent level", "intent_level"),
    ("Relevance", "relevance"),
]:
    selected = multiselect_if_available(label, search, column)
    if selected:
        search = search[search[column].isin(selected)]

search = add_generic_metrics(search)
for col in ACTION_QUEUE_COLUMNS:
    if col not in search.columns:
        search[col] = ""

action_queue = search.sort_values(["review_priority_score", "cost"], ascending=[False, False])
negative_candidates = search[truthy(search["negative_keyword_candidate"])].sort_values(
    ["cost", "clicks", "conversions"], ascending=[False, False, True]
)
expansion_candidates = search[truthy(search["keyword_expansion_candidate"])].sort_values(
    ["review_priority_score", "clicks"], ascending=[False, False]
)
mismatches = search[search.apply(objective_mismatch, axis=1)].sort_values("cost", ascending=False)
theme_rollup = summarize_queries(
    search,
    ["objective", "search_objective_group", "query_theme", "intent_level", "relevance"],
    count_terms=True,
).sort_values("cost", ascending=False)
match_type_rollup = summarize_queries(search, ["objective", "match_type"]).sort_values("cost", ascending=False)

render_table(
    action_queue,
    "Query Action Queue",
    "Start with the highest review score and spend exposure. CSV export is available below the table.",
    sort_by=None,
    key="query_action_queue",
    display_columns=ACTION_QUEUE_COLUMNS,
)
render_table(negative_candidates, "Negative Keyword Candidates", "Sheet-flagged negative keyword candidates, prioritized by cost.", sort_by=None, key="negative_keyword_candidates", display_columns=ACTION_QUEUE_COLUMNS)
render_table(expansion_candidates, "Keyword Expansion Candidates", "Sheet-flagged expansion opportunities, prioritized by review score and clicks.", sort_by=None, key="keyword_expansion_candidates", display_columns=ACTION_QUEUE_COLUMNS)
render_table(mismatches, "Objective Mismatch Terms", "Queries whose search objective group conflicts with the campaign objective.", key="objective_mismatch_terms", display_columns=MISMATCH_COLUMNS)
render_table(theme_rollup, "Query Theme Rollup", "Generic conversion efficiency grouped by query classification.", key="query_theme_rollup", display_columns=THEME_COLUMNS)
render_table(match_type_rollup, "Match Type Efficiency", "Generic conversion efficiency by objective and match type.", key="match_type_efficiency", display_columns=MATCH_TYPE_COLUMNS)

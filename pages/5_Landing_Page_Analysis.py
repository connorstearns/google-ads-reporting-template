import pandas as pd
import streamlit as st

from src.filters import apply_global_filters, multiselect_if_available, render_sidebar
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.metrics import safe_divide
from src.tables import render_table
from src.transforms import combine_primary_data


ACTION_QUEUE_COLUMNS = [
    "normalized_url", "page_type", "offer_program", "objective", "campaign_role", "funnel_stage",
    "primary_cta", "intent_match", "cro_priority", "cost", "impressions", "clicks",
    "conversions", "all_conversions", "ctr", "cpc", "cvr", "cpa", "primary_issue",
    "recommended_action",
]
INFLATION_COLUMNS = ACTION_QUEUE_COLUMNS + ["all_to_reported_conversion_ratio"]
ROLLUP_COLUMNS = [
    "objective", "page_type", "offer_program", "primary_cta", "cost", "clicks",
    "conversions", "all_conversions", "ctr", "cpc", "cvr", "cpa",
]


def add_generic_metrics(df):
    out = df.copy()
    for col in ["spend", "impressions", "clicks", "conversions"]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    if "all_conversions" not in out.columns:
        out["all_conversions"] = out["conversions"]
    out["all_conversions"] = pd.to_numeric(out["all_conversions"], errors="coerce").fillna(0)
    out["ctr"] = safe_divide(out["clicks"], out["impressions"])
    out["cpc"] = safe_divide(out["spend"], out["clicks"])
    out["cvr"] = safe_divide(out["conversions"], out["clicks"])
    out["cpa"] = safe_divide(out["spend"], out["conversions"])
    out["all_to_reported_conversion_ratio"] = safe_divide(out["all_conversions"], out["conversions"])
    out["cost"] = out["spend"]
    return out


def summarize_pages(df, group_cols):
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby(group_cols, dropna=False, as_index=False).agg(
        spend=("spend", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        conversions=("conversions", "sum"),
        all_conversions=("all_conversions", "sum"),
    )
    return add_generic_metrics(grouped)


def cro_sort_value(value):
    text = str(value or "").strip().lower()
    try:
        return float(text)
    except ValueError:
        if any(token in text for token in ["high", "urgent", "review", "critical"]):
            return 3
        if "medium" in text:
            return 2
        if "low" in text:
            return 1
        return 0


def local_issue(row):
    issues = []
    if row["cost"] > 0 and row["conversions"] == 0:
        issues.append("Spend with no reported conversions")
    if row["conversions"] > 0 and row["all_to_reported_conversion_ratio"] >= 3:
        issues.append("All conversions materially exceed reported conversions")
    if str(row.get("intent_match", "")).strip().lower() not in {"strong"}:
        issues.append("Intent match needs review")
    return "; ".join(issues) or "No major issue"


def local_action(row):
    issue = str(row.get("primary_issue", ""))
    if "materially exceed" in issue:
        return "Audit conversion actions firing on this page"
    if "Intent match" in issue:
        return "Review landing page alignment and CTA"
    if "no reported conversions" in issue:
        return "Review page efficiency and conversion path"
    return "Maintain and monitor"


st.set_page_config(page_title="Landing Page Analysis | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Landing Page Analysis")
st.caption("Page alignment and CRO triage workflow for landing-page media efficiency, intent match, and conversion-action audit risk.")
st.info("This page uses row-level landing-page media metrics and generic conversions. Priority outcomes currently live at campaign level unless more granular conversion-action data becomes available.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation)
landing = apply_global_filters(landing, filters)

if landing.empty or "final_url" not in landing.columns:
    st.info("Landing page data is not available yet. Add a model_landing_pages or report_landing_pages tab.")
    st.stop()

st.sidebar.header("Landing page workflow filters")
for label, column in [
    ("Page type", "page_type"),
    ("Intent match", "intent_match"),
    ("CRO priority", "cro_priority"),
]:
    selected = multiselect_if_available(label, landing, column)
    if selected:
        landing = landing[landing[column].isin(selected)]
min_spend = st.sidebar.number_input("Weak efficiency minimum spend", min_value=0.0, value=250.0, step=25.0)
cpa_threshold = st.sidebar.number_input("Weak efficiency CPA threshold", min_value=0.0, value=250.0, step=25.0)

landing = add_generic_metrics(landing)
if "normalized_url" not in landing.columns:
    landing["normalized_url"] = landing["final_url"]
for col in ACTION_QUEUE_COLUMNS:
    if col not in landing.columns:
        landing[col] = ""
landing["_cro_priority_sort"] = landing["cro_priority"].apply(cro_sort_value)
local_issues = landing.apply(local_issue, axis=1)
landing["primary_issue"] = landing["primary_issue"].fillna("").where(landing["primary_issue"].fillna("").ne(""), local_issues)
local_actions = landing.apply(local_action, axis=1)
landing["recommended_action"] = landing["recommended_action"].fillna("").where(landing["recommended_action"].fillna("").ne(""), local_actions)

action_queue = landing.sort_values(["_cro_priority_sort", "cost"], ascending=[False, False])
high_spend = landing.sort_values("cost", ascending=False)
weak_efficiency = landing[
    (landing["cost"] >= min_spend)
    & ((landing["conversions"] == 0) | (landing["cpa"] > cpa_threshold))
].sort_values("cost", ascending=False)
inflation_risk = landing[
    (landing["conversions"] > 0) & (landing["all_to_reported_conversion_ratio"] >= 3)
].copy()
inflation_risk["recommended_action"] = "Audit conversion actions firing on this page"
inflation_risk = inflation_risk.sort_values("cost", ascending=False)
intent_review = landing[
    ~landing["intent_match"].fillna("").astype(str).str.strip().str.lower().eq("strong")
].sort_values("cost", ascending=False)
page_type_rollup = summarize_pages(
    landing, ["objective", "page_type", "offer_program", "primary_cta"]
).sort_values("cost", ascending=False)
cro_review = landing[
    landing["cro_priority"].fillna("").astype(str).str.strip().ne("")
].sort_values(["_cro_priority_sort", "cost"], ascending=[False, False])

render_table(action_queue, "Landing Page Action Queue", "Start with CRO priority and cost exposure. CSV export is available below the table.", sort_by=None, key="landing_page_action_queue", display_columns=ACTION_QUEUE_COLUMNS)
render_table(high_spend, "High-Spend Pages", "Landing pages sorted by media cost.", sort_by=None, key="high_spend_pages", display_columns=ACTION_QUEUE_COLUMNS)
render_table(weak_efficiency, "Weak Efficiency Pages", "Pages above the cost threshold with zero generic conversions or CPA above the selected threshold.", sort_by=None, key="weak_efficiency_pages", display_columns=ACTION_QUEUE_COLUMNS)
render_table(inflation_risk, "Micro-Conversion Inflation Risk", "Pages where All Conversions are at least three times reported Conversions. Audit conversion actions firing on these pages.", sort_by=None, key="micro_conversion_inflation_risk", display_columns=INFLATION_COLUMNS)
render_table(intent_review, "Intent Match Review", "Pages with blank, weak, or otherwise non-Strong intent match.", sort_by=None, key="intent_match_review", display_columns=ACTION_QUEUE_COLUMNS)
render_table(page_type_rollup, "Page Type Rollup", "Generic conversion efficiency grouped by page alignment attributes.", sort_by=None, key="page_type_rollup", display_columns=ROLLUP_COLUMNS)
render_table(cro_review, "CRO Priority Review", "Pages with a populated CRO priority, sorted by priority and cost.", sort_by=None, key="cro_priority_review", display_columns=ACTION_QUEUE_COLUMNS)

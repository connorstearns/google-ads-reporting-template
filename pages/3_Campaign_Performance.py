import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.benchmarks import UNAVAILABLE_MESSAGE, build_campaign_type_context, get_campaign_type_benchmarks, priority_cpa_display
from src.campaign_decisions import missing_optional_campaign_fields
from src.filters import apply_global_filters, render_sidebar
from src.formatting import PRIORITY_CONVERSIONS_HELP, apply_page_style, kpi_card, money, number, render_conversion_model_debug, render_data_source_debug, render_kpi_card
from src.google_sheets import load_workbook
from src.metrics import summarize
from src.periods import get_filter_comparison_range, top_kpi_deltas
from src.tables import render_table
from src.transforms import combine_primary_data


ACTION_MATRIX_COLUMNS = [
    "campaign", "objective", "campaign_type", "campaign_role", "campaign_status",
    "spend", "clicks", "priority_conversions", "priority_cpa", "micro_conversions",
    "primary_conversions", "conversion_quality_ratio", "search_impression_share",
    "action_status", "recommended_action",
]
TACTIC_COLUMNS = [
    "objective", "tactic", "spend", "clicks", "priority_conversions", "priority_cpa",
    "spend_share", "priority_conversion_share", "efficiency_index", "allocation_interpretation",
]
SEARCH_COLUMNS = [
    "campaign", "objective", "campaign_type", "search_impression_share",
    "search_top_impression_share", "search_absolute_top_impression_share",
    "search_lost_is_budget", "search_lost_is_rank", "priority_cpa",
    "market_penetration_diagnosis",
]
BENCHMARK_CONTEXT_COLUMNS = [
    "month", "campaign_type", "objective", "campaign", "spend", "priority_conversions",
    "benchmark_status", "yoy_benchmark_status", "campaign_type_priority_cpa_benchmark",
    "prior_year_priority_cpa", "priority_cpa_vs_3mo_benchmark", "priority_cpa_yoy_pct",
    "yoy_benchmark_note",
]
SEARCH_IS_COLUMNS = [
    "search_impression_share",
    "search_top_impression_share",
    "search_absolute_top_impression_share",
    "search_lost_is_budget",
    "search_lost_is_rank",
]


def safe_div(numerator, denominator):
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    return numerator.div(denominator.replace({0: pd.NA}))


def numeric_or_zero(value):
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0 if pd.isna(value) else value


def campaign_group_columns(df):
    if "objective" not in df.columns:
        df["objective"] = "Other / Unmapped"
    if "campaign" not in df.columns:
        df["campaign"] = "Unknown campaign"
    cols = ["objective", "campaign"]
    for col in ["campaign_type", "campaign_role", "campaign_status", "advertising_channel_type"]:
        if col in df.columns:
            cols.append(col)
    return cols


def objective_conversion_metrics(row):
    objective = str(row.get("objective", ""))
    if objective == "Enrollment":
        return row.get("enrollment_apply_now_clicks", 0), row.get("enrollment_forms", 0)
    if objective == "Recruitment":
        return row.get("career_clicks", 0), row.get("applications_submitted", 0)
    return row.get("other_micro_conversions", 0), row.get("priority_conversions", 0)


def add_action_metrics(df, thresholds):
    out = df.copy()
    if out.empty:
        return out
    if "campaign_type" not in out.columns:
        out["campaign_type"] = out.get("advertising_channel_type", out.get("campaign_role", "Unmapped"))
    if "campaign_role" not in out.columns:
        out["campaign_role"] = "Unmapped"
    if "campaign_status" not in out.columns:
        out["campaign_status"] = "Unknown"
    micro_primary = out.apply(lambda row: pd.Series(objective_conversion_metrics(row), index=["micro_conversions", "primary_conversions"]), axis=1)
    out[["micro_conversions", "primary_conversions"]] = micro_primary
    out["conversion_quality_ratio"] = safe_div(out["priority_conversions"], out["total_conversions"])
    objective_totals = out.groupby("objective", dropna=False).agg(
        objective_spend=("spend", "sum"),
        objective_priority_conversions=("priority_conversions", "sum"),
    ).reset_index()
    objective_totals["objective_avg_priority_cpa"] = safe_div(
        objective_totals["objective_spend"],
        objective_totals["objective_priority_conversions"],
    )
    out = out.merge(objective_totals[["objective", "objective_avg_priority_cpa"]], on="objective", how="left")
    out["action_status"] = out.apply(lambda row: action_status(row, thresholds), axis=1)
    out["recommended_action"] = out.apply(recommended_action, axis=1)
    return out.sort_values(["action_status", "spend"], ascending=[True, False])


def action_status(row, thresholds):
    spend = numeric_or_zero(row.get("spend", 0))
    priority_conversions = numeric_or_zero(row.get("priority_conversions", 0))
    priority_cpa = numeric_or_zero(row.get("priority_cpa", 0))
    objective_avg = numeric_or_zero(row.get("objective_avg_priority_cpa", 0))
    total_conversions = numeric_or_zero(row.get("total_conversions", 0))
    quality_ratio = numeric_or_zero(row.get("conversion_quality_ratio", 0))
    if spend < thresholds["min_spend"]:
        return "Needs data"
    if total_conversions > priority_conversions * 3 and quality_ratio < 0.25:
        return "Quality issue"
    if spend > 0 and priority_conversions == 0:
        return "Investigate"
    if priority_conversions > 0 and objective_avg > 0 and priority_cpa <= objective_avg * 0.8:
        return "Scale"
    if priority_conversions > 0 and objective_avg > 0 and priority_cpa >= objective_avg * 1.2:
        return "Optimize"
    if priority_conversions > 0:
        return "Maintain"
    return "Needs data"


def recommended_action(row):
    status = row.get("action_status", "")
    if status == "Scale":
        return "Increase budget gradually or expand similar query/tactic coverage"
    if status == "Optimize":
        return "Improve targeting, search terms, creative, and landing page efficiency"
    if status == "Investigate":
        return "Check tracking, conversion path, search terms, and campaign fit before adding budget"
    if status == "Quality issue":
        return "Audit conversion action mix and primary conversion settings"
    if status == "Maintain":
        return "Maintain budget and monitor against objective average CPA"
    return "Wait for more spend/click volume before making a budget decision"


def build_action_matrix(campaign, thresholds):
    campaign = campaign.copy()
    if "objective" not in campaign.columns:
        campaign["objective"] = "Other / Unmapped"
    if "campaign" not in campaign.columns:
        campaign["campaign"] = "Unknown campaign"
    grouped = summarize(campaign, campaign_group_columns(campaign))
    for col in SEARCH_IS_COLUMNS:
        if col in campaign.columns:
            grouped = grouped.merge(
                campaign.groupby("campaign", dropna=False)[col].mean().rename(col),
                on="campaign",
                how="left",
            )
            if grouped[col].max(skipna=True) > 1:
                grouped[col] = grouped[col] / 100
    return add_action_metrics(grouped, thresholds)


def tactic_source_column(df):
    for col in ["campaign_type", "campaign_role", "advertising_channel_type", "campaign"]:
        if col in df.columns and df[col].fillna("").astype(str).str.strip().ne("").any():
            return col
    return None


def build_tactic_allocation(action_matrix):
    if action_matrix.empty:
        return action_matrix
    source_col = tactic_source_column(action_matrix)
    source = action_matrix.copy()
    if source_col is None:
        source["tactic"] = "Unmapped"
    else:
        source["tactic"] = source[source_col].fillna("Unmapped").replace("", "Unmapped")
    grouped = summarize(source, ["objective", "tactic"])
    objective_totals = grouped.groupby("objective", dropna=False).agg(
        objective_spend=("spend", "sum"),
        objective_priority_conversions=("priority_conversions", "sum"),
    ).reset_index()
    grouped = grouped.merge(objective_totals, on="objective", how="left")
    grouped["spend_share"] = safe_div(grouped["spend"], grouped["objective_spend"])
    grouped["priority_conversion_share"] = safe_div(grouped["priority_conversions"], grouped["objective_priority_conversions"])
    grouped["efficiency_index"] = safe_div(grouped["priority_conversion_share"], grouped["spend_share"])
    grouped["allocation_interpretation"] = grouped["efficiency_index"].apply(efficiency_label)
    return grouped.sort_values(["objective", "efficiency_index", "spend"], ascending=[True, False, False])


def efficiency_label(value):
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(value):
        return "Needs data"
    if value > 1.2:
        return "Over-performing relative to budget share"
    if value < 0.8:
        return "Under-performing relative to budget share"
    return "Proportional"


def allocation_chart(tactics):
    if tactics.empty:
        return go.Figure()
    shown = tactics.sort_values("spend", ascending=False).head(12)
    labels = shown["objective"].astype(str) + " / " + shown["tactic"].astype(str)
    fig = go.Figure()
    fig.add_bar(y=labels, x=shown["spend_share"], name="Spend Share", orientation="h", marker_color="#64748b")
    fig.add_bar(y=labels, x=shown["priority_conversion_share"], name="Priority Conversion Share", orientation="h", marker_color="#2563eb")
    fig.update_layout(
        template="plotly_white",
        title="Spend share vs priority conversion share",
        barmode="group",
        height=max(320, len(shown) * 34),
        margin=dict(l=10, r=10, t=55, b=20),
        xaxis_tickformat=".0%",
    )
    return fig


def impression_share_columns_present(df):
    return [col for col in SEARCH_IS_COLUMNS if col in df.columns]


def impression_share_populated(df):
    present = impression_share_columns_present(df)
    return bool(present) and df[present].fillna(0).sum().sum() > 0


def is_search_campaign(row):
    text = " ".join(str(row.get(col, "")) for col in ["campaign_type", "advertising_channel_type", "campaign"]).lower()
    return "search" in text


def build_search_market_penetration(action_matrix):
    if not impression_share_populated(action_matrix):
        return pd.DataFrame()
    search_rows = action_matrix[action_matrix.apply(is_search_campaign, axis=1)].copy()
    if search_rows.empty:
        return search_rows
    search_rows["market_penetration_diagnosis"] = search_rows.apply(search_diagnosis, axis=1)
    return search_rows.sort_values(["search_impression_share", "spend"], ascending=[True, False])


def search_diagnosis(row):
    search_is = row.get("search_impression_share", 0)
    lost_budget = row.get("search_lost_is_budget", 0)
    lost_rank = row.get("search_lost_is_rank", 0)
    abs_top = row.get("search_absolute_top_impression_share", 0)
    status = row.get("action_status", "")
    efficient = status in {"Scale", "Maintain"}
    poor_cpa = status == "Optimize"
    if efficient and search_is < 0.6:
        return "Scale opportunity / demand headroom"
    if search_is < 0.6 and lost_budget > 0.2:
        return "Budget constrained"
    if search_is < 0.6 and lost_rank > 0.2:
        return "Rank or quality issue"
    if search_is >= 0.75 and poor_cpa:
        return "Efficiency issue, not coverage issue"
    if abs_top >= 0.75 and poor_cpa:
        return "Potential overbidding"
    return "Monitor market coverage"


def status_count(df, status):
    return int((df["action_status"] == status).sum()) if "action_status" in df.columns else 0


def filtered_campaign_for_period(df, filters, start, end, ad_group_filter=None):
    if df.empty or start is None or end is None:
        return df.iloc[0:0].copy()
    period_filters = dict(filters)
    period_filters["date_range"] = (pd.Timestamp(start).date(), pd.Timestamp(end).date())
    out = apply_global_filters(df, period_filters)
    if ad_group_filter and "ad_group" in out.columns:
        out = out[out["ad_group"].isin(ad_group_filter)]
    return out


def action_metric_counts(df, thresholds):
    matrix = build_action_matrix(df, thresholds)
    counts = {
        "campaigns_eligible_to_scale": status_count(matrix, "Scale"),
        "campaigns_to_optimize": status_count(matrix, "Optimize"),
        "campaigns_to_investigate": status_count(matrix, "Investigate"),
        "campaigns_with_quality_issues": status_count(matrix, "Quality issue"),
    }
    if impression_share_populated(matrix):
        search_rows = build_search_market_penetration(matrix)
        counts["budget_limited_search_campaigns"] = int(search_rows.get("search_lost_is_budget", pd.Series(dtype=float)).fillna(0).gt(0.2).sum())
    return counts


def action_count_deltas(source, filters, thresholds, ad_group_filter=None):
    start, end, comp_start, comp_end, comparison_label = get_filter_comparison_range(filters)
    if start is None or comp_start is None:
        return {}
    current_df = filtered_campaign_for_period(source, filters, start, end, ad_group_filter)
    comparison_df = filtered_campaign_for_period(source, filters, comp_start, comp_end, ad_group_filter)
    if comparison_df.empty:
        return {}
    current_counts = action_metric_counts(current_df, thresholds)
    comparison_counts = action_metric_counts(comparison_df, thresholds)
    deltas = {}
    for metric, current_value in current_counts.items():
        comparison_value = comparison_counts.get(metric)
        if comparison_value is None or pd.isna(comparison_value):
            deltas[metric] = None
        else:
            deltas[metric] = f"{int(current_value - comparison_value):+,d} vs {comparison_label}"
    return deltas


apply_page_style()
st.title("Campaign Performance")
st.caption("Campaign-management decision dashboard focused on objective-quality outcomes, peer efficiency, budget allocation, and next actions.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation, thresholds=True, date_presets=True)
campaign_source = campaign.copy()
campaign = apply_global_filters(campaign, filters)

if campaign.empty:
    st.warning("No campaign performance data is available with the current filters.")
    st.stop()

missing_optional = missing_optional_campaign_fields(campaign)
if missing_optional:
    st.warning(
        "Some optional campaign fields are unavailable, so safe fallbacks are being used: "
        + ", ".join(missing_optional)
        + "."
    )

ad_group_filter = []
if "ad_group" in campaign.columns:
    ad_group_filter = st.multiselect("Ad group", sorted(campaign["ad_group"].dropna().unique()))
    if ad_group_filter:
        campaign = campaign[campaign["ad_group"].isin(ad_group_filter)]

thresholds = filters["thresholds"]
totals = summarize(campaign).iloc[0]
start, end, comp_start, comp_end, comparison_label = get_filter_comparison_range(filters)
if start is not None and comp_start is not None:
    st.caption(
        f"Current period: {start:%Y-%m-%d} to {end:%Y-%m-%d} | "
        f"Comparison period: {comp_start:%Y-%m-%d} to {comp_end:%Y-%m-%d} ({comparison_label})"
    )
top_deltas = top_kpi_deltas(campaign_source, filters, ["spend", "priority_conversions", "priority_cpa"])
action_matrix = build_action_matrix(campaign, thresholds)
count_deltas = action_count_deltas(campaign_source, filters, thresholds, ad_group_filter)
tactic_allocation = build_tactic_allocation(action_matrix)
benchmarks = get_campaign_type_benchmarks(data)
present_search_is = impression_share_columns_present(action_matrix)
search_is_ready = impression_share_populated(action_matrix)
search_market = build_search_market_penetration(action_matrix)
quality_issue_count = status_count(action_matrix, "Quality issue")

cols = st.columns(8 if quality_issue_count else 7)
with cols[0]: render_kpi_card("Total Spend", money(totals["spend"]), delta=top_deltas.get("spend"))
with cols[1]: render_kpi_card("Priority Conversions", number(totals["priority_conversions"], 1), delta=top_deltas.get("priority_conversions"), help_text=PRIORITY_CONVERSIONS_HELP)
with cols[2]: render_kpi_card("Priority CPA", priority_cpa_display(totals["priority_cpa"], totals["priority_conversions"]), delta=top_deltas.get("priority_cpa"), format_type="cost_efficiency", help_text=PRIORITY_CONVERSIONS_HELP)
with cols[3]: render_kpi_card("Campaigns Eligible to Scale", number(status_count(action_matrix, "Scale")), delta=count_deltas.get("campaigns_eligible_to_scale"))
with cols[4]: render_kpi_card("Campaigns to Optimize", number(status_count(action_matrix, "Optimize")), delta=count_deltas.get("campaigns_to_optimize"), format_type="lower")
with cols[5]: render_kpi_card("Campaigns to Investigate", number(status_count(action_matrix, "Investigate")), delta=count_deltas.get("campaigns_to_investigate"), format_type="lower")
search_card_index = 6
if quality_issue_count:
    with cols[6]: render_kpi_card("Campaigns with Quality Issues", number(quality_issue_count), delta=count_deltas.get("campaigns_with_quality_issues"), format_type="lower")
    search_card_index = 7
if search_is_ready:
    budget_limited = search_market.get("search_lost_is_budget", pd.Series(dtype=float)).fillna(0).gt(0.2).sum()
    with cols[search_card_index]: render_kpi_card("Budget-Limited Search Campaigns", number(budget_limited), delta=count_deltas.get("budget_limited_search_campaigns"), format_type="lower")
else:
    missing_label = "Campaigns Missing Search IS Data" if present_search_is else "Search IS Fields Missing"
    with cols[search_card_index]: kpi_card(missing_label, number(len(action_matrix)))

st.subheader("Campaign Action Matrix")
st.caption("One row per campaign. Status compares each campaign's priority CPA to the average CPA for its objective.")
render_table(
    action_matrix,
    "Campaign action matrix",
    "Use this as the working campaign-management queue.",
    sort_by="spend",
    key="campaign_action_matrix",
    display_columns=ACTION_MATRIX_COLUMNS,
)

st.subheader("Tactic Allocation")
st.caption("Shows whether each objective/tactic group is earning its share of budget through priority outcomes.")
render_table(
    tactic_allocation,
    "Tactic allocation by objective",
    "Efficiency Index = Priority Conversion Share divided by Spend Share.",
    sort_by="spend",
    key="tactic_allocation",
    display_columns=TACTIC_COLUMNS,
)
allocation_fig = allocation_chart(tactic_allocation)
if allocation_fig.data:
    st.plotly_chart(allocation_fig, use_container_width=True)

if search_is_ready:
    st.subheader("Search Market Penetration")
    st.caption("Search-only view of coverage, lost impression share, and whether efficient campaigns have demand headroom.")
    render_table(
        search_market,
        "Search market penetration diagnostics",
        "",
        sort_by="search_impression_share",
        key="search_market_penetration",
        display_columns=SEARCH_COLUMNS,
    )
elif present_search_is:
    st.info(
        "Search impression share fields exist in the raw campaign schema but are not populated. "
        "Add Search IS, Lost IS Budget, and Lost IS Rank to the Supermetrics campaign query to enable market penetration diagnostics."
    )

with st.expander("Campaign type benchmark context", expanded=False):
    benchmark_context = build_campaign_type_context(campaign, benchmarks)
    if benchmarks.empty:
        st.info(UNAVAILABLE_MESSAGE)
    elif benchmark_context.empty:
        st.info("Campaign Type Benchmark context is unavailable because campaign rows do not include campaign type and month fields.")
    else:
        render_table(
            benchmark_context,
            "Campaign Type Benchmark Context",
            "Benchmarks support campaign decisions; they are not the primary decision queue.",
            sort_by=None,
            key="campaign_type_benchmark_context",
            display_columns=BENCHMARK_CONTEXT_COLUMNS,
        )

with st.expander("Supporting campaign views", expanded=False):
    tab1, tab2, tab3, tab4 = st.tabs(["Scale", "Optimize", "Investigate", "Quality issue"])
    with tab1:
        render_table(action_matrix[action_matrix["action_status"].eq("Scale")], "Scale candidates", key="scale_candidates", display_columns=ACTION_MATRIX_COLUMNS)
    with tab2:
        render_table(action_matrix[action_matrix["action_status"].eq("Optimize")], "Optimization candidates", key="optimize_candidates", display_columns=ACTION_MATRIX_COLUMNS)
    with tab3:
        render_table(action_matrix[action_matrix["action_status"].eq("Investigate")], "Investigation candidates", key="investigate_candidates", display_columns=ACTION_MATRIX_COLUMNS)
    with tab4:
        render_table(action_matrix[action_matrix["action_status"].eq("Quality issue")], "Quality issue candidates", key="quality_issue_candidates", display_columns=ACTION_MATRIX_COLUMNS)

with st.expander("Debug conversion outcome join", expanded=False):
    render_conversion_model_debug(campaign)

with st.expander("Data Source Debug", expanded=False):
    render_data_source_debug(campaign)

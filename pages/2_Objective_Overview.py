import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.benchmarks import priority_cpa_display
from src.charts import (
    campaign_priority_cpa_bar,
    objective_mix_bar,
    objective_spend_priority_scatter,
)
from src.conversion_logic import conversion_debug_audit
from src.filters import apply_global_filters, render_sidebar
from src.formatting import PRIORITY_CONVERSIONS_HELP, apply_page_style, kpi_card, money, number, percent, render_conversion_model_debug, render_data_source_debug, render_kpi_card
from src.google_sheets import load_workbook
from src.metrics import safe_divide, summarize
from src.periods import top_kpi_deltas
from src.tables import render_table
from src.transforms import combine_primary_data


ENROLLMENT_COLUMNS = [
    "campaign", "campaign_type", "campaign_role", "spend", "clicks", "micro_conversions",
    "primary_conversions", "micro_rate", "primary_rate", "micro_cpa", "primary_cpa",
    "diagnosis", "recommended_action",
]
RECRUITMENT_COLUMNS = [
    "campaign", "campaign_type", "campaign_role", "spend", "clicks", "micro_conversions",
    "primary_conversions", "micro_rate", "primary_rate", "micro_cpa", "primary_cpa",
    "diagnosis", "recommended_action",
]
TACTIC_COLUMNS = [
    "tactic", "spend", "clicks", "micro_conversions", "primary_conversions",
    "micro_rate", "primary_rate", "micro_cpa", "primary_cpa",
]


def objective_row(objective_summary, objective):
    matched = objective_summary[objective_summary["objective"].eq(objective)]
    if not matched.empty:
        return matched.iloc[0]
    return pd.Series({
        "spend": 0, "clicks": 0, "enrollment_apply_now_clicks": 0, "enrollment_forms": 0,
        "career_clicks": 0, "applications_submitted": 0, "priority_conversions": 0, "priority_cpa": 0,
        "cost_per_enrollment_apply_click": 0, "cost_per_enrollment_form": 0,
        "cost_per_application_submitted": 0, "cost_per_career_click": 0,
    })


def add_objective_funnel_metrics(df, objective):
    out = df.copy()
    if out.empty:
        return out
    if objective == "Enrollment":
        out["apply_now_rate"] = safe_divide(out["enrollment_apply_now_clicks"], out["clicks"])
        out["form_completion_rate"] = safe_divide(out["enrollment_forms"], out["enrollment_apply_now_clicks"])
        out["click_to_form_rate"] = safe_divide(out["enrollment_forms"], out["clicks"])
        out["cost_per_apply_now_click"] = safe_divide(out["spend"], out["enrollment_apply_now_clicks"])
        out["cost_per_enrollment_form"] = safe_divide(out["spend"], out["enrollment_forms"])
    if objective == "Recruitment":
        out["career_click_rate"] = safe_divide(out["career_clicks"], out["clicks"])
        out["application_completion_rate"] = safe_divide(out["applications_submitted"], out["career_clicks"])
        out["click_to_application_rate"] = safe_divide(out["applications_submitted"], out["clicks"])
        out["cost_per_career_click"] = safe_divide(out["spend"], out["career_clicks"])
        out["cost_per_application"] = safe_divide(out["spend"], out["applications_submitted"])
    return out


def objective_conversion_cols(objective):
    if objective == "Enrollment":
        return "enrollment_apply_now_clicks", "enrollment_forms"
    return "career_clicks", "applications_submitted"


def add_diagnostic_metrics(df, objective):
    out = add_objective_funnel_metrics(df, objective)
    micro_col, primary_col = objective_conversion_cols(objective)
    out["micro_conversions"] = out[micro_col]
    out["primary_conversions"] = out[primary_col]
    out["micro_rate"] = safe_divide(out["micro_conversions"], out["clicks"])
    out["primary_rate"] = safe_divide(out["primary_conversions"], out["clicks"])
    out["micro_cpa"] = safe_divide(out["spend"], out["micro_conversions"])
    out["primary_cpa"] = safe_divide(out["spend"], out["primary_conversions"])
    return out


def funnel_chart(row, objective):
    if objective == "Enrollment":
        labels = ["Clicks", "Apply Now Clicks", "Enrollment Forms"]
        values = [row.get("clicks", 0), row.get("enrollment_apply_now_clicks", 0), row.get("enrollment_forms", 0)]
        color = "#2563eb"
    else:
        labels = ["Clicks", "Career Clicks", "Applications Submitted"]
        values = [row.get("clicks", 0), row.get("career_clicks", 0), row.get("applications_submitted", 0)]
        color = "#16a34a"
    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=color,
        text=[number(value, 1 if label != "Clicks" else 0) for label, value in zip(labels, values)],
        textposition="outside",
        hovertemplate="%{y}: %{x:,.1f}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"{objective} funnel",
        margin=dict(l=10, r=35, t=45, b=10),
        height=240,
        xaxis_title="Volume",
        yaxis_title="",
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def tactic_diagnostics(campaign, objective):
    filtered = campaign[campaign["objective"].eq(objective)]
    tactic_col = "campaign_type" if "campaign_type" in filtered.columns else "campaign_role"
    if tactic_col not in filtered.columns:
        filtered = filtered.assign(tactic="Unmapped")
        tactic_col = "tactic"
    perf = summarize(filtered, [tactic_col])
    if perf.empty:
        return perf
    perf = perf.rename(columns={tactic_col: "tactic"})
    return add_diagnostic_metrics(perf, objective).sort_values(["primary_conversions", "spend"], ascending=[False, False])


def campaign_diagnostics(campaign, objective):
    group_cols = ["objective", "campaign"]
    for col in ["campaign_type", "campaign_role"]:
        if col in campaign.columns:
            group_cols.append(col)
    perf = summarize(campaign[campaign["objective"].eq(objective)], group_cols)
    if perf.empty:
        return perf
    perf = add_diagnostic_metrics(perf, objective)
    objective_average_primary_cpa = safe_divide(perf["spend"].sum(), perf["primary_conversions"].sum()).item()
    objective_average_micro_rate = safe_divide(perf["micro_conversions"].sum(), perf["clicks"].sum()).item()
    perf[["diagnosis", "recommended_action"]] = perf.apply(
        lambda row: pd.Series(diagnose_campaign(row, objective, objective_average_primary_cpa, objective_average_micro_rate)),
        axis=1,
    )
    if "conversion_mapping_status" in campaign.columns:
        unmapped = (
            campaign[campaign["objective"].eq(objective)]
            .groupby("campaign")["conversion_mapping_status"]
            .apply(lambda values: "Unmapped" if values.eq("Unmapped").any() else "Mapped or inferred")
            .rename("conversion_mapping_status")
        )
        perf = perf.merge(unmapped, on="campaign", how="left")
    return perf.sort_values(["diagnosis", "spend"], ascending=[True, False])


def diagnose_campaign(row, objective, objective_average_primary_cpa, objective_average_micro_rate):
    spend = row.get("spend", 0)
    micro = row.get("micro_conversions", 0)
    primary = row.get("primary_conversions", 0)
    micro_rate = row.get("micro_rate", 0)
    primary_cpa = row.get("primary_cpa", 0)
    total = row.get("total_conversions", 0)
    priority = row.get("priority_conversions", 0)
    low_micro_rate = spend > 0 and row.get("clicks", 0) >= 20 and micro_rate < objective_average_micro_rate * 0.5
    efficient_primary_cpa = primary > 0 and objective_average_primary_cpa > 0 and primary_cpa <= objective_average_primary_cpa
    conversion_quality_issue = total >= 5 and priority < total * 0.5
    if objective == "Enrollment":
        if spend > 0 and micro > 0 and primary == 0:
            return "Interest not becoming forms", "Review landing page/form completion path"
        if low_micro_rate:
            return "Weak Apply Now rate", "Review search terms, landing page relevance, and CTA alignment"
        if efficient_primary_cpa:
            return "Scale candidate", "Consider increasing budget or expanding similar query/tactic coverage"
        if conversion_quality_issue:
            return "Conversion quality issue", "Check optimization action mix and primary conversion settings"
        return "Monitor", "No immediate action"
    if spend > 0 and micro > 0 and primary == 0:
        return "Career interest not becoming applications", "Review job/application flow"
    if low_micro_rate:
        return "Weak career click rate", "Review landing page relevance and CTA clarity"
    if efficient_primary_cpa:
        return "Scale candidate", "Consider increasing budget or expanding similar query/tactic coverage"
    return "Monitor", "No immediate action"


st.set_page_config(page_title="Objective Overview | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Objective Overview")
st.caption("Objective-specific view of whether Enrollment campaigns drive Apply Now clicks and forms, and whether Recruitment campaigns drive submitted applications.")
st.info(PRIORITY_CONVERSIONS_HELP)

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation)
campaign_source = campaign.copy()
campaign = apply_global_filters(campaign, filters)

if campaign.empty:
    st.warning("No objective-level campaign data is available with the current filters.")
    st.stop()

objective = summarize(campaign, ["objective"]).sort_values("spend", ascending=False)
objective = pd.concat([
    add_objective_funnel_metrics(objective[objective["objective"].eq("Enrollment")], "Enrollment"),
    add_objective_funnel_metrics(objective[objective["objective"].eq("Recruitment")], "Recruitment"),
    objective[~objective["objective"].isin(["Enrollment", "Recruitment"])],
], ignore_index=True)
enrollment = objective_row(objective, "Enrollment")
recruitment = objective_row(objective, "Recruitment")
enrollment_tactics = tactic_diagnostics(campaign, "Enrollment")
recruitment_tactics = tactic_diagnostics(campaign, "Recruitment")
enrollment_table = campaign_diagnostics(campaign, "Enrollment")
recruitment_table = campaign_diagnostics(campaign, "Recruitment")
enrollment_deltas = top_kpi_deltas(
    campaign_source[campaign_source["objective"].eq("Enrollment")],
    filters,
    ["spend", "clicks", "enrollment_apply_now_clicks", "enrollment_forms", "priority_cpa"],
)
recruitment_deltas = top_kpi_deltas(
    campaign_source[campaign_source["objective"].eq("Recruitment")],
    filters,
    ["spend", "clicks", "career_clicks", "applications_submitted", "priority_cpa"],
)

st.header("Enrollment Performance")
cols = st.columns(4)
with cols[0]: render_kpi_card("Spend", money(enrollment["spend"]), delta=enrollment_deltas.get("spend"))
with cols[1]: render_kpi_card("Clicks", number(enrollment["clicks"]), delta=enrollment_deltas.get("clicks"))
with cols[2]: render_kpi_card("Enrollment Apply Now Clicks", number(enrollment["enrollment_apply_now_clicks"], 1), delta=enrollment_deltas.get("enrollment_apply_now_clicks"))
with cols[3]: render_kpi_card("Enrollment Forms", number(enrollment["enrollment_forms"], 1), delta=enrollment_deltas.get("enrollment_forms"))
cols = st.columns(4)
with cols[0]: kpi_card("Apply Now Rate", percent(enrollment.get("apply_now_rate", 0)), help_text="Enrollment Apply Now Clicks divided by Clicks.")
with cols[1]: kpi_card("Form Completion Rate", percent(enrollment.get("form_completion_rate", 0)), help_text="Enrollment Forms divided by Enrollment Apply Now Clicks.")
with cols[2]: kpi_card("Cost per Enrollment Form", money(enrollment["cost_per_enrollment_form"]))
with cols[3]: render_kpi_card("Enrollment Priority CPA", priority_cpa_display(enrollment["priority_cpa"], enrollment["priority_conversions"]), delta=enrollment_deltas.get("priority_cpa"), format_type="cost_efficiency", help_text=PRIORITY_CONVERSIONS_HELP)
if enrollment["enrollment_apply_now_clicks"] > 0 and enrollment["enrollment_forms"] == 0:
    st.warning("Apply Now intent is not translating into form submissions.")
st.plotly_chart(funnel_chart(enrollment, "Enrollment"), use_container_width=True)
render_table(enrollment_tactics, "Enrollment tactic diagnostics", "Compare which campaign type or role turns clicks into Apply Now clicks and forms.", key="enrollment_tactics", display_columns=TACTIC_COLUMNS)
render_table(enrollment_table, "Enrollment campaign diagnostics", "Identify campaigns that need landing page, targeting, or conversion action review.", key="enrollment_diagnostics", display_columns=ENROLLMENT_COLUMNS)

st.header("Recruitment Performance")
cols = st.columns(4)
with cols[0]: render_kpi_card("Spend", money(recruitment["spend"]), delta=recruitment_deltas.get("spend"))
with cols[1]: render_kpi_card("Clicks", number(recruitment["clicks"]), delta=recruitment_deltas.get("clicks"))
with cols[2]: render_kpi_card("Career Clicks", number(recruitment["career_clicks"], 1), delta=recruitment_deltas.get("career_clicks"), help_text="Career Clicks are a mid-funnel recruitment intent metric. They do not count as Priority Conversions.")
with cols[3]: render_kpi_card("Applications Submitted", number(recruitment["applications_submitted"], 1), delta=recruitment_deltas.get("applications_submitted"))
cols = st.columns(4)
with cols[0]: kpi_card("Career Click Rate", percent(recruitment.get("career_click_rate", 0)), help_text="Career Clicks divided by Clicks.")
with cols[1]: kpi_card("Application Completion Rate", percent(recruitment.get("application_completion_rate", 0)), help_text="Applications Submitted divided by Career Clicks.")
with cols[2]: kpi_card("Cost per Application", money(recruitment.get("cost_per_application", recruitment.get("cost_per_application_submitted", 0))))
with cols[3]: render_kpi_card("Recruitment Priority CPA", priority_cpa_display(recruitment["priority_cpa"], recruitment["priority_conversions"]), delta=recruitment_deltas.get("priority_cpa"), format_type="cost_efficiency", help_text=PRIORITY_CONVERSIONS_HELP)
if recruitment["career_clicks"] > 0 and recruitment["applications_submitted"] == 0:
    st.warning("Career interest is not translating into submitted applications.")
st.plotly_chart(funnel_chart(recruitment, "Recruitment"), use_container_width=True)
render_table(recruitment_tactics, "Recruitment tactic diagnostics", "Compare which campaign type or role turns clicks into career clicks and submitted applications.", key="recruitment_tactics", display_columns=TACTIC_COLUMNS)
render_table(recruitment_table, "Recruitment campaign diagnostics", "Identify campaigns that need landing page, targeting, or conversion action review.", key="recruitment_diagnostics", display_columns=RECRUITMENT_COLUMNS)

st.header("Cross-objective diagnostics")
left, right = st.columns(2)
with left:
    st.plotly_chart(objective_mix_bar(campaign, "priority_conversions", "Priority conversions by objective"), use_container_width=True)
with right:
    st.plotly_chart(objective_spend_priority_scatter(campaign), use_container_width=True)
campaign_perf = summarize(campaign, ["objective", "campaign"])
st.plotly_chart(campaign_priority_cpa_bar(campaign_perf, 0, 1, "Priority CPA by campaign with priority conversions"), use_container_width=True)

with st.expander("Debug conversion classification", expanded=False):
    render_conversion_model_debug(campaign)
    st.subheader("Conversion classification audit")
    audit = pd.DataFrame(campaign.attrs.get("conversion_audit", []))
    if audit.empty:
        audit = conversion_debug_audit(campaign)
    if audit.empty:
        st.info("Conversion-action detail is not available in the conversion outcome dataset.")
    else:
        st.dataframe(audit, use_container_width=True, hide_index=True)

with st.expander("Data Source Debug", expanded=False):
    render_data_source_debug(campaign)

import pandas as pd
import streamlit as st

from src.charts import (
    campaign_priority_cpa_bar,
    objective_funnel_bar,
    objective_mix_bar,
    objective_spend_priority_scatter,
)
from src.conversion_logic import conversion_debug_audit, objective_diagnostic_flags, recommended_objective_action
from src.filters import apply_global_filters, render_sidebar
from src.formatting import PRIORITY_CONVERSIONS_HELP, apply_page_style, kpi_card, money, number, render_conversion_model_debug, render_data_source_debug
from src.google_sheets import load_workbook
from src.metrics import summarize
from src.tables import render_table
from src.transforms import combine_primary_data


ENROLLMENT_COLUMNS = [
    "campaign", "spend", "clicks", "ctr", "cpc", "total_conversions", "enrollment_apply_now_clicks",
    "enrollment_forms", "priority_conversions", "priority_cpa", "primary_issue", "recommended_action",
]
RECRUITMENT_COLUMNS = [
    "campaign", "spend", "clicks", "ctr", "cpc", "career_clicks", "applications_submitted",
    "priority_conversions", "priority_cpa", "primary_issue", "recommended_action",
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


def campaign_diagnostics(campaign, objective):
    perf = summarize(campaign[campaign["objective"].eq(objective)], ["objective", "campaign"])
    if perf.empty:
        return perf
    if "conversion_mapping_status" in campaign.columns:
        unmapped = (
            campaign[campaign["objective"].eq(objective)]
            .groupby("campaign")["conversion_mapping_status"]
            .apply(lambda values: "Unmapped" if values.eq("Unmapped").any() else "Mapped or inferred")
            .rename("conversion_mapping_status")
        )
        perf = perf.merge(unmapped, on="campaign", how="left")
    local_issues = perf.apply(objective_diagnostic_flags, axis=1)
    local_actions = perf.apply(recommended_objective_action, axis=1)
    if "primary_issue" not in perf.columns:
        perf["primary_issue"] = local_issues
    else:
        perf["primary_issue"] = perf["primary_issue"].fillna("").where(perf["primary_issue"].fillna("").ne(""), local_issues)
    if "recommended_action" not in perf.columns:
        perf["recommended_action"] = local_actions
    else:
        perf["recommended_action"] = perf["recommended_action"].fillna("").where(perf["recommended_action"].fillna("").ne(""), local_actions)
    return perf.sort_values(["priority_conversions", "spend"], ascending=[True, False])


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
campaign = apply_global_filters(campaign, filters)

if campaign.empty:
    st.warning("No objective-level campaign data is available with the current filters.")
    st.stop()

objective = summarize(campaign, ["objective"]).sort_values("spend", ascending=False)
enrollment = objective_row(objective, "Enrollment")
recruitment = objective_row(objective, "Recruitment")
enrollment_table = campaign_diagnostics(campaign, "Enrollment")
recruitment_table = campaign_diagnostics(campaign, "Recruitment")

st.header("Enrollment Performance")
cols = st.columns(4)
with cols[0]: kpi_card("Spend", money(enrollment["spend"]))
with cols[1]: kpi_card("Clicks", number(enrollment["clicks"]))
with cols[2]: kpi_card("Enrollment Apply Now Clicks", number(enrollment["enrollment_apply_now_clicks"], 1))
with cols[3]: kpi_card("Enrollment Forms", number(enrollment["enrollment_forms"], 1))
cols = st.columns(4)
with cols[0]: kpi_card("Enrollment Priority Conversions", number(enrollment["priority_conversions"], 1), help_text=PRIORITY_CONVERSIONS_HELP)
with cols[1]: kpi_card("Cost per Apply Now Click", money(enrollment["cost_per_enrollment_apply_click"]))
with cols[2]: kpi_card("Cost per Enrollment Form", money(enrollment["cost_per_enrollment_form"]))
with cols[3]: kpi_card("Enrollment Priority CPA", money(enrollment["priority_cpa"]), help_text=PRIORITY_CONVERSIONS_HELP)
if enrollment["enrollment_apply_now_clicks"] > 0 and enrollment["enrollment_forms"] == 0:
    st.warning("Apply Now intent is not translating into form submissions.")
enrollment_fig = objective_funnel_bar(campaign, "Enrollment", "Enrollment: Apply Now clicks vs forms by campaign")
if enrollment_fig.data:
    st.plotly_chart(enrollment_fig, use_container_width=True)
else:
    st.info("Enrollment funnel chart is unavailable because Apply Now/Form outcome columns are missing or zero for the selected filters.")
render_table(enrollment_table, "Enrollment campaign diagnostics", "Identify campaigns with spend but no Apply Now clicks or forms, and Apply Now interest that is not becoming forms.", key="enrollment_diagnostics", display_columns=ENROLLMENT_COLUMNS)

st.header("Recruitment Performance")
cols = st.columns(4)
with cols[0]: kpi_card("Spend", money(recruitment["spend"]))
with cols[1]: kpi_card("Clicks", number(recruitment["clicks"]))
with cols[2]: kpi_card("Career Clicks", number(recruitment["career_clicks"], 1), help_text="Career Clicks are a mid-funnel recruitment intent metric. They do not count as Priority Conversions.")
with cols[3]: kpi_card("Applications Submitted", number(recruitment["applications_submitted"], 1))
cols = st.columns(4)
with cols[0]: kpi_card("Recruitment Priority Conversions", number(recruitment["priority_conversions"], 1), help_text=PRIORITY_CONVERSIONS_HELP)
with cols[1]: kpi_card("Cost per Career Click", money(recruitment["cost_per_career_click"]))
with cols[2]: kpi_card("Cost per Application Submitted", money(recruitment["cost_per_application_submitted"]))
with cols[3]: kpi_card("Recruitment Priority CPA", money(recruitment["priority_cpa"]), help_text=PRIORITY_CONVERSIONS_HELP)
if recruitment["career_clicks"] > 0 and recruitment["applications_submitted"] == 0:
    st.warning("Career interest is not translating into submitted applications.")
recruitment_fig = objective_funnel_bar(campaign, "Recruitment", "Recruitment: career clicks vs applications submitted by campaign")
if recruitment_fig.data:
    st.plotly_chart(recruitment_fig, use_container_width=True)
else:
    st.info("Recruitment funnel chart is unavailable because Career Click/Application outcome columns are missing or zero for the selected filters.")
render_table(recruitment_table, "Recruitment campaign diagnostics", "Identify campaigns creating career interest without submitted applications.", key="recruitment_diagnostics", display_columns=RECRUITMENT_COLUMNS)

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

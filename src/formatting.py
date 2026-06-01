import math
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
        "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
        "cpa": st.column_config.NumberColumn("CPA", format="$%.0f"),
        "priority_cpa": st.column_config.NumberColumn("Priority CPA", format="$%.0f"),
        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
        "cvr": st.column_config.NumberColumn("CVR", format="%.2f%%"),
        "spend_share": st.column_config.NumberColumn("Spend Share", format="%.1f%%"),
        "click_share": st.column_config.NumberColumn("Click Share", format="%.1f%%"),
        "conversion_share": st.column_config.NumberColumn("Conversion Share", format="%.1f%%"),
        "impressions": st.column_config.NumberColumn("Impressions", format="%d"),
        "clicks": st.column_config.NumberColumn("Clicks", format="%d"),
        "conversions": st.column_config.NumberColumn("Conversions", format="%.1f"),
        "total_conversions": st.column_config.NumberColumn("Total Conversions", format="%.1f"),
        "priority_conversions": st.column_config.NumberColumn("Priority Conversions", format="%.1f"),
        "enrollment_apply_now_clicks": st.column_config.NumberColumn("Enrollment Apply Now Clicks", format="%.1f"),
        "enrollment_forms": st.column_config.NumberColumn("Enrollment Forms", format="%.1f"),
        "career_clicks": st.column_config.NumberColumn("Career Clicks", format="%.1f"),
        "applications_submitted": st.column_config.NumberColumn("Applications Submitted", format="%.1f"),
        "micro_conversions": st.column_config.NumberColumn("Other / Micro Conversions", format="%.1f"),
        "priority_score": st.column_config.NumberColumn("Priority Score", format="%d"),
    }

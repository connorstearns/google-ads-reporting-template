import streamlit as st
from src.formatting import apply_page_style, money, number, percent, kpi_card
from src.google_sheets import load_workbook
from src.transforms import combine_primary_data
from src.filters import render_sidebar, apply_global_filters
from src.metrics import summarize
from src.charts import metric_trend_line, objective_mix_bar, conversion_mix_stacked_bar
from src.tables import render_table


st.set_page_config(page_title="Objective Overview | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Objective Overview")
st.caption("Compare enrollment and recruitment performance, efficiency, and conversion mix.")

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
selected = objective.iloc[0] if not objective.empty else None

cols = st.columns(5)
if selected is not None:
    with cols[0]: kpi_card("Spend", money(selected.spend))
    with cols[1]: kpi_card("Clicks", number(selected.clicks))
    with cols[2]: kpi_card("Conversions", number(selected.conversions, 1))
    with cols[3]: kpi_card("CPA", money(selected.cpa))
    with cols[4]: kpi_card("Quality CPA", money(selected.quality_cpa))

left, right = st.columns(2)
with left:
    st.plotly_chart(objective_mix_bar(campaign, "spend", "Spend by objective"), use_container_width=True)
with right:
    st.plotly_chart(objective_mix_bar(campaign, "quality_conversions", "Quality conversions by objective"), use_container_width=True)

st.plotly_chart(metric_trend_line(campaign, "spend", "Weekly spend trend by objective"), use_container_width=True)
st.plotly_chart(conversion_mix_stacked_bar(campaign, "Conversion mix by objective"), use_container_width=True)

render_table(objective, "Objective performance", "Use this table to compare budget alignment, demand generation, and lead efficiency.", key="objective")
render_table(summarize(campaign, ["objective", "campaign"]), "Objective by campaign", "Campaign-level breakout within each objective.", key="objective_campaign")

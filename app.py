import streamlit as st
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.transforms import combine_primary_data
from src.filters import render_sidebar, apply_global_filters
from src.metrics import summarize, period_delta, share_columns
from src.formatting import money, number, percent, signed_percent, kpi_card
from src.charts import spend_vs_conversions_bar_line, objective_mix_bar, top_n_bar
from src.tables import render_table


st.set_page_config(page_title="HCZ Google Ads Dashboard", layout="wide")
apply_page_style()

st.title("HCZ Google Ads Executive Summary")
st.caption("Internal reporting dashboard for spend, traffic, conversion quality, and optimization priorities.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet.")
    st.info("Check that .streamlit/secrets.toml contains a valid service account and that the service account email has access to the workbook.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
filters = render_sidebar([campaign, search, landing], validation)
campaign = apply_global_filters(campaign, filters)
search = apply_global_filters(search, filters)
landing = apply_global_filters(landing, filters)

summary = summarize(campaign)
if summary.empty or campaign.empty:
    st.warning("No campaign performance data is available yet. Add a model_campaign_performance tab or another supported campaign tab.")
    st.stop()

row = summary.iloc[0]
deltas = {}
if filters.get("date_range") and len(filters["date_range"]) == 2:
    import pandas as pd
    deltas = period_delta(campaign, pd.to_datetime(filters["date_range"][0]), pd.to_datetime(filters["date_range"][1]))

cols = st.columns(5)
with cols[0]: kpi_card("Spend", money(row.spend), signed_percent(deltas.get("spend")), "Media cost in selected period.")
with cols[1]: kpi_card("Impressions", number(row.impressions), None)
with cols[2]: kpi_card("Clicks", number(row.clicks), signed_percent(deltas.get("clicks")))
with cols[3]: kpi_card("CTR", percent(row.ctr), signed_percent(deltas.get("ctr")))
with cols[4]: kpi_card("CPC", money(row.cpc, 2), None)
cols = st.columns(4)
with cols[0]: kpi_card("Conversions", number(row.conversions, 1), signed_percent(deltas.get("conversions")))
with cols[1]: kpi_card("CPA", money(row.cpa), signed_percent(deltas.get("cpa")))
with cols[2]: kpi_card("Quality conversions", number(row.quality_conversions, 1), None)
with cols[3]: kpi_card("Quality CPA", money(row.quality_cpa), None)

st.plotly_chart(spend_vs_conversions_bar_line(campaign), use_container_width=True)

left, right = st.columns(2)
with left:
    st.plotly_chart(objective_mix_bar(campaign, "spend", "Spend by objective"), use_container_width=True)
with right:
    st.plotly_chart(objective_mix_bar(campaign, "conversions", "Conversions by objective"), use_container_width=True)

objective = share_columns(summarize(campaign, ["objective"])).sort_values("spend", ascending=False)
campaign_summary = summarize(campaign, ["objective", "campaign"]).sort_values("spend", ascending=False)

st.subheader("What to look at")
notes = []
if not campaign_summary.empty:
    top = campaign_summary.iloc[0]
    spend_share = top.spend / campaign_summary.spend.sum() if campaign_summary.spend.sum() else 0
    notes.append(f"Spend is concentrated in {top.campaign}, which accounts for {percent(spend_share)} of filtered spend.")
if "Enrollment" in objective.get("objective", []).values:
    enroll = objective[objective.objective.eq("Enrollment")].iloc[0]
    notes.append(f"Enrollment accounts for {percent(enroll.conversion_share)} of conversions.")
zero_quality = campaign_summary[(campaign_summary.spend > 0) & (campaign_summary.quality_conversions == 0)]
if not zero_quality.empty:
    notes.append(f"{len(zero_quality)} campaigns have spend but no quality conversions.")
if not search.empty and "objective" in search.columns:
    unmapped_spend = search.loc[search.objective.eq("Other / Unmapped"), "spend"].sum()
    total_spend = search["spend"].sum()
    notes.append(f"{percent(unmapped_spend / total_spend if total_spend else 0)} of search term spend is currently unmapped.")
for note in notes or ["Load more model data to populate automated diagnostic readouts."]:
    st.write(f"- {note}")

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(top_n_bar(campaign, "campaign", "spend", 10, "Top campaigns by spend"), use_container_width=True)
with col2:
    st.plotly_chart(top_n_bar(campaign, "campaign", "quality_conversions", 10, "Top campaigns by quality conversions"), use_container_width=True)

render_table(objective, "Objective split", "Spend, traffic, and efficiency by objective.", key="objective_split")
render_table(campaign_summary.head(50), "Campaign diagnostics", "Top campaign rows sorted by spend.", key="campaign_diagnostics")

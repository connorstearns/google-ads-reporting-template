import streamlit as st
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.transforms import combine_primary_data
from src.filters import render_sidebar, apply_global_filters
from src.metrics import summarize
from src.charts import top_n_bar
from src.tables import render_table


st.set_page_config(page_title="Landing Page Analysis | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Landing Page Analysis")
st.caption("Understand final URL performance, page intent quality, and mapping gaps.")

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
    st.info("Landing page data is not available yet. Add a model_landing_pages tab with final_url, campaign, spend, impressions, clicks, and conversions.")
    st.stop()

if "page_group" not in landing.columns:
    landing["page_group"] = landing["final_url"].astype(str).str.lower().map(
        lambda url: "Recruitment" if any(x in url for x in ["career", "teacher", "classroom", "facilities", "food-services"]) else
        "Enrollment" if any(x in url for x in ["enrollment", "kindergarten", "lottery", "scholar", "apply-today"]) else
        "Other / Unmapped"
    )

page_perf = summarize(landing, ["objective", "campaign", "final_url", "page_group"])
page_perf["review_flag"] = ""
page_perf.loc[(page_perf["spend"] > 0) & (page_perf["quality_conversions"] == 0), "review_flag"] = "Spend with weak conversion quality"
page_perf.loc[page_perf["page_group"].eq("Other / Unmapped"), "review_flag"] = page_perf["review_flag"].where(page_perf["review_flag"].eq(""), page_perf["review_flag"] + "; ") + "URL mapping gap"

left, right = st.columns(2)
with left:
    st.plotly_chart(top_n_bar(landing, "page_group", "spend", 10, "Spend by page group"), use_container_width=True)
with right:
    st.plotly_chart(top_n_bar(landing, "final_url", "conversions", 15, "Conversions by landing page"), use_container_width=True)

weak = page_perf[(page_perf["spend"] > 0) & (page_perf["quality_conversions"] == 0)].sort_values("spend", ascending=False)
unmapped = page_perf[page_perf["page_group"].eq("Other / Unmapped")]

render_table(page_perf, "Landing page performance", "Final URL view for spend, traffic, quality outcomes, and efficiency.", key="landing_pages")
render_table(weak, "Landing pages with weak intent quality", "Pages receiving spend without quality conversions.", key="weak_landing")
render_table(unmapped, "URL mapping gaps", "Landing pages that need a page group or objective mapping.", key="unmapped_landing")

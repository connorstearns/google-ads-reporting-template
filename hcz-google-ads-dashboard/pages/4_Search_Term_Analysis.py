import streamlit as st
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.transforms import combine_primary_data
from src.filters import render_sidebar, apply_global_filters
from src.metrics import summarize
from src.charts import top_n_bar
from src.tables import render_table


st.set_page_config(page_title="Search Term Analysis | HCZ Google Ads", layout="wide")
apply_page_style()
st.title("Search Term Analysis")
st.caption("Identify query quality, waste, intent mismatches, and mapping gaps.")

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
    st.info("Search term data is not available yet. Add a model_search_terms tab with search_term, campaign, spend, impressions, clicks, and conversions.")
    st.stop()

if "search_term_category" not in search.columns:
    search["search_term_category"] = "Other / Unmapped"

def flag(row):
    text = f"{row.get('search_term', '')} {row.get('campaign', '')}".lower()
    flags = []
    if row.spend > 0 and row.conversions == 0:
        flags.append("High spend / no conversion")
    if row.objective == "Enrollment" and any(x in text for x in ["career", "job", "teacher"]):
        flags.append("Career term in enrollment campaign")
    if row.objective == "Recruitment" and any(x in text for x in ["enroll", "kindergarten", "scholar", "lottery"]):
        flags.append("Enrollment term in recruitment campaign")
    if row.search_term_category == "Other / Unmapped":
        flags.append("Unmapped category")
    return "; ".join(flags)

search["review_flag"] = search.apply(flag, axis=1)
term_perf = summarize(search, ["objective", "campaign", "ad_group", "search_term", "search_term_category"] if "ad_group" in search.columns else ["objective", "campaign", "search_term", "search_term_category"])
flags = search.groupby("search_term", as_index=False)["review_flag"].first()
term_perf = term_perf.merge(flags, on="search_term", how="left")

left, right = st.columns(2)
with left:
    st.plotly_chart(top_n_bar(search, "search_term_category", "spend", 10, "Spend by search term category"), use_container_width=True)
with right:
    st.plotly_chart(top_n_bar(search, "search_term", "conversions", 15, "Top search terms by conversions"), use_container_width=True)

negative_candidates = term_perf[(term_perf["spend"] > 0) & (term_perf["conversions"] == 0)].sort_values("spend", ascending=False)
unmapped = term_perf[term_perf["search_term_category"].eq("Other / Unmapped")]

render_table(term_perf, "Search term table", "Review search terms by intent, efficiency, and mapping status.", key="search_terms")
render_table(negative_candidates, "Negative keyword review candidates", "Queries with spend and no measured conversions.", key="negative_candidates")
render_table(unmapped, "Unmapped search terms", "Terms that need category or objective mapping.", key="unmapped_search_terms")

import streamlit as st
from src.formatting import apply_page_style
from src.google_sheets import load_workbook
from src.transforms import combine_primary_data
from src.filters import render_sidebar, apply_global_filters
from src.review import build_review_queue
from src.tables import render_table


apply_page_style()
st.title("Review Queue")
st.caption("Prioritized action list for campaign, search term, landing page, and mapping review.")

try:
    data, validation, _ = load_workbook()
except Exception as exc:
    st.error("Could not load the Google Sheet. Check credentials and workbook access.")
    st.exception(exc)
    st.stop()

campaign, search, landing = combine_primary_data(data)
sheet_queue = data.get("review_queue")
filters = render_sidebar([campaign, search, landing, sheet_queue], validation, thresholds=True)
campaign = apply_global_filters(campaign, filters)
search = apply_global_filters(search, filters)
landing = apply_global_filters(landing, filters)
sheet_queue = apply_global_filters(sheet_queue, filters) if sheet_queue is not None else sheet_queue

queue = sheet_queue.copy() if sheet_queue is not None and not sheet_queue.empty else build_review_queue(campaign, search, landing, filters["thresholds"])
if queue.empty:
    st.success("No review queue items match the current filters and thresholds.")
    st.stop()

if "priority_score" not in queue.columns:
    queue["priority_score"] = 0
if "spend" not in queue.columns:
    queue["spend"] = 0
if "issue_type" not in queue.columns:
    queue["issue_type"] = queue.get("primary_issue", "Review item")
if "entity_name" not in queue.columns:
    queue["entity_name"] = queue.get("campaign", queue.get("search_term", queue.get("final_url", "Review item")))
if "recommended_action" not in queue.columns:
    queue["recommended_action"] = queue.get("action", "")

top = queue.groupby("issue_type", as_index=False).agg(priority_score=("priority_score", "sum"), spend=("spend", "sum")).sort_values("priority_score", ascending=False)
render_table(top, "Issue summary", "Rollup of active optimization issues by category.", key="issue_summary")
render_table(queue, "Prioritized review queue", "Work from highest priority score and spend first.", sort_by="priority_score", search_cols=["entity_name", "issue_type", "recommended_action"], key="review_queue")

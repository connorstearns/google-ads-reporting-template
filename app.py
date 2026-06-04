import streamlit as st

st.set_page_config(
    page_title="Executive Summary",
    page_icon="\U0001F4CA",
    layout="wide",
)


pages = [
    st.Page("pages/1_Executive_Summary.py", title="Executive Summary", icon="\U0001F4CA"),
    st.Page("pages/2_Objective_Overview.py", title="Objective Overview", icon="\U0001F3AF"),
    st.Page("pages/3_Campaign_Performance.py", title="Campaign Performance", icon="\U0001F4C8"),
    st.Page("pages/7_Benchmarking.py", title="Benchmarking", icon="\U0001F4CF"),
    st.Page("pages/4_Search_Term_Analysis.py", title="Search Term Analysis", icon="\U0001F50E"),
    st.Page("pages/5_Landing_Page_Analysis.py", title="Landing Page Analysis", icon="\U0001F9ED"),
]

pg = st.navigation(pages)
pg.run()

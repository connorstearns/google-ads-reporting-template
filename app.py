import streamlit as st

st.set_page_config(
    page_title="Executive Summary",
    page_icon="📊",
    layout="wide",
)


pages = [
    st.Page("pages/1_Executive_Summary.py", title="Executive Summary", icon="📊"),
    st.Page("pages/2_Objective_Overview.py", title="Objective Overview"),
    st.Page("pages/3_Campaign_Performance.py", title="Campaign Performance"),
    st.Page("pages/4_Search_Term_Analysis.py", title="Search Term Analysis"),
    st.Page("pages/5_Landing_Page_Analysis.py", title="Landing Page Analysis"),
    st.Page("pages/6_Review_Queue.py", title="Review Queue"),
    st.Page("pages/7_Benchmarking.py", title="Benchmarking"),
]

pg = st.navigation(pages)
pg.run()

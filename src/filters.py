import pandas as pd
import streamlit as st
from .google_sheets import clear_data_cache
from .config import DEFAULT_THRESHOLDS


def render_sidebar(dataframes, validation=None, thresholds=False):
    st.sidebar.header("Filters")
    if st.sidebar.button("Refresh data", use_container_width=True):
        clear_data_cache()
        st.rerun()

    combined = pd.concat([df for df in dataframes if df is not None and not df.empty], ignore_index=True) if any(not df.empty for df in dataframes) else pd.DataFrame()
    date_range = None
    if "date" in combined.columns and combined["date"].notna().any():
        min_date, max_date = combined["date"].min().date(), combined["date"].max().date()
        date_range = st.sidebar.date_input("Date range", (min_date, max_date), min_value=min_date, max_value=max_date)
        st.sidebar.caption(f"Data through {max_date:%b %d, %Y}")

    objective = multiselect_if_available("Objective", combined, "objective")
    campaign = multiselect_if_available("Campaign", combined, "campaign")
    network = multiselect_if_available("Network", combined, "network")
    device = multiselect_if_available("Device", combined, "device")

    threshold_values = DEFAULT_THRESHOLDS.copy()
    if thresholds:
        st.sidebar.header("Review thresholds")
        threshold_values["min_spend"] = st.sidebar.number_input("Minimum spend", min_value=0.0, value=DEFAULT_THRESHOLDS["min_spend"], step=25.0)
        threshold_values["cpa"] = st.sidebar.number_input("CPA threshold", min_value=0.0, value=DEFAULT_THRESHOLDS["cpa"], step=25.0)
        threshold_values["ctr"] = st.sidebar.number_input("CTR threshold", min_value=0.0, max_value=1.0, value=DEFAULT_THRESHOLDS["ctr"], step=0.005, format="%.3f")
        threshold_values["cpc"] = st.sidebar.number_input("CPC threshold", min_value=0.0, value=DEFAULT_THRESHOLDS["cpc"], step=1.0)
        threshold_values["min_clicks"] = st.sidebar.number_input("Minimum clicks", min_value=0, value=DEFAULT_THRESHOLDS["min_clicks"], step=5)

    show_validation(validation)
    return {"date_range": date_range, "objective": objective, "campaign": campaign, "network": network, "device": device, "thresholds": threshold_values}


def multiselect_if_available(label, df, col):
    if col not in df.columns:
        return []
    values = sorted([v for v in df[col].dropna().unique() if str(v).strip()])
    return st.sidebar.multiselect(label, values)


def apply_global_filters(df, filters):
    if df.empty:
        return df
    out = df.copy()
    if filters.get("date_range") and "date" in out.columns:
        dates = filters["date_range"]
        if len(dates) == 2:
            start, end = pd.to_datetime(dates[0]), pd.to_datetime(dates[1])
            out = out[(out["date"] >= start) & (out["date"] <= end)]
    for col in ["objective", "campaign", "network", "device"]:
        selected = filters.get(col) or []
        if selected and col in out.columns:
            out = out[out[col].isin(selected)]
    return out


def show_validation(validation):
    if not validation:
        return
    with st.sidebar.expander("Data validation", expanded=False):
        for item in validation:
            icon = {"green": "[OK]", "yellow": "[WARN]", "red": "[MISSING]"}.get(item.status, "[INFO]")
            st.caption(f"{icon} {item.message}")
            if item.required_missing:
                st.caption(f"Missing required: {', '.join(item.required_missing)}")
            if item.optional_missing:
                st.caption(f"Missing optional: {', '.join(item.optional_missing)}")

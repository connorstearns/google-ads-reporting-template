import pandas as pd
import streamlit as st
from .google_sheets import clear_data_cache
from .config import DEFAULT_THRESHOLDS
from .periods import DATE_PRESETS, comparison_label, get_comparison_range, get_date_range_from_preset, latest_complete_month_range


def render_sidebar(dataframes, validation=None, thresholds=False, date_presets=True):
    st.sidebar.header("Filters")
    if st.sidebar.button("Refresh data", use_container_width=True):
        clear_data_cache()
        st.rerun()

    usable_frames = [df for df in dataframes if df is not None and not df.empty]
    combined = pd.concat(usable_frames, ignore_index=True) if usable_frames else pd.DataFrame()
    date_range = None
    comparison_range = None
    comparison_text = None
    date_preset = None
    if "date" in combined.columns and combined["date"].notna().any():
        min_date, max_date = combined["date"].min().date(), combined["date"].max().date()
        latest_start, latest_end, latest_is_partial = latest_complete_month_range(max_date, min_date)
        if date_presets:
            today = min(pd.Timestamp.today().normalize(), pd.Timestamp(max_date))
            date_preset = st.sidebar.selectbox("Date preset", DATE_PRESETS, index=0)
            if date_preset == "Custom range":
                selected = st.sidebar.date_input("Custom range", (latest_start.date(), latest_end.date()), min_value=min_date, max_value=max_date)
                start, end = (pd.Timestamp(selected[0]), pd.Timestamp(selected[1])) if len(selected) == 2 else (pd.Timestamp(min_date), pd.Timestamp(max_date))
            else:
                start, end = get_date_range_from_preset(date_preset, today, min_date)
            date_range = (start.date(), end.date())
            comp_start, comp_end, raw_comparison_label = get_comparison_range(start, end, date_preset)
            comparison_range = (comp_start.date(), comp_end.date()) if comp_start is not None and comp_end is not None else None
            comparison_text = comparison_label(raw_comparison_label)
            st.sidebar.caption(f"Current period: {start:%b %d, %Y} - {end:%b %d, %Y}")
            if comp_start is not None and comp_end is not None:
                st.sidebar.caption(f"Comparison: {comp_start:%b %d, %Y} - {comp_end:%b %d, %Y}")
        else:
            date_range = st.sidebar.date_input("Date range", (latest_start.date(), latest_end.date()), min_value=min_date, max_value=max_date)
        st.sidebar.caption(f"Data through {max_date:%b %d, %Y}")
        with st.sidebar.expander("Data status", expanded=False):
            st.caption(f"Data through: {max_date:%b %d, %Y}")
            st.caption(f"Latest complete month: {latest_start:%b %d, %Y} - {latest_end:%b %d, %Y}")
            if latest_is_partial:
                st.warning("Only partial current-month data is available; the default period is partial.")
            if date_range and len(date_range) == 2:
                st.caption(f"Selected period: {pd.Timestamp(date_range[0]):%b %d, %Y} - {pd.Timestamp(date_range[1]):%b %d, %Y}")
            if comparison_range:
                st.caption(f"Comparison period: {pd.Timestamp(comparison_range[0]):%b %d, %Y} - {pd.Timestamp(comparison_range[1]):%b %d, %Y}")

    objective = multiselect_if_available("Objective", combined, "objective")
    campaign = multiselect_if_available("Campaign", combined, "campaign")
    network = multiselect_if_available("Network", combined, "network")
    device = multiselect_if_available("Device", combined, "device")

    threshold_values = DEFAULT_THRESHOLDS.copy()
    if thresholds:
        st.sidebar.header("Decision thresholds")
        threshold_values["min_spend"] = st.sidebar.number_input("Minimum spend threshold", min_value=0.0, value=DEFAULT_THRESHOLDS["min_spend"], step=25.0)
        threshold_values["min_clicks"] = st.sidebar.number_input("Minimum clicks threshold", min_value=0, value=DEFAULT_THRESHOLDS["min_clicks"], step=5)
        threshold_values["cpa"] = st.sidebar.number_input("CPA threshold", min_value=0.0, value=DEFAULT_THRESHOLDS["cpa"], step=25.0)
        threshold_values["priority_cpa"] = st.sidebar.number_input("Priority CPA threshold", min_value=0.0, value=DEFAULT_THRESHOLDS["priority_cpa"], step=25.0)
        threshold_values["min_priority_conversions"] = st.sidebar.number_input("Minimum priority conversions threshold", min_value=1, value=DEFAULT_THRESHOLDS["min_priority_conversions"], step=1)
        with st.sidebar.expander("Diagnostic thresholds", expanded=False):
            threshold_values["ctr"] = st.number_input("CTR threshold", min_value=0.0, max_value=1.0, value=DEFAULT_THRESHOLDS["ctr"], step=0.005, format="%.3f")
            threshold_values["cpc"] = st.number_input("CPC threshold", min_value=0.0, value=DEFAULT_THRESHOLDS["cpc"], step=1.0)

    show_validation(validation)
    return {
        "date_range": date_range,
        "date_preset": date_preset,
        "comparison_range": comparison_range,
        "comparison_label": comparison_text,
        "objective": objective,
        "campaign": campaign,
        "network": network,
        "device": device,
        "thresholds": threshold_values,
    }


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

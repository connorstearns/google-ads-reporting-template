import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .config import OBJECTIVE_COLORS
from .metrics import summarize


def _layout(fig):
    fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=55, b=20), legend_title_text="")
    return fig


def metric_trend_line(df, metric="spend", title="Performance trend", freq="W"):
    if df.empty or "date" not in df.columns:
        return go.Figure()
    temp = df.dropna(subset=["date"]).copy()
    temp["period"] = temp["date"].dt.to_period(freq).dt.start_time
    grouped = summarize(temp, ["period", "objective"] if "objective" in temp.columns else ["period"])
    fig = px.line(grouped, x="period", y=metric, color="objective" if "objective" in grouped.columns else None,
                  markers=True, color_discrete_map=OBJECTIVE_COLORS, title=title, labels={"period": "Date", metric: metric.replace("_", " ").title()})
    return _layout(fig)


def spend_vs_conversions_bar_line(df, title="Spend and priority conversions over time", freq="W"):
    if df.empty or "date" not in df.columns:
        return go.Figure()
    temp = df.dropna(subset=["date"]).copy()
    temp["period"] = temp["date"].dt.to_period(freq).dt.start_time
    grouped = summarize(temp, ["period"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=grouped["period"], y=grouped["spend"], name="Spend", marker_color="#2563eb")
    fig.add_trace(go.Scatter(x=grouped["period"], y=grouped["priority_conversions"], name="Priority conversions", mode="lines+markers", line_color="#16a34a"), secondary_y=True)
    fig.update_yaxes(title_text="Spend ($)", tickprefix="$", secondary_y=False)
    fig.update_yaxes(title_text="Priority conversions", secondary_y=True)
    fig.update_layout(title=title)
    return _layout(fig)


def objective_mix_bar(df, metric="spend", title="Objective mix"):
    grouped = summarize(df, ["objective"]) if not df.empty and "objective" in df.columns else pd.DataFrame()
    fig = px.bar(grouped, x="objective", y=metric, color="objective", color_discrete_map=OBJECTIVE_COLORS,
                 title=title, labels={"objective": "Objective", metric: metric.replace("_", " ").title()})
    return _layout(fig)


def campaign_performance_scatter(df, y="cpa", title="Campaign efficiency"):
    if df.empty or "campaign" not in df.columns:
        return go.Figure()
    grouped = summarize(df, ["objective", "campaign"] if "objective" in df.columns else ["campaign"])
    fig = px.scatter(grouped, x="spend", y=y, size="conversions", color="objective" if "objective" in grouped.columns else None,
                     hover_name="campaign", color_discrete_map=OBJECTIVE_COLORS, title=title,
                     labels={"spend": "Spend", y: y.replace("_", " ").title(), "conversions": "Conversions"})
    fig.update_xaxes(tickprefix="$")
    fig.update_yaxes(tickprefix="$" if "cpa" in y or "cpc" in y else None)
    return _layout(fig)


def top_n_bar(df, group_col, metric="spend", n=10, title=None):
    if df.empty or group_col not in df.columns:
        return go.Figure()
    grouped = summarize(df, [group_col]).sort_values(metric, ascending=False).head(n)
    fig = px.bar(grouped.sort_values(metric), x=metric, y=group_col, orientation="h",
                 title=title or f"Top {n} by {metric}", labels={metric: metric.title(), group_col: group_col.replace("_", " ").title()})
    if metric in {"spend", "cpa", "cpc", "priority_cpa", "quality_cpa"}:
        fig.update_xaxes(tickprefix="$")
    return _layout(fig)


def conversion_mix_stacked_bar(df, title="Conversion mix"):
    if df.empty or "objective" not in df.columns:
        return go.Figure()
    metrics = ["enrollment_apply_now_clicks", "enrollment_forms", "applications_submitted", "career_clicks", "other_micro_conversions"]
    available = [metric for metric in metrics if metric in df.columns]
    grouped = df.groupby("objective", dropna=False, as_index=False)[available].sum()
    grouped = grouped.melt(id_vars="objective", var_name="conversion_type", value_name="conversions")
    grouped["conversion_type"] = grouped["conversion_type"].map(_conversion_mix_label)
    fig = px.bar(grouped, x="objective", y="conversions", color="conversion_type", title=title,
                 labels={"objective": "Objective", "conversion_type": "Conversion type"})
    return _layout(fig)


def weekly_heatmap_if_useful(df, metric="spend", title="Weekly heatmap"):
    if df.empty or "date" not in df.columns:
        return go.Figure()
    temp = df.dropna(subset=["date"]).copy()
    temp["week"] = temp["date"].dt.isocalendar().week.astype(int)
    temp["weekday"] = temp["date"].dt.day_name()
    pivot = temp.pivot_table(index="weekday", columns="week", values=metric, aggfunc="sum", fill_value=0)
    fig = px.imshow(pivot, aspect="auto", title=title, labels=dict(x="Week", y="Weekday", color=metric.title()))
    return _layout(fig)


def campaign_spend_priority_scatter(df, title="Spend vs priority conversions by campaign"):
    if df.empty:
        return go.Figure()
    size = df["clicks"].clip(lower=1)
    fig = px.scatter(
        df,
        x="spend",
        y="priority_conversions",
        size=size,
        color="status",
        hover_name="campaign",
        hover_data={
            "objective": True,
            "spend": ":$,.0f",
            "clicks": ":,.0f",
            "priority_conversions": ":,.1f",
            "priority_cpa": ":$,.0f",
            "status": True,
            "primary_issue": True,
        },
        title=title,
        labels={"spend": "Spend", "priority_conversions": "Priority conversions"},
    )
    fig.update_xaxes(tickprefix="$")
    return _layout(fig)


def campaign_priority_cpa_bar(df, min_spend, min_priority_conversions, title="Priority CPA by campaign"):
    meaningful = df[(df["spend"] >= min_spend) & (df["priority_conversions"] >= min_priority_conversions)].copy()
    if meaningful.empty:
        return go.Figure()
    meaningful = meaningful.sort_values("priority_cpa", ascending=False).head(15)
    fig = px.bar(
        meaningful.sort_values("priority_cpa"),
        x="priority_cpa",
        y="campaign",
        color="objective",
        orientation="h",
        color_discrete_map=OBJECTIVE_COLORS,
        title=title,
        labels={"priority_cpa": "Priority CPA", "campaign": "Campaign"},
    )
    fig.update_xaxes(tickprefix="$")
    return _layout(fig)


def campaign_conversion_mix_bar(df, title="Conversion mix by campaign"):
    if df.empty:
        return go.Figure()
    metrics = ["enrollment_apply_now_clicks", "enrollment_forms", "applications_submitted", "career_clicks", "other_micro_conversions"]
    available = [col for col in metrics if col in df.columns and df[col].sum() > 0]
    if not available:
        return go.Figure()
    top_campaigns = df.groupby("campaign", as_index=False)["spend"].sum().nlargest(12, "spend")["campaign"]
    melted = df[df["campaign"].isin(top_campaigns)].groupby("campaign", as_index=False)[available].sum()
    melted = melted.melt(id_vars="campaign", var_name="conversion_type", value_name="conversions")
    melted["conversion_type"] = melted["conversion_type"].map(_conversion_mix_label)
    fig = px.bar(
        melted,
        x="campaign",
        y="conversions",
        color="conversion_type",
        title=title,
        labels={"campaign": "Campaign", "conversions": "Conversions", "conversion_type": "Outcome"},
    )
    fig.update_xaxes(tickangle=-35)
    return _layout(fig)


def campaign_status_spend_bar(df, title="Spend by campaign status"):
    if df.empty:
        return go.Figure()
    grouped = df.groupby("status", as_index=False)["spend"].sum().sort_values("spend", ascending=False)
    fig = px.bar(grouped, x="status", y="spend", color="status", title=title, labels={"status": "Status", "spend": "Spend"})
    fig.update_yaxes(tickprefix="$")
    return _layout(fig)


def _conversion_mix_label(metric):
    return {
        "enrollment_apply_now_clicks": "Enrollment Apply Now Clicks",
        "enrollment_forms": "Enrollment Forms",
        "applications_submitted": "Applications Submitted",
        "career_clicks": "Career Clicks",
        "other_micro_conversions": "Other / Micro Conversions",
    }.get(metric, metric.replace("_", " ").title())


def objective_funnel_bar(df, objective, title):
    if df.empty or "campaign" not in df.columns:
        return go.Figure()
    if "objective" not in df.columns:
        return go.Figure()
    metrics = (
        ["enrollment_apply_now_clicks", "enrollment_forms"]
        if objective == "Enrollment"
        else ["career_clicks", "applications_submitted"]
    )
    filtered = df[df["objective"].astype(str).eq(objective)].copy()
    if filtered.empty:
        return go.Figure()
    for metric in metrics:
        if metric not in filtered.columns:
            filtered[metric] = 0
    grouped = summarize(filtered, ["campaign"])
    if grouped.empty or "campaign" not in grouped.columns:
        return go.Figure()
    for metric in metrics:
        if metric not in grouped.columns:
            grouped[metric] = 0
    available_metrics = [metric for metric in metrics if metric in grouped.columns]
    if not available_metrics or grouped[available_metrics].sum().sum() == 0:
        return go.Figure()
    grouped = grouped.melt(id_vars="campaign", value_vars=available_metrics, var_name="conversion_type", value_name="outcome_conversions")
    grouped["conversion_type"] = grouped["conversion_type"].map(_conversion_mix_label)
    fig = px.bar(grouped, x="campaign", y="outcome_conversions", color="conversion_type", barmode="group", title=title,
                 labels={"campaign": "Campaign", "outcome_conversions": "Conversions", "conversion_type": "Outcome"})
    fig.update_xaxes(tickangle=-35)
    return _layout(fig)


def objective_spend_priority_scatter(df, title="Spend vs priority conversions by objective"):
    if df.empty:
        return go.Figure()
    grouped = summarize(df, ["objective"])
    fig = px.scatter(grouped, x="spend", y="priority_conversions", color="objective", size="clicks",
                     color_discrete_map=OBJECTIVE_COLORS, hover_name="objective", title=title,
                     hover_data={"spend": ":$,.0f", "priority_conversions": ":,.1f", "priority_cpa": ":$,.0f", "clicks": ":,.0f"},
                     labels={"spend": "Spend", "priority_conversions": "Priority conversions"})
    fig.update_xaxes(tickprefix="$")
    return _layout(fig)

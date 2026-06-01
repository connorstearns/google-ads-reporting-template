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


def spend_vs_conversions_bar_line(df, title="Spend and conversions over time", freq="W"):
    if df.empty or "date" not in df.columns:
        return go.Figure()
    temp = df.dropna(subset=["date"]).copy()
    temp["period"] = temp["date"].dt.to_period(freq).dt.start_time
    grouped = summarize(temp, ["period"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=grouped["period"], y=grouped["spend"], name="Spend", marker_color="#2563eb")
    fig.add_trace(go.Scatter(x=grouped["period"], y=grouped["conversions"], name="Conversions", mode="lines+markers", line_color="#16a34a"), secondary_y=True)
    fig.update_yaxes(title_text="Spend ($)", tickprefix="$", secondary_y=False)
    fig.update_yaxes(title_text="Conversions", secondary_y=True)
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
    if metric in {"spend", "cpa", "cpc", "quality_cpa"}:
        fig.update_xaxes(tickprefix="$")
    return _layout(fig)


def conversion_mix_stacked_bar(df, title="Conversion mix"):
    if df.empty or "conversion_type" not in df.columns:
        return go.Figure()
    grouped = df.groupby(["objective", "conversion_type"], dropna=False, as_index=False)["conversions"].sum()
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


def campaign_spend_quality_scatter(df, title="Spend vs quality conversions by campaign"):
    if df.empty:
        return go.Figure()
    size = df["clicks"].clip(lower=1)
    fig = px.scatter(
        df,
        x="spend",
        y="quality_conversions",
        size=size,
        color="status",
        hover_name="campaign",
        hover_data={
            "objective": True,
            "spend": ":$,.0f",
            "clicks": ":,.0f",
            "quality_conversions": ":,.1f",
            "quality_cpa": ":$,.0f",
            "status": True,
            "primary_issue": True,
        },
        title=title,
        labels={"spend": "Spend", "quality_conversions": "Quality conversions"},
    )
    fig.update_xaxes(tickprefix="$")
    return _layout(fig)


def campaign_quality_cpa_bar(df, min_spend, min_quality_conversions, title="Quality CPA by campaign"):
    meaningful = df[(df["spend"] >= min_spend) & (df["quality_conversions"] >= min_quality_conversions)].copy()
    if meaningful.empty:
        return go.Figure()
    meaningful = meaningful.sort_values("quality_cpa", ascending=False).head(15)
    fig = px.bar(
        meaningful.sort_values("quality_cpa"),
        x="quality_cpa",
        y="campaign",
        color="objective",
        orientation="h",
        color_discrete_map=OBJECTIVE_COLORS,
        title=title,
        labels={"quality_cpa": "Quality CPA", "campaign": "Campaign"},
    )
    fig.update_xaxes(tickprefix="$")
    return _layout(fig)


def campaign_conversion_mix_bar(df, title="Conversion mix by campaign"):
    if df.empty:
        return go.Figure()
    metrics = ["enrollment_apply_clicks", "enrollment_forms", "career_clicks", "applications"]
    available = [col for col in metrics if col in df.columns and df[col].sum() > 0]
    if not available:
        return go.Figure()
    top_campaigns = df.groupby("campaign", as_index=False)["spend"].sum().nlargest(12, "spend")["campaign"]
    melted = df[df["campaign"].isin(top_campaigns)].groupby("campaign", as_index=False)[available].sum()
    melted = melted.melt(id_vars="campaign", var_name="conversion_type", value_name="conversions")
    melted["conversion_type"] = melted["conversion_type"].str.replace("_", " ").str.title()
    fig = px.bar(
        melted,
        x="campaign",
        y="conversions",
        color="conversion_type",
        title=title,
        labels={"campaign": "Campaign", "conversions": "Quality outcomes", "conversion_type": "Outcome"},
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

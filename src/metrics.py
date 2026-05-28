import numpy as np
import pandas as pd


def safe_divide(numerator, denominator):
    return np.where(np.asarray(denominator) == 0, 0, np.asarray(numerator) / np.asarray(denominator))


def add_core_metrics(df):
    out = df.copy()
    for col in ["spend", "impressions", "clicks", "conversions"]:
        if col not in out.columns:
            out[col] = 0
    out["ctr"] = safe_divide(out["clicks"], out["impressions"])
    out["cpc"] = safe_divide(out["spend"], out["clicks"])
    out["cvr"] = safe_divide(out["conversions"], out["clicks"])
    out["cpa"] = safe_divide(out["spend"], out["conversions"])
    if "quality_conversions" not in out.columns:
        out["quality_conversions"] = infer_quality_conversions(out)
    out["quality_cpa"] = safe_divide(out["spend"], out["quality_conversions"])
    return out


def infer_quality_conversions(df):
    cols = [c for c in ["applications", "enrollment_forms", "enrollment_apply_now_clicks", "career_clicks"] if c in df.columns]
    if cols:
        return df[cols].sum(axis=1)
    return df.get("conversions", pd.Series(0, index=df.index))


def summarize(df, group_cols=None):
    if df.empty:
        return add_core_metrics(pd.DataFrame())
    group_cols = group_cols or []
    numeric = ["spend", "impressions", "clicks", "conversions", "quality_conversions",
               "career_clicks", "applications", "enrollment_apply_now_clicks", "enrollment_forms"]
    agg = {c: "sum" for c in numeric if c in df.columns}
    if group_cols:
        out = df.groupby(group_cols, dropna=False, as_index=False).agg(agg)
    else:
        out = pd.DataFrame([df.agg(agg).to_dict()])
    return add_core_metrics(out)


def period_delta(df, start, end):
    if "date" not in df.columns or pd.isna(start) or pd.isna(end):
        return {}
    days = (end - start).days + 1
    prev_end = start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=days - 1)
    current = summarize(df[(df["date"] >= start) & (df["date"] <= end)])
    previous = summarize(df[(df["date"] >= prev_start) & (df["date"] <= prev_end)])
    if current.empty or previous.empty:
        return {}
    deltas = {}
    for col in ["spend", "clicks", "conversions", "cpa", "ctr"]:
        prev = previous.iloc[0].get(col, 0)
        cur = current.iloc[0].get(col, 0)
        deltas[col] = None if prev == 0 else (cur - prev) / prev
    return deltas


def share_columns(df):
    out = df.copy()
    for metric in ["spend", "clicks", "conversions"]:
        total = out[metric].sum() if metric in out.columns else 0
        out[f"{metric}_share"] = 0 if total == 0 else out[metric] / total
    return out

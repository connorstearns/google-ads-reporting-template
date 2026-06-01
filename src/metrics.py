import numpy as np
import pandas as pd


def safe_divide(numerator, denominator):
    numerator = np.asarray(numerator)
    denominator = np.asarray(denominator)
    return np.divide(numerator, denominator, out=np.zeros_like(numerator, dtype=float), where=denominator != 0)


def add_core_metrics(df):
    out = df.copy()
    for col in ["spend", "impressions", "clicks", "conversions"]:
        if col not in out.columns:
            out[col] = 0
    out = add_standardized_conversion_metrics(out)
    out["ctr"] = safe_divide(out["clicks"], out["impressions"])
    out["cpc"] = safe_divide(out["spend"], out["clicks"])
    out["cvr"] = safe_divide(out["total_conversions"], out["clicks"])
    out["cpa"] = safe_divide(out["spend"], out["total_conversions"])
    out["priority_cpa"] = safe_divide(out["spend"], out["priority_conversions"])
    # Temporary aliases for older pages and downstream workbook consumers.
    out["quality_conversions"] = out["priority_conversions"]
    out["quality_cpa"] = out["priority_cpa"]
    return out


def add_standardized_conversion_metrics(df):
    out = df.copy()
    if "enrollment_apply_now_clicks" not in out.columns:
        out["enrollment_apply_now_clicks"] = out.get("enrollment_apply_clicks", 0)
    if "applications_submitted" not in out.columns:
        out["applications_submitted"] = out.get("applications", 0)
    for col in ["enrollment_apply_now_clicks", "enrollment_forms", "applications_submitted", "career_clicks"]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    if "total_conversions" not in out.columns:
        out["total_conversions"] = out["conversions"]
    out["total_conversions"] = pd.to_numeric(out["total_conversions"], errors="coerce").fillna(0)
    out["conversions"] = out["total_conversions"]
    if "micro_conversions" not in out.columns:
        known = out[["enrollment_apply_now_clicks", "enrollment_forms", "applications_submitted", "career_clicks"]].sum(axis=1)
        out["micro_conversions"] = (out["total_conversions"] - known).clip(lower=0)
    out["micro_conversions"] = pd.to_numeric(out["micro_conversions"], errors="coerce").fillna(0)
    if "objective" in out.columns or "priority_conversions" not in out.columns:
        objective = out.get("objective", pd.Series("", index=out.index)).astype(str)
        out["priority_conversions"] = np.select(
            [objective.str.contains("enroll", case=False), objective.str.contains("recruit", case=False)],
            [out["enrollment_apply_now_clicks"] + out["enrollment_forms"], out["applications_submitted"]],
            default=0,
        )
    out["priority_conversions"] = pd.to_numeric(out["priority_conversions"], errors="coerce").fillna(0)
    return out


def summarize(df, group_cols=None):
    if df.empty:
        return add_core_metrics(pd.DataFrame())
    group_cols = group_cols or []
    numeric = ["spend", "impressions", "clicks", "conversions", "total_conversions", "priority_conversions",
               "micro_conversions", "quality_conversions", "career_clicks", "applications_submitted",
               "applications", "enrollment_apply_clicks", "enrollment_apply_now_clicks", "enrollment_forms"]
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
    for metric in ["spend", "clicks", "conversions", "total_conversions", "priority_conversions"]:
        total = out[metric].sum() if metric in out.columns else 0
        out[f"{metric}_share"] = 0 if total == 0 else out[metric] / total
    return out

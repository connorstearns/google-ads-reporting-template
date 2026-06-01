import re

import numpy as np
import pandas as pd


STANDARD_BUCKETS = [
    "enrollment_apply_now_clicks",
    "enrollment_forms",
    "applications_submitted",
    "career_clicks",
    "other_micro_conversions",
]
JOIN_KEY_CANDIDATES = [
    ["campaign_id", "date"],
    ["campaign", "date"],
    ["campaign_id", "month"],
    ["campaign", "month"],
    ["campaign_id"],
    ["campaign"],
]


def safe_divide(numerator, denominator):
    numerator, denominator = np.broadcast_arrays(np.asarray(numerator), np.asarray(denominator))
    return np.divide(numerator, denominator, out=np.zeros(numerator.shape, dtype=float), where=denominator != 0)


def add_standardized_conversion_metrics(df):
    out = df.copy()
    if "conversions" not in out.columns:
        out["conversions"] = out.get("total_conversions", 0)
    if "enrollment_apply_now_clicks" not in out.columns:
        out["enrollment_apply_now_clicks"] = out.get("enrollment_apply_clicks", 0)
    if "applications_submitted" not in out.columns:
        out["applications_submitted"] = out.get("applications", 0)
    if "other_micro_conversions" not in out.columns:
        out["other_micro_conversions"] = out.get("micro_conversions", 0)
    for col in STANDARD_BUCKETS:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    if "total_conversions" not in out.columns:
        out["total_conversions"] = out["conversions"]
    out["total_conversions"] = pd.to_numeric(out["total_conversions"], errors="coerce").fillna(0)
    out["conversions"] = out["total_conversions"]
    known = out[STANDARD_BUCKETS[:-1]].sum(axis=1)
    inferred_micro = (out["total_conversions"] - known).clip(lower=0)
    out["other_micro_conversions"] = out["other_micro_conversions"].where(out["other_micro_conversions"] > 0, inferred_micro)
    objective = out.get("objective", pd.Series("", index=out.index)).astype(str)
    out["priority_conversions"] = np.select(
        [objective.str.contains("enroll", case=False), objective.str.contains("recruit", case=False)],
        [out["enrollment_apply_now_clicks"] + out["enrollment_forms"], out["applications_submitted"]],
        default=0,
    )
    out["priority_cpa"] = safe_divide(out.get("spend", 0), out["priority_conversions"])
    out["cost_per_enrollment_apply_click"] = safe_divide(out.get("spend", 0), out["enrollment_apply_now_clicks"])
    out["cost_per_enrollment_form"] = safe_divide(out.get("spend", 0), out["enrollment_forms"])
    out["cost_per_application_submitted"] = safe_divide(out.get("spend", 0), out["applications_submitted"])
    out["cost_per_career_click"] = safe_divide(out.get("spend", 0), out["career_clicks"])
    # Temporary aliases for older pages and downstream workbook consumers.
    out["micro_conversions"] = out["other_micro_conversions"]
    out["quality_conversions"] = out["priority_conversions"]
    out["quality_cpa"] = out["priority_cpa"]
    return out


def classify_conversion_rows(df, mapping=None, conversion_quality=None):
    out = df.copy()
    if out.empty or "conversion_action" not in out.columns:
        return add_standardized_conversion_metrics(out)
    lookup = build_conversion_lookup(mapping, conversion_quality)
    out["_conversion_action_key"] = out["conversion_action"].apply(normalize_conversion_action_name)
    if lookup.empty:
        out["standardized_conversion_bucket"] = out["conversion_action"].apply(infer_standardized_bucket)
        out["conversion_metric_source"] = "Inferred logic"
        out["conversion_mapping_status"] = "Inferred"
    else:
        out = out.merge(lookup, on="_conversion_action_key", how="left")
        out["conversion_mapping_status"] = out["conversion_mapping_status"].fillna("Unmapped")
        out["conversion_metric_source"] = out["conversion_metric_source"].fillna("Unmapped")
        out["standardized_conversion_bucket"] = out["standardized_conversion_bucket"].fillna("other_micro_conversions")
    for bucket in STANDARD_BUCKETS:
        out[bucket] = out["conversions"].where(out["standardized_conversion_bucket"].eq(bucket), 0)
    out = out.drop(columns="_conversion_action_key")
    out["total_conversions"] = out["conversions"]
    return add_standardized_conversion_metrics(out)


def build_conversion_outcome_rollup(conversion_quality, conversion_mapping=None, group_cols=None):
    from .data_validation import coerce_types, normalize_columns

    detail = coerce_types(normalize_columns(conversion_quality.copy()))
    conversion_mapping = normalize_columns(conversion_mapping.copy()) if conversion_mapping is not None else None
    if detail.empty:
        return add_standardized_conversion_metrics(detail)
    if "conversions" not in detail.columns:
        detail["conversions"] = detail.get("all_conversions", 0)
    detail = classify_conversion_rows(detail, conversion_mapping, detail)
    group_cols = group_cols or _best_rollup_keys(detail)
    detail = _normalize_join_key_values(detail, group_cols)
    metrics = STANDARD_BUCKETS + ["total_conversions"]
    agg = {metric: "sum" for metric in metrics}
    if "objective" in detail.columns and "objective" not in group_cols:
        agg["objective"] = "first"
    rollup = detail.groupby(group_cols, dropna=False, as_index=False).agg(agg) if group_cols else pd.DataFrame([detail.agg(agg).to_dict()])
    rollup = add_standardized_conversion_metrics(rollup)
    rollup.attrs["conversion_audit"] = conversion_debug_audit(detail).to_dict("records")
    rollup.attrs["rollup_keys"] = group_cols
    return rollup


def join_conversion_outcomes(media, outcome_rollup):
    out = media.copy()
    debug = {
        "join_keys": [],
        "media_rows": len(out),
        "outcome_rollup_rows": len(outcome_rollup),
        "matched_media_rows": 0,
    }
    if out.empty or outcome_rollup.empty:
        enriched = add_standardized_conversion_metrics(out)
        enriched.attrs["conversion_join_debug"] = debug
        enriched.attrs["conversion_audit"] = outcome_rollup.attrs.get("conversion_audit", [])
        return enriched
    join_keys = _best_join_keys(out, outcome_rollup)
    debug["join_keys"] = join_keys
    if not join_keys:
        enriched = add_standardized_conversion_metrics(out)
        enriched.attrs["conversion_join_debug"] = debug
        enriched.attrs["conversion_audit"] = outcome_rollup.attrs.get("conversion_audit", [])
        return enriched
    outcome_metrics = STANDARD_BUCKETS + ["total_conversions"]
    out = _normalize_join_key_values(out, join_keys)
    rollup = _normalize_join_key_values(outcome_rollup[join_keys + outcome_metrics].copy(), join_keys)
    rollup = rollup.rename(columns={metric: f"{metric}_outcome" for metric in outcome_metrics})
    out["_media_join_row"] = np.arange(len(out))
    out["_join_weight"] = _join_allocation_weights(out, join_keys)
    out = out.merge(rollup, on=join_keys, how="left")
    debug["matched_media_rows"] = int(out[f"{STANDARD_BUCKETS[0]}_outcome"].notna().sum())
    for metric in STANDARD_BUCKETS:
        outcome_col = f"{metric}_outcome"
        out[metric] = out[outcome_col].fillna(0) * out["_join_weight"]
    out = out.drop(columns=[f"{metric}_outcome" for metric in outcome_metrics] + ["_join_weight", "_media_join_row"])
    enriched = add_standardized_conversion_metrics(out)
    enriched.attrs["conversion_join_debug"] = debug
    enriched.attrs["conversion_audit"] = outcome_rollup.attrs.get("conversion_audit", [])
    return enriched


def build_conversion_lookup(mapping=None, conversion_quality=None):
    frames = []
    for source_name, source in [("map_conversion_actions", mapping), ("model_conversion_quality", conversion_quality)]:
        if source is None or source.empty or "conversion_action" not in source.columns:
            continue
        frame = source.copy()
        bucket_cols = [
            col for col in [
                "standardized_conversion_bucket", "standardized_bucket", "conversion_bucket", "metric_bucket",
                "conversion_type", "conversion_category", "funnel_stage", "goal_group",
            ] if col in frame.columns
        ]
        if not bucket_cols:
            continue
        frame["standardized_conversion_bucket"] = frame[["conversion_action"] + bucket_cols].astype(str).agg(" ".join, axis=1).apply(normalize_mapped_bucket)
        frame["_conversion_action_key"] = frame["conversion_action"].apply(normalize_conversion_action_name)
        frame["conversion_metric_source"] = source_name
        frame["conversion_mapping_status"] = frame["standardized_conversion_bucket"].apply(
            lambda value: "Mapped" if value != "other_micro_conversions" else "Mapped as micro"
        )
        frames.append(frame[["_conversion_action_key", "standardized_conversion_bucket", "conversion_metric_source", "conversion_mapping_status"]])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates("_conversion_action_key", keep="first")


def normalize_conversion_action_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def validate_priority_business_rules(df):
    if df.empty:
        return []
    objective = df.get("objective", pd.Series("", index=df.index)).astype(str)
    enrollment = objective.str.contains("enroll", case=False)
    recruitment = objective.str.contains("recruit", case=False)
    issues = []
    expected_enrollment = df["enrollment_apply_now_clicks"] + df["enrollment_forms"]
    if not np.allclose(df.loc[enrollment, "priority_conversions"], expected_enrollment.loc[enrollment]):
        issues.append("Enrollment priority conversions must equal Apply Now clicks plus Enrollment Forms.")
    if not np.allclose(df.loc[recruitment, "priority_conversions"], df.loc[recruitment, "applications_submitted"]):
        issues.append("Recruitment priority conversions must equal Applications Submitted.")
    return issues


def normalize_mapped_bucket(value):
    text = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    canonical = text.replace(" ", "_")
    if text == "recruitment lead":
        return "applications_submitted"
    if text == "recruitment intent":
        return "career_clicks"
    if text == "enrollment lead":
        return "enrollment_forms"
    if text == "enrollment intent":
        return "enrollment_apply_now_clicks"
    if "application" in text and any(token in text for token in ["submit", "complete", "lead"]):
        return "applications_submitted"
    if any(token in text for token in ["career", "recruitment intent", "job"]) and any(token in text for token in ["click", "intent", "opportunit"]):
        return "career_clicks"
    if "enroll" in text and any(token in text for token in ["form", "lead"]):
        return "enrollment_forms"
    if "enroll" in text and any(token in text for token in ["apply", "intent"]):
        return "enrollment_apply_now_clicks"
    if canonical in STANDARD_BUCKETS:
        return canonical
    return "other_micro_conversions"


def infer_standardized_bucket(value):
    text = str(value or "").lower()
    if re.search(r"application.{0,12}(submit|complete)|submit.{0,12}application", text):
        return "applications_submitted"
    if re.search(r"career|job|teacher|recruit", text) and re.search(r"click|opportunit", text):
        return "career_clicks"
    if re.search(r"enroll|scholar|lottery|kindergarten|k-8|promise academy", text) and re.search(r"form|lead", text):
        return "enrollment_forms"
    if re.search(r"apply now|apply_now", text):
        return "enrollment_apply_now_clicks"
    return "other_micro_conversions"


def conversion_debug_audit(df):
    if df.empty or "conversion_action" not in df.columns:
        return pd.DataFrame()
    cols = ["conversion_action", "standardized_conversion_bucket", "conversion_metric_source", "conversion_mapping_status"]
    available = [col for col in cols if col in df.columns]
    audit = df[available + ["conversions"]].copy()
    return audit.groupby(available, dropna=False, as_index=False)["conversions"].sum().sort_values("conversions", ascending=False)


def objective_diagnostic_flags(row):
    issues = []
    objective = str(row.get("objective", ""))
    if objective.startswith("Other") or not objective:
        issues.append("Objective unmapped")
    if row.get("conversion_mapping_status") == "Unmapped":
        issues.append("Conversion action unmapped")
    if objective == "Enrollment" and row.get("spend", 0) > 0 and row.get("priority_conversions", 0) == 0:
        issues.append("Enrollment spend with no Apply Now clicks/forms")
    if objective == "Enrollment" and row.get("enrollment_apply_now_clicks", 0) > 0 and row.get("enrollment_forms", 0) == 0:
        issues.append("Enrollment Apply Now clicks but no forms")
    if objective == "Recruitment" and row.get("spend", 0) > 0 and row.get("applications_submitted", 0) == 0:
        issues.append("Recruitment spend with no applications submitted")
    if objective == "Recruitment" and row.get("career_clicks", 0) > 0 and row.get("applications_submitted", 0) == 0:
        issues.append("Career clicks but no applications submitted")
    if row.get("total_conversions", 0) > 0 and row.get("priority_conversions", 0) == 0:
        issues.append("Total conversions present but no priority conversions")
    return "; ".join(issues) or "No major issue"


def recommended_objective_action(row):
    issue = objective_diagnostic_flags(row)
    if "Objective unmapped" in issue:
        return "Complete campaign/objective mapping"
    if "Conversion action unmapped" in issue:
        return "Complete conversion action mapping"
    if "Career clicks but no applications submitted" in issue:
        return "Review recruitment landing page and application flow"
    if "Recruitment spend with no applications submitted" in issue:
        return "Review application submission tracking and funnel"
    if "Enrollment Apply Now clicks but no forms" in issue:
        return "Review enrollment form completion path"
    if "Enrollment spend with no Apply Now clicks/forms" in issue:
        return "Review enrollment conversion path"
    if "Total conversions present but no priority conversions" in issue:
        return "Check conversion mapping and optimization goals"
    return "Maintain and monitor"


def _best_rollup_keys(df):
    for keys in JOIN_KEY_CANDIDATES:
        if all(key in df.columns for key in keys):
            return keys
    return []


def _best_join_keys(media, outcomes):
    for keys in JOIN_KEY_CANDIDATES:
        if all(key in media.columns and key in outcomes.columns for key in keys):
            return keys
    return []


def _join_allocation_weights(df, join_keys):
    group_spend = df.groupby(join_keys, dropna=False)["spend"].transform("sum") if "spend" in df.columns else 0
    row_count = df.groupby(join_keys, dropna=False)[join_keys[0]].transform("size")
    if "spend" not in df.columns:
        return 1 / row_count
    return np.where(group_spend > 0, df["spend"] / group_spend, 1 / row_count)


def _normalize_join_key_values(df, join_keys):
    out = df.copy()
    for key in join_keys:
        if key == "date":
            out[key] = pd.to_datetime(out[key], errors="coerce")
        else:
            out[key] = out[key].astype(str).str.strip()
    return out

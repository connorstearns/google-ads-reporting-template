from .metrics import safe_divide, share_columns, summarize


OPTIONAL_CAMPAIGN_FIELDS = [
    "quality_conversions",
    "quality_cpa",
    "enrollment_apply_clicks",
    "enrollment_forms",
    "career_clicks",
    "applications",
    "objective",
    "ad_group",
]

STATUS_ORDER = {
    "Mapping Needed": 0,
    "Investigate": 1,
    "Optimize": 2,
    "Monitor": 3,
    "Scale": 4,
    "Maintain": 5,
}


def missing_optional_campaign_fields(source_df):
    columns = set(source_df.columns)
    missing = []
    for col in OPTIONAL_CAMPAIGN_FIELDS:
        if col == "enrollment_apply_clicks" and "enrollment_apply_now_clicks" in columns:
            continue
        if col not in columns:
            missing.append(col)
    return missing


def ensure_campaign_fields(df):
    out = df.copy()
    if "objective" not in out.columns:
        out["objective"] = "Other / Unmapped"
    out["objective"] = out["objective"].fillna("Other / Unmapped").replace("", "Other / Unmapped")
    if "campaign" not in out.columns:
        out["campaign"] = "Unknown campaign"
    if "enrollment_apply_clicks" not in out.columns:
        out["enrollment_apply_clicks"] = out.get("enrollment_apply_now_clicks", 0)
    for col in ["quality_conversions", "enrollment_forms", "career_clicks", "applications"]:
        if col not in out.columns:
            out[col] = 0
    return out


def build_campaign_decisions(df, thresholds, include_ad_group=True):
    prepared = ensure_campaign_fields(df)
    group_cols = ["objective", "campaign"]
    if include_ad_group and "ad_group" in prepared.columns:
        group_cols.append("ad_group")
    out = summarize(prepared, group_cols)
    out = ensure_campaign_fields(out)
    out = share_columns(out)
    out["quality_conversion_rate"] = safe_divide(out["quality_conversions"], out["conversions"])
    out["primary_issue"] = out.apply(lambda row: diagnose_campaign(row, thresholds), axis=1)
    out["status"] = out.apply(lambda row: classify_campaign(row, thresholds), axis=1)
    out["recommended_action"] = out.apply(recommend_action, axis=1)
    out["rationale"] = out.apply(lambda row: build_rationale(row, thresholds), axis=1)
    out["priority_score"] = out.apply(lambda row: priority_score(row, thresholds), axis=1)
    out["_status_order"] = out["status"].map(STATUS_ORDER).fillna(99)
    return out.sort_values(["_status_order", "priority_score", "spend"], ascending=[True, False, False]).drop(columns="_status_order")


def diagnose_campaign(row, thresholds):
    spend = row["spend"]
    clicks = row["clicks"]
    conversions = row["conversions"]
    quality_conversions = row["quality_conversions"]
    if row["objective"] in {"Other", "Other / Unmapped", "", None}:
        return "Mapping gap"
    if _has_objective_mismatch(row):
        return "Objective mismatch"
    if spend >= thresholds["min_spend"] and conversions == 0:
        return "Spend with no conversions"
    if spend >= thresholds["min_spend"] and quality_conversions == 0:
        return "Spend with no quality conversions"
    if spend < thresholds["min_spend"] or clicks < thresholds["min_clicks"]:
        return "Insufficient data"
    if row["ctr"] < thresholds["ctr"]:
        return "Low CTR"
    if row["cpc"] > thresholds["cpc"]:
        return "High CPC"
    if row["cvr"] < 0.03:
        return "Low CVR"
    if conversions > 0 and row["quality_conversion_rate"] < 0.25:
        return "Low quality conversion rate"
    return "No major issue"


def classify_campaign(row, thresholds):
    meaningful = row["spend"] >= thresholds["min_spend"] and row["clicks"] >= thresholds["min_clicks"]
    if row["objective"] in {"Other", "Other / Unmapped", "", None}:
        return "Mapping Needed"
    if meaningful and (row["quality_conversions"] == 0 or row["primary_issue"] == "Objective mismatch"):
        return "Investigate"
    if not meaningful:
        return "Monitor"
    if (
        row["quality_conversions"] > 0
        and row["quality_cpa"] > thresholds["quality_cpa"]
    ) or (
        row["conversions"] > 0
        and row["cpa"] > thresholds["cpa"]
    ):
        return "Optimize"
    if (
        row["quality_conversions"] >= thresholds["min_quality_conversions"]
        and 0 < row["quality_cpa"] <= thresholds["quality_cpa"]
    ):
        return "Scale"
    return "Maintain"


def recommend_action(row):
    issue = row["primary_issue"]
    if row["status"] == "Mapping Needed":
        return "Complete campaign/objective mapping"
    if issue == "Objective mismatch":
        return "Check conversion action quality"
    if issue == "Spend with no conversions":
        return "Reduce budget or pause if no signal"
    if issue in {"Spend with no quality conversions", "Low quality conversion rate"}:
        return "Check conversion action quality"
    if row["status"] == "Scale":
        return "Consider scaling gradually"
    if issue == "Low CTR":
        return "Review search terms"
    if issue in {"Low CVR", "High CPC"}:
        return "Review landing page alignment"
    if row["status"] == "Optimize":
        return "Review landing page alignment"
    if row["status"] == "Maintain":
        return "Maintain budget"
    return "Monitor until more data accrues"


def build_rationale(row, thresholds):
    if row["status"] == "Mapping Needed":
        return "Objective mapping is required before budget decisions can be trusted."
    if row["status"] == "Monitor":
        return f"Only ${row['spend']:,.0f} spend and {row['clicks']:,.0f} clicks; wait for a stronger signal."
    if row["status"] == "Investigate":
        return f"${row['spend']:,.0f} spend has produced {row['quality_conversions']:,.1f} quality conversions. Primary issue: {row['primary_issue']}."
    if row["status"] == "Optimize":
        return f"Efficiency needs work: CPA ${row['cpa']:,.0f}, quality CPA ${row['quality_cpa']:,.0f}. Primary issue: {row['primary_issue']}."
    if row["status"] == "Scale":
        return f"{row['quality_conversions']:,.1f} quality conversions at ${row['quality_cpa']:,.0f} quality CPA, below the ${thresholds['quality_cpa']:,.0f} threshold."
    return f"Performance is acceptable at ${row['quality_cpa']:,.0f} quality CPA, without enough quality volume to qualify for scaling."


def priority_score(row, thresholds):
    score = {
        "Mapping Needed": 95,
        "Investigate": 85,
        "Optimize": 65,
        "Monitor": 25,
        "Scale": 20,
        "Maintain": 10,
    }[row["status"]]
    score += min(20, int(safe_divide(row["spend"], max(thresholds["min_spend"], 1)) * 3))
    if row["primary_issue"] in {"Spend with no conversions", "Objective mismatch"}:
        score += 10
    return min(score, 100)


def _has_objective_mismatch(row):
    enrollment = row.get("enrollment_apply_clicks", 0) + row.get("enrollment_forms", 0)
    recruitment = row.get("career_clicks", 0) + row.get("applications", 0)
    return (row["objective"] == "Enrollment" and recruitment > enrollment and recruitment > 0) or (
        row["objective"] == "Recruitment" and enrollment > recruitment and enrollment > 0
    )

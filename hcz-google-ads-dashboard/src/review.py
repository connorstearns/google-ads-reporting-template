import pandas as pd
from .metrics import summarize


def add_review_flags(df, entity_col, entity_type, thresholds):
    if df.empty or entity_col not in df.columns:
        return pd.DataFrame()
    group_cols = ["objective", entity_col] if "objective" in df.columns else [entity_col]
    perf = summarize(df, group_cols)
    rows = []
    for _, r in perf.iterrows():
        issues = []
        score = 0
        if r.spend >= thresholds["min_spend"] and r.conversions == 0:
            issues.append(("High spend, no conversions", 3, "Review budget allocation"))
        if r.spend >= thresholds["min_spend"] and r.quality_conversions == 0:
            issues.append(("High spend, no quality conversions", 3, "Investigate conversion quality"))
        if r.conversions > 0 and r.cpa > thresholds["cpa"]:
            issues.append(("CPA above threshold", 2, "Review bids, targeting, and landing page alignment"))
        if r.clicks >= thresholds["min_clicks"] and r.ctr < thresholds["ctr"]:
            issues.append(("CTR below threshold", 1, "Review ad relevance and query alignment"))
        if r.clicks >= thresholds["min_clicks"] and r.cpc > thresholds["cpc"]:
            issues.append(("CPC above threshold", 1, "Check auction pressure and keyword match quality"))
        if str(r.get("objective", "")).startswith("Other"):
            issues.append(("Unmapped objective", 2, "Map objective"))
        for issue, points, action in issues:
            rows.append({
                "priority_score": score + points,
                "issue_type": issue,
                "entity_type": entity_type,
                "entity_name": r[entity_col],
                "objective": r.get("objective", "Other / Unmapped"),
                "spend": r.spend,
                "clicks": r.clicks,
                "conversions": r.conversions,
                "quality_conversions": r.quality_conversions,
                "cpa": r.cpa,
                "recommended_action": action,
                "notes": f"{entity_type} triggered {issue.lower()} under current thresholds.",
            })
    return pd.DataFrame(rows)


def build_review_queue(campaign, search, landing, thresholds):
    parts = [
        add_review_flags(campaign, "campaign", "Campaign", thresholds),
        add_review_flags(search, "search_term", "Search Term", thresholds),
        add_review_flags(landing, "final_url", "Landing Page", thresholds),
    ]
    queue = pd.concat([p for p in parts if not p.empty], ignore_index=True) if any(not p.empty for p in parts) else pd.DataFrame()
    if not queue.empty:
        queue = queue.sort_values(["priority_score", "spend"], ascending=False)
    return queue

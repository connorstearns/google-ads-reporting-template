import re
from dataclasses import dataclass
import pandas as pd


COLUMN_ALIASES = {
    "campaign_name": "campaign",
    "campaign": "campaign",
    "campaign_id": "campaign_id",
    "campaign_status": "campaign_status",
    "campaign_role": "campaign_role",
    "campaign_type": "campaign_type",
    "funnel_stage": "funnel_stage",
    "ad_group_name": "ad_group",
    "ad_group": "ad_group",
    "ad_group_cleaned": "ad_group_cleaned",
    "cost": "spend",
    "amount_spent": "spend",
    "spend": "spend",
    "impr": "impressions",
    "impressions": "impressions",
    "clicks": "clicks",
    "conv": "conversions",
    "conversions": "conversions",
    "reported_conversions": "reported_conversions",
    "all_conversions": "all_conversions",
    "reported_cpa": "reported_cpa",
    "conversion_action": "conversion_action",
    "conversion_action_name": "conversion_action",
    "conversion_type_name": "conversion_action",
    "conversion_name": "conversion_action",
    "conversion_tracker_name": "conversion_action",
    "conversion_action_type": "conversion_action",
    "conversion_type": "conversion_type",
    "conversion_category": "conversion_category",
    "quality_conversions": "quality_conversions",
    "quality_conversions_count": "quality_conversions",
    "priority_conversions": "priority_conversions",
    "priority_cpa": "priority_cpa",
    "micro_conversions": "micro_conversions",
    "other_micro_conversions": "other_micro_conversions",
    "total_conversions": "total_conversions",
    "primary_mapped_conversions": "primary_mapped_conversions",
    "micro_mapped_conversions": "micro_mapped_conversions",
    "career_clicks": "career_clicks",
    "applications": "applications",
    "applications_submitted": "applications_submitted",
    "enrollment_apply_now_clicks": "enrollment_apply_now_clicks",
    "enrollment_apply_clicks": "enrollment_apply_clicks",
    "enrollment_forms": "enrollment_forms",
    "search_term": "search_term",
    "search_terms": "search_term",
    "keyword": "keyword",
    "search_objective_group": "search_objective_group",
    "query_theme": "query_theme",
    "intent_level": "intent_level",
    "relevance": "relevance",
    "brand_nonbrand": "brand_nonbrand",
    "negative_keyword_candidate": "negative_keyword_candidate",
    "keyword_expansion_candidate": "keyword_expansion_candidate",
    "review_priority_score": "review_priority_score",
    "action_flag": "action_flag",
    "final_url": "final_url",
    "landing_page": "final_url",
    "landing_page_url": "final_url",
    "normalized_url": "normalized_url",
    "page_type": "page_type",
    "offer_program": "offer_program",
    "primary_cta": "primary_cta",
    "intent_match": "intent_match",
    "cro_priority": "cro_priority",
    "date": "date",
    "day": "date",
    "week": "week",
    "month": "month",
    "device": "device",
    "network": "network",
    "objective": "objective",
    "objective_raw": "objective_raw",
    "primary_kpi": "primary_kpi",
    "budget_group": "budget_group",
    "active_status": "active_status",
    "cost_apply_now_click": "cost_per_enrollment_apply_click",
    "cost_per_apply_now_click": "cost_per_enrollment_apply_click",
    "cost_enrollment_form": "cost_per_enrollment_form",
    "cost_per_enrollment_form": "cost_per_enrollment_form",
    "cost_career_click": "cost_per_career_click",
    "cost_per_career_click": "cost_per_career_click",
    "cost_application_submitted": "cost_per_application_submitted",
    "cost_per_application_submitted": "cost_per_application_submitted",
    "primary_issue": "primary_issue",
    "recommended_action": "recommended_action",
    "join_key": "join_key",
    "match_type": "match_type",
    "search_term_category": "search_term_category",
    "page_group": "page_group",
    "benchmark_status": "benchmark_status",
    "benchmark_note": "benchmark_note",
    "yoy_benchmark_status": "yoy_benchmark_status",
    "yoy_benchmark_note": "yoy_benchmark_note",
    "prior_year_spend": "prior_year_spend",
    "prior_year_clicks": "prior_year_clicks",
    "prior_year_priority_conversions": "prior_year_priority_conversions",
    "prior_year_priority_cpa": "prior_year_priority_cpa",
    "spend_yoy_pct": "spend_yoy_pct",
    "clicks_yoy_pct": "clicks_yoy_pct",
    "priority_conversions_yoy_pct": "priority_conversions_yoy_pct",
    "priority_cpa_yoy_pct": "priority_cpa_yoy_pct",
    "trailing_3mo_median_priority_cpa": "trailing_3mo_median_priority_cpa",
    "priority_cpa_vs_3mo_median": "priority_cpa_vs_3mo_median",
    "trailing_3mo_median_priority_conversions": "trailing_3mo_median_priority_conversions",
    "priority_conversions_vs_3mo_median": "priority_conversions_vs_3mo_median",
}


REQUIRED_COLUMNS = {
    "campaign_performance": {"campaign", "spend", "impressions", "clicks"},
    "objective_performance": {"spend", "impressions", "clicks", "conversions"},
    "search_terms": {"search_term", "campaign", "spend", "impressions", "clicks", "conversions"},
    "landing_pages": {"final_url", "campaign", "spend", "impressions", "clicks", "conversions"},
    "campaign_type_benchmarks": {"month", "campaign_type", "objective"},
}


OPTIONAL_COLUMNS = {
    "campaign_performance": {"date", "ad_group", "objective", "network", "device", "conversion_action", "final_url", "conversions"},
    "objective_performance": {"date", "month", "objective", "campaign"},
    "search_terms": {
        "date", "ad_group", "ad_group_cleaned", "objective", "keyword", "match_type",
        "search_objective_group", "query_theme", "intent_level", "relevance", "brand_nonbrand",
        "recommended_action", "negative_keyword_candidate", "keyword_expansion_candidate",
        "review_priority_score", "action_flag",
    },
    "landing_pages": {
        "date", "objective", "normalized_url", "all_conversions", "campaign_role", "page_type",
        "offer_program", "funnel_stage", "primary_cta", "intent_match", "cro_priority",
    },
}


@dataclass
class ValidationResult:
    tab_key: str
    tab_name: str
    status: str
    required_missing: list
    optional_missing: list
    message: str


def normalize_column_name(name):
    cleaned = str(name).strip().lower()
    cleaned = cleaned.replace("%", "pct")
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return COLUMN_ALIASES.get(cleaned, cleaned)


def normalize_columns(df):
    out = df.copy()
    out.columns = [normalize_column_name(c) for c in out.columns]
    out = out.loc[:, ~pd.Index(out.columns).duplicated()]
    return out


def coerce_types(df):
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    if "month" in out.columns:
        out["month"] = pd.to_datetime(out["month"], errors="coerce")
    for col in ["spend", "impressions", "clicks", "conversions", "reported_conversions", "all_conversions",
                "ctr", "cpc", "cvr", "cpa",
                "reported_cpa", "total_conversions", "priority_conversions",
                "priority_cpa", "micro_conversions", "other_micro_conversions", "quality_conversions", "career_clicks", "applications",
                "applications_submitted", "enrollment_apply_now_clicks", "enrollment_apply_clicks", "enrollment_forms",
                "primary_mapped_conversions", "micro_mapped_conversions", "cost_per_enrollment_apply_click",
                "cost_per_enrollment_form", "cost_per_career_click", "cost_per_application_submitted",
                "review_priority_score", "prior_year_spend", "prior_year_clicks",
                "prior_year_priority_conversions", "prior_year_priority_cpa",
                "trailing_3mo_median_priority_cpa", "trailing_3mo_median_priority_conversions",
                "current_value", "benchmark_value", "variance_pct",
                "spend_yoy_pct", "clicks_yoy_pct", "priority_conversions_yoy_pct",
                "priority_cpa_yoy_pct", "priority_cpa_vs_3mo_median",
                "priority_conversions_vs_3mo_median"]:
        if col in out.columns:
            raw = out[col].astype(str)
            percent_mask = raw.str.contains("%", regex=False)
            out[col] = (
                raw
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
            )
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
            out.loc[percent_mask, col] = out.loc[percent_mask, col] / 100
    return out


def validate_dataframe(tab_key, tab_name, df):
    if df is None or df.empty:
        return ValidationResult(tab_key, tab_name, "red", [], [], f"{tab_key} loaded from {tab_name} but is empty.")
    required = REQUIRED_COLUMNS.get(tab_key, set())
    optional = OPTIONAL_COLUMNS.get(tab_key, set())
    missing_required = sorted(required - set(df.columns))
    missing_optional = sorted(optional - set(df.columns))
    if missing_required:
        return ValidationResult(tab_key, tab_name, "red", missing_required, missing_optional, f"{tab_key} loaded from {tab_name} with required fields missing: {', '.join(missing_required)}")
    if missing_optional:
        return ValidationResult(tab_key, tab_name, "yellow", [], missing_optional, f"{tab_key} loaded from {tab_name} with optional fields missing: {', '.join(missing_optional)}")
    return ValidationResult(tab_key, tab_name, "green", [], [], f"{tab_key} loaded from {tab_name}")

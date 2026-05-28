import re
from dataclasses import dataclass
import pandas as pd


COLUMN_ALIASES = {
    "campaign_name": "campaign",
    "campaign": "campaign",
    "ad_group_name": "ad_group",
    "ad_group": "ad_group",
    "cost": "spend",
    "amount_spent": "spend",
    "spend": "spend",
    "impr": "impressions",
    "impressions": "impressions",
    "clicks": "clicks",
    "conv": "conversions",
    "conversions": "conversions",
    "all_conversions": "conversions",
    "conversion_action": "conversion_action",
    "conversion_action_name": "conversion_action",
    "conversion_type": "conversion_type",
    "conversion_category": "conversion_type",
    "quality_conversions": "quality_conversions",
    "quality_conversions_count": "quality_conversions",
    "career_clicks": "career_clicks",
    "applications": "applications",
    "enrollment_apply_now_clicks": "enrollment_apply_now_clicks",
    "enrollment_forms": "enrollment_forms",
    "search_term": "search_term",
    "search_terms": "search_term",
    "final_url": "final_url",
    "landing_page": "final_url",
    "landing_page_url": "final_url",
    "date": "date",
    "day": "date",
    "week": "week",
    "month": "month",
    "device": "device",
    "network": "network",
    "objective": "objective",
    "match_type": "match_type",
    "search_term_category": "search_term_category",
    "page_group": "page_group",
}


REQUIRED_COLUMNS = {
    "campaign_performance": {"campaign", "spend", "impressions", "clicks", "conversions"},
    "objective_performance": {"spend", "impressions", "clicks", "conversions"},
    "search_terms": {"search_term", "campaign", "spend", "impressions", "clicks", "conversions"},
    "landing_pages": {"final_url", "campaign", "spend", "impressions", "clicks", "conversions"},
}


OPTIONAL_COLUMNS = {
    "campaign_performance": {"date", "ad_group", "objective", "network", "device", "conversion_action", "final_url"},
    "objective_performance": {"date", "month", "objective", "campaign"},
    "search_terms": {"date", "ad_group", "objective", "match_type", "search_term_category"},
    "landing_pages": {"date", "objective", "page_group"},
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
    for col in ["spend", "impressions", "clicks", "conversions", "quality_conversions",
                "career_clicks", "applications", "enrollment_apply_now_clicks", "enrollment_forms"]:
        if col in out.columns:
            out[col] = (
                out[col].astype(str)
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
            )
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
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

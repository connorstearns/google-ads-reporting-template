SPREADSHEET_ID = "18RXavpYmmXc2zSVz1xxCXbGub-VvBU-NzHjv_FB6d6o"
SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"

EXPECTED_MODEL_TABS = {
    "campaign_performance": "model_campaign_daily",
    "objective_performance": "report_monthly_objective",
    "search_terms": "model_search_terms",
    "landing_pages": "model_landing_pages",
    "conversion_quality": "model_conversion_quality",
    "review_queue": "report_review_queue",
    "campaign_mapping": "map_campaigns",
    "landing_page_mapping": "map_landing_pages",
    "search_term_mapping": "map_search_terms",
    "conversion_action_mapping": "map_conversion_actions",
    "budget_targets": "map_budget_targets",
    "mapping_gaps": "qa_mapping_gaps",
    "dashboard_validation": "qa_dashboard_validation",
}

TAB_ALIASES = {
    "campaign_performance": [
        "model_campaign_daily",
        "report_monthly_campaigns",
        "model_campaign_performance",
        "raw_campaign_daily",
    ],
    "objective_performance": [
        "report_monthly_objective",
        "model_campaign_daily",
        "model_objective_performance",
    ],
    "search_terms": [
        "model_search_terms",
        "report_search_terms",
        "raw_search_terms",
    ],
    "landing_pages": [
        "model_landing_pages",
        "report_landing_pages",
        "raw_landing_pages",
    ],
    "conversion_quality": [
        "model_conversion_quality",
        "report_monthly_conversions",
        "raw_conversion_actions",
    ],
    "review_queue": [
        "report_review_queue",
        "model_review_queue",
    ],
    "campaign_mapping": [
        "map_campaigns",
        "campaign_mapping",
    ],
    "landing_page_mapping": [
        "map_landing_pages",
        "landing_page_mapping",
    ],
    "search_term_mapping": [
        "map_search_terms",
        "search_term_mapping",
    ],
    "conversion_action_mapping": [
        "map_conversion_actions",
        "conversion_action_mapping",
    ],
    "budget_targets": ["map_budget_targets"],
    "mapping_gaps": ["qa_mapping_gaps"],
    "dashboard_validation": ["qa_dashboard_validation"],
}

TAB_CANDIDATES = TAB_ALIASES

OBJECTIVE_COLORS = {
    "Enrollment": "#2563eb",
    "Recruitment": "#16a34a",
    "Other / Unmapped": "#64748b",
    "Other": "#64748b",
}

DEFAULT_THRESHOLDS = {
    "min_spend": 250.0,
    "cpa": 250.0,
    "ctr": 0.01,
    "cpc": 8.0,
    "min_clicks": 20,
}

QUALITY_CONVERSION_TYPES = {
    "Enrollment Lead",
    "Enrollment Intent",
    "Recruitment Lead",
    "Recruitment Intent",
}

SPREADSHEET_ID = "18RXavpYmmXc2zSVz1xxCXbGub-VvBU-NzHjv_FB6d6o"
SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"

EXPECTED_MODEL_TABS = {
    "campaign": "model_campaign_performance",
    "objective": "model_objective_performance",
    "search": "model_search_terms",
    "landing": "model_landing_pages",
    "conversion": "model_conversion_quality",
    "review": "model_review_queue",
    "campaign_mapping": "campaign_mapping",
    "landing_mapping": "landing_page_mapping",
    "search_mapping": "search_term_mapping",
    "conversion_mapping": "conversion_action_mapping",
}

TAB_ALIASES = {
    "campaign": ["model_campaign_performance", "campaign_performance", "campaigns"],
    "objective": ["model_objective_performance", "objective_performance"],
    "search": ["model_search_terms", "search_terms", "search_term_performance"],
    "landing": ["model_landing_pages", "landing_pages", "final_url_performance"],
    "conversion": ["model_conversion_quality", "conversion_quality", "conversions"],
    "review": ["model_review_queue", "review_queue"],
    "campaign_mapping": ["campaign_mapping"],
    "landing_mapping": ["landing_page_mapping"],
    "search_mapping": ["search_term_mapping"],
    "conversion_mapping": ["conversion_action_mapping"],
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

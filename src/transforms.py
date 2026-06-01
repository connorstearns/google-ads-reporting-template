import re
import pandas as pd
from .conversion_logic import classify_conversion_rows
from .metrics import add_core_metrics


def normalize_objective(value):
    text = str(value or "").strip().lower()
    if "enroll" in text:
        return "Enrollment"
    if "recruit" in text or "career" in text or "job" in text:
        return "Recruitment"
    return "Other / Unmapped"


def infer_objective_from_text(*values):
    text = " ".join(str(v or "").lower() for v in values)
    if re.search(r"career|job|teacher|recruit|application", text):
        return "Recruitment"
    if re.search(r"enroll|apply now|scholar|lottery|kindergarten|k-8|promise academy", text):
        return "Enrollment"
    return "Other / Unmapped"


def prepare_performance(df):
    if df.empty:
        return add_core_metrics(df)
    out = df.copy()
    if "objective" in out.columns:
        out["objective"] = out["objective"].apply(normalize_objective)
    else:
        out["objective"] = out.apply(lambda r: infer_objective_from_text(r.get("campaign"), r.get("final_url")), axis=1)
        out["objective_mapping_status"] = "Inferred"
    return add_core_metrics(out)


def apply_conversion_mapping(df, mapping, conversion_quality=None):
    return classify_conversion_rows(df, mapping, conversion_quality)


def infer_conversion_type(value):
    text = str(value or "").lower()
    if re.search(r"application|apply|form|lead", text) and re.search(r"career|job|teacher|recruit", text):
        return "Recruitment Lead"
    if re.search(r"career|job|teacher|recruit", text):
        return "Recruitment Intent"
    if re.search(r"form|lead|lottery", text) and re.search(r"enroll|scholar|kindergarten|k-8", text):
        return "Enrollment Lead"
    if re.search(r"enroll|apply now|scholar|lottery|kindergarten|k-8", text):
        return "Enrollment Intent"
    if re.search(r"click|page|view|engagement", text):
        return "Soft Engagement"
    return "Other / Unmapped"


def combine_primary_data(data):
    campaign_df = data.get("campaign_performance", data.get("campaign", pd.DataFrame()))
    conversion_mapping = data.get("conversion_action_mapping", data.get("conversion_mapping", pd.DataFrame()))
    conversion_quality = data.get("conversion_quality", pd.DataFrame())
    objective_df = data.get("objective_performance", data.get("objective", pd.DataFrame()))
    campaign = prepare_performance(apply_conversion_mapping(campaign_df, conversion_mapping, conversion_quality))
    if campaign.empty and not objective_df.empty:
        campaign = prepare_performance(objective_df)
    search = prepare_performance(apply_conversion_mapping(data.get("search_terms", data.get("search", pd.DataFrame())), conversion_mapping, conversion_quality))
    landing = prepare_performance(apply_conversion_mapping(data.get("landing_pages", data.get("landing", pd.DataFrame())), conversion_mapping, conversion_quality))
    return campaign, search, landing

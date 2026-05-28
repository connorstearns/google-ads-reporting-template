import re
import pandas as pd
from .config import QUALITY_CONVERSION_TYPES
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


def apply_conversion_mapping(df, mapping):
    out = df.copy()
    if out.empty:
        return out
    has_conversion_detail = "conversion_action" in out.columns or "conversion_type" in out.columns
    if not has_conversion_detail:
        return out
    if "conversion_type" not in out.columns:
        out["conversion_type"] = "Other / Unmapped"
    out["conversion_mapping_status"] = "Inferred"
    if not mapping.empty and {"conversion_action", "conversion_type"}.issubset(mapping.columns) and "conversion_action" in out.columns:
        map_df = mapping[["conversion_action", "conversion_type"]].drop_duplicates()
        out = out.drop(columns=["conversion_type"], errors="ignore").merge(map_df, on="conversion_action", how="left")
        out["conversion_type"] = out["conversion_type"].fillna("Other / Unmapped")
        out["conversion_mapping_status"] = out["conversion_type"].where(out["conversion_type"].eq("Other / Unmapped"), "Mapped")
    elif "conversion_action" in out.columns:
        out["conversion_type"] = out["conversion_action"].apply(infer_conversion_type)
    out["quality_conversions"] = out["conversions"].where(out["conversion_type"].isin(QUALITY_CONVERSION_TYPES), 0)
    return out


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
    campaign = prepare_performance(apply_conversion_mapping(data.get("campaign", pd.DataFrame()), data.get("conversion_mapping", pd.DataFrame())))
    if campaign.empty and not data.get("objective", pd.DataFrame()).empty:
        campaign = prepare_performance(data["objective"])
    search = prepare_performance(data.get("search", pd.DataFrame()))
    landing = prepare_performance(data.get("landing", pd.DataFrame()))
    return campaign, search, landing

from urllib.parse import urlparse
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from .config import SPREADSHEET_ID, TAB_CANDIDATES
from .data_validation import normalize_columns, coerce_types, validate_dataframe


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_spreadsheet_id():
    return st.secrets.get("SPREADSHEET_ID", SPREADSHEET_ID)


def get_client():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Missing Streamlit secret [gcp_service_account].")
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds)


def choose_tab(available_tabs, candidates):
    lower = {t.lower(): t for t in available_tabs}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


@st.cache_data(ttl=1800, show_spinner=False)
def load_workbook(spreadsheet_id=None):
    spreadsheet_id = spreadsheet_id or get_spreadsheet_id()
    client = get_client()
    sheet = client.open_by_key(spreadsheet_id)
    available = [ws.title for ws in sheet.worksheets()]
    data = {}
    validation = []

    for key, candidates in TAB_CANDIDATES.items():
        tab_name = choose_tab(available, candidates)
        if not tab_name:
            data[key] = pd.DataFrame()
            validation.append(validate_dataframe(key, candidates[0], pd.DataFrame()))
            continue
        records = sheet.worksheet(tab_name).get_all_records()
        df = coerce_types(normalize_columns(pd.DataFrame(records)))
        data[key] = df
        validation.append(validate_dataframe(key, tab_name, df))

    return data, validation, available


def clear_data_cache():
    load_workbook.clear()

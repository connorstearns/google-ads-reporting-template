import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import APIError, GSpreadException, SpreadsheetNotFound
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError

from .config import EXPECTED_MODEL_TABS, SPREADSHEET_ID, TAB_ALIASES
from .data_validation import ValidationResult, normalize_columns, coerce_types, validate_dataframe


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
CACHE_TTL_SECONDS = 1800


class GoogleSheetsConfigurationError(RuntimeError):
    """Raised when local Streamlit secrets are missing or malformed."""


class GoogleSheetsAccessError(RuntimeError):
    """Raised when the service account cannot access the configured workbook."""


def get_spreadsheet_id():
    return st.secrets.get("SPREADSHEET_ID", SPREADSHEET_ID)


def get_client():
    if "gcp_service_account" not in st.secrets:
        raise GoogleSheetsConfigurationError(
            "Missing Streamlit secret [gcp_service_account]. Copy .streamlit/secrets.toml.example "
            "to .streamlit/secrets.toml and paste the service account JSON fields."
        )
    try:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
        return gspread.authorize(creds)
    except (GoogleAuthError, KeyError, ValueError, TypeError) as exc:
        raise GoogleSheetsConfigurationError(
            "The [gcp_service_account] secret is present but could not be used. "
            "Check private_key formatting and required service account fields."
        ) from exc


def choose_tab(available_tabs, candidates):
    lower = {str(t).lower(): t for t in available_tabs}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _worksheet_to_dataframe(worksheet):
    records = worksheet.get_all_records()
    return coerce_types(normalize_columns(pd.DataFrame(records)))


def _missing_tab_result(tab_key):
    expected = EXPECTED_MODEL_TABS.get(tab_key, tab_key)
    return ValidationResult(tab_key, expected, "red", [], [], f"{tab_key} missing; no configured preferred or alias tab was found.")


def _failed_tab_result(tab_key, tab_name, exc):
    return ValidationResult(tab_key, tab_name, "red", [], [], f"{tab_key} matched {tab_name} but that tab failed to load: {exc}")


def _open_sheet(client, spreadsheet_id):
    try:
        return client.open_by_key(spreadsheet_id)
    except SpreadsheetNotFound as exc:
        raise GoogleSheetsAccessError(
            "The Google Sheet could not be opened. Confirm the spreadsheet ID is correct and "
            "share the workbook with the service account client_email as a Viewer."
        ) from exc
    except APIError as exc:
        raise GoogleSheetsAccessError(
            "Google Sheets API returned an access error. Confirm the Sheets API and Drive API "
            "are enabled and the service account has access to the workbook."
        ) from exc


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_workbook(spreadsheet_id=None):
    spreadsheet_id = spreadsheet_id or get_spreadsheet_id()
    client = get_client()
    sheet = _open_sheet(client, spreadsheet_id)

    try:
        worksheets = sheet.worksheets()
    except APIError as exc:
        raise GoogleSheetsAccessError(
            "Could not list worksheets. Confirm the service account has Viewer access to the workbook."
        ) from exc

    available = [ws.title for ws in worksheets]
    all_tabs = {}
    tab_errors = {}
    data = {}
    validation = []

    for worksheet in worksheets:
        try:
            all_tabs[worksheet.title] = _worksheet_to_dataframe(worksheet)
        except (APIError, GSpreadException, ValueError) as exc:
            all_tabs[worksheet.title] = pd.DataFrame()
            tab_errors[worksheet.title] = str(exc)

    tab_aliases = {}
    for key, candidates in TAB_ALIASES.items():
        tab_name = choose_tab(available, candidates)
        if not tab_name:
            data[key] = pd.DataFrame()
            validation.append(_missing_tab_result(key))
            continue
        tab_aliases[key] = tab_name
        if tab_name in tab_errors:
            data[key] = pd.DataFrame()
            validation.append(_failed_tab_result(key, tab_name, tab_errors[tab_name]))
            continue
        df = all_tabs.get(tab_name, pd.DataFrame())
        data[key] = df
        validation.append(validate_dataframe(key, tab_name, df))

    data["_all_tabs"] = all_tabs
    metadata = {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_title": getattr(sheet, "title", ""),
        "available_tabs": available,
        "expected_model_tabs": EXPECTED_MODEL_TABS,
        "tab_aliases": tab_aliases,
        "tab_errors": tab_errors,
        "loaded_tab_count": sum(1 for df in all_tabs.values() if not df.empty),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }
    return data, validation, metadata


def clear_data_cache():
    load_workbook.clear()

# HCZ Google Ads Dashboard

Production-oriented Streamlit dashboard for Harlem Children's Zone Google Ads reporting. The app reads cleaned/model-ready tabs from a Google Sheet and turns them into executive reporting, campaign diagnostics, search term analysis, landing page analysis, and a prioritized review queue.

## Setup

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
4. Fill in the Google Cloud service account fields.
5. Share the Google Sheet with the service account email as a Viewer.
6. Run the app:

```bash
streamlit run app.py
```

## Create Google Cloud Credentials

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project or select the project that will own this reporting integration.
3. Go to **APIs & Services > Library**.
4. Enable **Google Sheets API**.
5. Enable **Google Drive API**. Drive API access is used by `gspread` to open and inspect the workbook by ID.
6. Go to **APIs & Services > Credentials**.
7. Choose **Create Credentials > Service Account**.
8. Give the account a clear name, such as `hcz-google-ads-dashboard-reader`.
9. Open the service account, go to the **Keys** tab, and create a JSON key.
10. Download the JSON file and copy its fields into `.streamlit/secrets.toml`.

## Google Sheets Configuration

The default spreadsheet ID is configured in `src/config.py`:

```text
18RXavpYmmXc2zSVz1xxCXbGub-VvBU-NzHjv_FB6d6o
```

You can override it in `.streamlit/secrets.toml` with:

```toml
SPREADSHEET_ID = "your-spreadsheet-id"
```

Share the Google Sheet with the service account email shown in the JSON key:

```text
client_email = "your-service-account@your-project-id.iam.gserviceaccount.com"
```

Grant Viewer access unless the app is later extended to write back to the sheet.

## Expected Logical Datasets

The app resolves logical datasets to the first available preferred or alias tab. It prefers `model_` and `report_` tabs before raw fallbacks.

- `campaign_performance`: `model_campaign_daily`, `report_monthly_campaigns`, `model_campaign_performance`, `raw_campaign_daily`
- `objective_performance`: `report_monthly_objective`, `model_campaign_daily`, `model_objective_performance`
- `search_terms`: `model_search_terms`, `report_search_terms`, `raw_search_terms`
- `landing_pages`: `model_landing_pages`, `report_landing_pages`, `raw_landing_pages`
- `conversion_quality`: `model_conversion_quality`, `report_monthly_conversions`, `raw_conversion_actions`
- `review_queue`: `report_review_queue`, `model_review_queue`
- `campaign_mapping`: `map_campaigns`, `campaign_mapping`
- `landing_page_mapping`: `map_landing_pages`, `landing_page_mapping`
- `search_term_mapping`: `map_search_terms`, `search_term_mapping`
- `conversion_action_mapping`: `map_conversion_actions`, `conversion_action_mapping`
- `budget_targets`: `map_budget_targets`
- `mapping_gaps`: `qa_mapping_gaps`
- `dashboard_validation`: `qa_dashboard_validation`

Raw Supermetrics tabs are not required. Add cleaned model tabs whenever possible so page logic remains stable.

## Minimum Columns

Campaign performance:

- `date`
- `campaign`
- `ad_group` optional
- `objective` recommended
- `spend`
- `impressions`
- `clicks`
- `conversions`
- `conversion_action` optional
- `network` optional
- `device` optional
- `final_url` optional

Search terms:

- `date`
- `campaign`
- `ad_group`
- `search_term`
- `match_type` optional
- `spend`
- `impressions`
- `clicks`
- `conversions`
- `objective` optional
- `search_term_category` optional

Landing pages:

- `date`
- `campaign`
- `final_url`
- `spend`
- `impressions`
- `clicks`
- `conversions`
- `objective` optional
- `page_group` optional

## Credential Format

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste the service account fields:

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

No private credentials should be committed.

If the app shows an access error, check four things:

- The spreadsheet ID is correct.
- Google Sheets API is enabled.
- Google Drive API is enabled.
- The workbook is shared with the service account `client_email`.

## Running Locally

From the project directory:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads data only through `src/google_sheets.py::load_workbook()`. That function authenticates with Streamlit secrets, opens the workbook by ID, loads every worksheet into pandas, maps expected model tabs to stable app keys, and returns workbook metadata plus validation results.

## Analytics Logic

The dashboard emphasizes quality outcomes over raw conversion volume. If `conversion_action_mapping` is available, conversion actions are classified into enrollment lead, enrollment intent, recruitment lead, recruitment intent, soft engagement, and unmapped categories. If no mapping exists, the app uses cautious keyword inference and exposes inferred mapping status where possible.

The review queue uses configurable thresholds for spend, CPA, CTR, CPC, and minimum clicks. It prioritizes actionable issues such as high spend with no conversions, no quality conversions, unmapped entities, inefficient CPA, and low CTR.

## Adding New Model Tabs

1. Add the tab name to `TAB_ALIASES` and `EXPECTED_MODEL_TABS` in `src/config.py`.
2. Add or update required and optional columns in `src/data_validation.py`.
3. Normalize any new column aliases in `COLUMN_ALIASES`.
4. Add page-specific logic in `src/transforms.py`, `src/metrics.py`, or the relevant page.

## Known Limitations

- The app can only read sheets the service account can access.
- Inferred objectives and conversion types are useful as a fallback, but mapping tabs should be maintained for production reporting.
- Streamlit cannot truly freeze dataframe columns; identity columns are ordered first to keep tables readable.

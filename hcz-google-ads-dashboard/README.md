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

## Google Sheets Configuration

The default spreadsheet ID is configured in `src/config.py`:

```text
18RXavpYmmXc2zSVz1xxCXbGub-VvBU-NzHjv_FB6d6o
```

You can override it in `.streamlit/secrets.toml` with:

```toml
SPREADSHEET_ID = "your-spreadsheet-id"
```

## Expected Model Tabs

The app prefers model tabs and gracefully skips tabs that are not present:

- `model_campaign_performance`
- `model_objective_performance`
- `model_search_terms`
- `model_landing_pages`
- `model_conversion_quality`
- `model_review_queue`
- `campaign_mapping`
- `landing_page_mapping`
- `search_term_mapping`
- `conversion_action_mapping`

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

Use Streamlit secrets with a service account:

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

## Analytics Logic

The dashboard emphasizes quality outcomes over raw conversion volume. If `conversion_action_mapping` is available, conversion actions are classified into enrollment lead, enrollment intent, recruitment lead, recruitment intent, soft engagement, and unmapped categories. If no mapping exists, the app uses cautious keyword inference and exposes inferred mapping status where possible.

The review queue uses configurable thresholds for spend, CPA, CTR, CPC, and minimum clicks. It prioritizes actionable issues such as high spend with no conversions, no quality conversions, unmapped entities, inefficient CPA, and low CTR.

## Adding New Model Tabs

1. Add the tab name to `TAB_CANDIDATES` in `src/config.py`.
2. Add or update required and optional columns in `src/data_validation.py`.
3. Normalize any new column aliases in `COLUMN_ALIASES`.
4. Add page-specific logic in `src/transforms.py`, `src/metrics.py`, or the relevant page.

## Known Limitations

- The app can only read sheets the service account can access.
- Inferred objectives and conversion types are useful as a fallback, but mapping tabs should be maintained for production reporting.
- Streamlit cannot truly freeze dataframe columns; identity columns are ordered first to keep tables readable.

import pandas as pd


UNAVAILABLE_MESSAGE = "Benchmarking is unavailable because benchmark model tabs are missing or empty."
RECRUITMENT_CAVEAT = "Recruitment YoY tracking caveat"
NO_YOY_BENCHMARK = "No YoY benchmark"
SUPPRESSED_YOY_STATUSES = {
    RECRUITMENT_CAVEAT,
    NO_YOY_BENCHMARK,
    "No priority-conversion benchmark",
    "No prior CPA benchmark",
}

BENCHMARK_TABLE_COLUMNS = [
    "month", "campaign_type", "objective", "spend", "clicks", "priority_conversions",
    "priority_cpa", "trailing_3mo_median_priority_cpa", "priority_cpa_vs_3mo_median",
    "prior_year_priority_conversions", "prior_year_priority_cpa",
    "priority_conversions_yoy_pct", "priority_cpa_yoy_pct", "benchmark_status",
    "yoy_benchmark_status", "benchmark_note", "yoy_benchmark_note",
]

ACTION_QUEUE_COLUMNS = [
    "month", "campaign_type", "objective", "benchmark_type", "status", "metric",
    "current_value", "benchmark_value", "variance_pct", "diagnosis", "recommended_action",
]


def get_campaign_type_benchmarks(data):
    benchmarks = data.get("campaign_type_benchmarks", pd.DataFrame()).copy()
    required = {"month", "campaign_type", "objective"}
    if benchmarks.empty or not required.issubset(benchmarks.columns):
        return pd.DataFrame()
    if "month" in benchmarks.columns:
        benchmarks["month"] = pd.to_datetime(benchmarks["month"], errors="coerce")
    return benchmarks.dropna(subset=["month"])


def latest_benchmarks(benchmarks):
    if benchmarks.empty or "month" not in benchmarks.columns:
        return pd.DataFrame()
    return benchmarks[benchmarks["month"].eq(benchmarks["month"].max())].copy()


def get_latest_complete_benchmark_month(benchmarks, today=None):
    if benchmarks.empty or "month" not in benchmarks.columns:
        return None
    months = pd.to_datetime(benchmarks["month"], errors="coerce").dropna()
    if months.empty:
        return None
    current_month = pd.Timestamp(today or "today").to_period("M").start_time
    complete_months = months[months < current_month]
    return complete_months.max() if not complete_months.empty else None


def get_default_benchmark_month(benchmarks, today=None):
    complete_month = get_latest_complete_benchmark_month(benchmarks, today=today)
    if complete_month is not None:
        return complete_month
    if benchmarks.empty or "month" not in benchmarks.columns:
        return None
    latest_month = pd.to_datetime(benchmarks["month"], errors="coerce").max()
    return None if pd.isna(latest_month) else latest_month


def latest_complete_benchmarks(benchmarks, today=None):
    if benchmarks.empty or "month" not in benchmarks.columns:
        return pd.DataFrame(), None, False
    selected_month = get_latest_complete_benchmark_month(benchmarks, today=today)
    used_fallback = selected_month is None
    if used_fallback:
        selected_month = pd.to_datetime(benchmarks["month"], errors="coerce").max()
    if pd.isna(selected_month):
        return pd.DataFrame(), None, used_fallback
    selected = benchmarks[pd.to_datetime(benchmarks["month"], errors="coerce").eq(selected_month)].copy()
    return add_fallback_yoy_status(selected), selected_month, used_fallback


def add_fallback_yoy_status(benchmarks):
    if benchmarks.empty:
        return benchmarks
    out = benchmarks.copy()
    if "yoy_benchmark_status" not in out.columns:
        out["yoy_benchmark_status"] = ""
    blank_status = out["yoy_benchmark_status"].fillna("").astype(str).str.strip().eq("")
    if blank_status.any():
        out.loc[blank_status, "yoy_benchmark_status"] = out[blank_status].apply(_derive_yoy_status, axis=1)
    return out


def priority_cpa_display(priority_cpa, priority_conversions):
    if pd.isna(priority_conversions) or priority_conversions <= 0:
        return "No priority conversions"
    if pd.isna(priority_cpa):
        return "No priority conversions"
    return f"${priority_cpa:,.0f}"


def yoy_percentage_display(row, metric):
    status = str(row.get("yoy_benchmark_status", "") or "").strip()
    if status in SUPPRESSED_YOY_STATUSES:
        return status or NO_YOY_BENCHMARK
    prior_year_priority_conversions = row.get("prior_year_priority_conversions")
    prior_year_priority_cpa = row.get("prior_year_priority_cpa")
    if (
        prior_year_priority_conversions is None
        or pd.isna(prior_year_priority_conversions)
        or prior_year_priority_conversions <= 0
        or prior_year_priority_cpa is None
        or pd.isna(prior_year_priority_cpa)
        or prior_year_priority_cpa <= 0
    ):
        return NO_YOY_BENCHMARK
    value = row.get(metric)
    if value is None or pd.isna(value):
        return NO_YOY_BENCHMARK
    return f"{value * 100:+,.1f}%"


def comparable_yoy_rows(benchmarks):
    if benchmarks.empty:
        return benchmarks
    statuses = benchmarks.get("yoy_benchmark_status", pd.Series("", index=benchmarks.index)).fillna("")
    return benchmarks[~statuses.isin({NO_YOY_BENCHMARK, RECRUITMENT_CAVEAT})].copy()


def recruitment_caveat_present(benchmarks):
    return (
        not benchmarks.empty
        and "yoy_benchmark_status" in benchmarks.columns
        and benchmarks["yoy_benchmark_status"].fillna("").eq(RECRUITMENT_CAVEAT).any()
    )


def get_benchmark_action_queue(data, benchmarks):
    flags = data.get("benchmark_flags", pd.DataFrame()).copy()
    if not flags.empty:
        return flags
    if benchmarks.empty:
        return pd.DataFrame(columns=ACTION_QUEUE_COLUMNS)
    rows = []
    for _, row in benchmarks.iterrows():
        rows.append(_fallback_action(row, "Trailing 3-month", "priority_cpa", "priority_cpa_vs_3mo_median",
                                     "trailing_3mo_median_priority_cpa", "benchmark_status", "benchmark_note"))
        yoy_status = row.get("yoy_benchmark_status", "")
        if yoy_status not in {NO_YOY_BENCHMARK, RECRUITMENT_CAVEAT}:
            rows.append(_fallback_action(row, "Prior year", "priority_cpa", "priority_cpa_yoy_pct",
                                         "prior_year_priority_cpa", "yoy_benchmark_status", "yoy_benchmark_note"))
    return pd.DataFrame(rows)


def build_campaign_type_context(campaign, benchmarks):
    if campaign.empty or benchmarks.empty or "campaign_type" not in campaign.columns:
        return pd.DataFrame()
    source = campaign.copy()
    if "month" not in source.columns and "date" in source.columns:
        source["month"] = source["date"].dt.to_period("M").dt.start_time
    if "month" not in source.columns:
        return pd.DataFrame()
    source["month"] = pd.to_datetime(source["month"], errors="coerce").dt.to_period("M").dt.start_time
    benchmark_rows = benchmarks.copy()
    benchmark_rows["month"] = benchmark_rows["month"].dt.to_period("M").dt.start_time
    keys = ["month", "campaign_type", "objective"]
    metrics = [
        "benchmark_status", "yoy_benchmark_status", "priority_cpa",
        "prior_year_priority_cpa", "priority_cpa_vs_3mo_median",
        "priority_cpa_yoy_pct", "yoy_benchmark_note",
    ]
    benchmark_rows = benchmark_rows[[c for c in keys + metrics if c in benchmark_rows.columns]].drop_duplicates(keys)
    campaign_rows = source.groupby(keys + ["campaign"], dropna=False, as_index=False).agg(
        spend=("spend", "sum"),
        priority_conversions=("priority_conversions", "sum"),
    )
    context = campaign_rows.merge(benchmark_rows, on=keys, how="left")
    return context.rename(columns={
        "priority_cpa": "campaign_type_priority_cpa_benchmark",
        "priority_cpa_vs_3mo_median": "priority_cpa_vs_3mo_benchmark",
    })


def _fallback_action(row, benchmark_type, metric, variance_col, benchmark_col, status_col, note_col):
    return {
        "month": row.get("month"),
        "campaign_type": row.get("campaign_type", ""),
        "objective": row.get("objective", ""),
        "benchmark_type": benchmark_type,
        "status": row.get(status_col, ""),
        "metric": metric,
        "current_value": row.get(metric, 0),
        "benchmark_value": row.get(benchmark_col, 0),
        "variance_pct": row.get(variance_col, 0),
        "diagnosis": row.get(note_col, ""),
        "recommended_action": "Review campaign-type performance and confirm the next optimization action.",
    }


def _derive_yoy_status(row):
    if "prior_year_priority_conversions" not in row.index:
        return NO_YOY_BENCHMARK
    current = row.get("priority_conversions")
    prior = row.get("prior_year_priority_conversions")
    if current is None or prior is None or pd.isna(current) or pd.isna(prior):
        return NO_YOY_BENCHMARK
    if current == 0 and prior == 0:
        return "No priority-conversion benchmark"
    if current > 0 and prior == 0:
        return "New / no prior-year priority volume"
    if current == 0 and prior > 0:
        return "Underperforming"
    return NO_YOY_BENCHMARK

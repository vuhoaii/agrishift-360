"""Incremental NASA POWER updates, no Airflow required."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from services import climate_pipeline as climate

LOOKBACK_DAYS = 14  # Recheck recently published days for corrections.
LAG_DAYS = 7       # Buffer, not a guaranteed NASA publication delay.
PARAMS = climate.NASA_PARAMS


def master_path():
    return climate.DATA_DIR / "raw" / (
        f"nasa_power_master_{climate.LAT:.6f}_{climate.LON:.6f}_{climate.TIME_STANDARD}.csv"
    )


def normalize(df):
    if not set(PARAMS).issubset(df.columns):
        raise ValueError(f"Missing NASA columns: {set(PARAMS) - set(df.columns)}")
    out = df[list(PARAMS)].copy()
    out.index = pd.to_datetime(out.index).normalize()
    if out.index.has_duplicates:
        raise ValueError("Duplicate dates in NASA data")
    out.index.name = "date"
    for col in PARAMS:
        out[col] = pd.to_numeric(out[col], errors="coerce").replace(
            [-999, np.inf, -np.inf], np.nan
        )
    return out.sort_index().astype(float)


def read_csv(path):
    return normalize(pd.read_csv(path, index_col="date", parse_dates=True))


def fetch_days(start, end):
    response = requests.get(climate.NASA_URL, params={
        "parameters": ",".join(PARAMS), "community": "AG",
        "latitude": climate.LAT, "longitude": climate.LON,
        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
        "format": "JSON", "time-standard": climate.TIME_STANDARD,
    }, timeout=(10, 60))
    response.raise_for_status()
    values = response.json()["properties"]["parameter"]
    frame = pd.DataFrame({col: values[col] for col in PARAMS})
    if frame.empty:
        return normalize(pd.DataFrame(columns=PARAMS, index=pd.DatetimeIndex([], name="date")))
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    frame = normalize(frame)
    if frame.index.min() < pd.Timestamp(start) or frame.index.max() > pd.Timestamp(end):
        raise ValueError("NASA returned dates outside requested range")
    return frame.dropna(how="all")


def fetch_range(start, end):
    chunks = []
    cursor = start
    while cursor <= end:
        finish = min(end, date(cursor.year, 12, 31))
        chunk = fetch_days(cursor, finish)
        if not chunk.empty:
            chunks.append(chunk)
        cursor = finish + timedelta(days=1)
    if not chunks:
        return normalize(pd.DataFrame(columns=PARAMS, index=pd.DatetimeIndex([], name="date")))
    return normalize(pd.concat(chunks))


def write_atomic(path, content, *, is_json=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        if is_json:
            tmp.write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        else:
            content.to_csv(tmp, index=True, index_label="date")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def update(offline=False, start_year=climate.START_YEAR, as_of=None):
    today = as_of or datetime.now(timezone(timedelta(hours=7))).date()
    target = today - timedelta(days=LAG_DAYS)
    if target < date(start_year, 1, 1):
        raise ValueError("start_year is later than the available period")
    master = master_path()
    if master.exists():
        raw = read_csv(master)
    else:
        # Reuse the older 2014-2025 CSV, then backfill 2006-2013 online.
        older = climate.get_cache_path(start_year=2014, end_year=2025)
        raw = read_csv(older) if older.exists() else normalize(
            pd.DataFrame(columns=PARAMS, index=pd.DatetimeIndex([], name="date"))
        )
    initial = raw.copy()
    windows = []
    if offline:
        if raw.empty or raw.index.min().year > start_year:
            raise RuntimeError("Not enough cached data from 2006. Run online first.")
    else:
        if raw.empty:
            windows = [(date(start_year, 1, 1), target)]
        else:
            first, last = raw.index.min().date(), raw.index.max().date()
            if first > date(start_year, 1, 1):
                windows.append((date(start_year, 1, 1), first - timedelta(days=1)))
            recent_start = max(date(start_year, 1, 1), last - timedelta(days=LOOKBACK_DAYS))
            if recent_start <= target:
                windows.append((recent_start, target))
        for start, end in windows:
            new = fetch_range(start, end)
            combined = raw.reindex(raw.index.union(new.index)).sort_index()
            combined.update(new)  # Updated non-null API values win; do not delete old values.
            raw = normalize(combined)
    if raw.empty or raw.index.min().year > start_year:
        raise RuntimeError("Full historical baseline was not downloaded")
    available = raw.loc[raw.index <= pd.Timestamp(target)].dropna(how="all")
    if available.empty:
        raise RuntimeError("NASA has no usable data before cutoff")
    cutoff = available.index.max()
    changed = not raw.equals(initial)
    if not master.exists() or changed:
        write_atomic(master, raw)

    # Analyze the last 20 completed calendar years, plus current partial year.
    last_full_year = cutoff.year if cutoff.strftime("%m-%d") == "12-31" else cutoff.year - 1
    first_year = max(start_year, last_full_year - 19)
    window = available.loc[available.index >= pd.Timestamp(f"{first_year}-01-01")]
    payload = climate.get_climate_payload_for_ui(
        start_year=first_year, end_year=cutoff.year,
        raw_df=window, end_date=cutoff.strftime("%Y-%m-%d"), save_processed=False
    )
    if any(set(payload["scenarios"][k]) != set(climate.SEASONS) for k in payload["scenarios"]):
        raise RuntimeError("Insufficient complete seasons; existing published JSON retained")
    payload["analysis_window"] = {
        "rolling_complete_years": 20,
        "archive_start_year": start_year,
        "analysis_start_year": first_year,
        "observed_through": cutoff.strftime("%Y-%m-%d"),
    }
    target_file = climate.PROCESSED_DIR / "climate_payload_latest.json"
    # Avoid rewriting identical publication on an unchanged daily run.
    if changed or not target_file.exists():
        clean, _ = climate.clean_climate_data(window, first_year, cutoff.year,
                                              cutoff.strftime("%Y-%m-%d"))
        seasons = climate.aggregate_by_season(clean)
        for filename, df, use_index in (
            ("daily_clean_latest.csv", clean, True),
            ("seasonal_stats_latest.csv", seasons, False),
        ):
            path = climate.PROCESSED_DIR / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            try:
                df.to_csv(tmp, index=use_index, index_label="date" if use_index else None)
                os.replace(tmp, path)
            finally:
                tmp.unlink(missing_ok=True)
        write_atomic(target_file, payload, is_json=True)  # Publish JSON last.
    return {
        "status": "updated" if changed else "unchanged",
        "archive_start_year": start_year,
        "stored_days": len(raw),
        "observed_through": cutoff.strftime("%Y-%m-%d"),
        "valid_seasons": payload["data_quality"]["valid_complete_seasons"],
        "output": str(target_file),
        "queries": [[a.isoformat(), b.isoformat()] for a, b in windows],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--start-year", type=int, default=climate.START_YEAR)
    args = parser.parse_args()
    print(json.dumps(update(args.offline, args.start_year), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
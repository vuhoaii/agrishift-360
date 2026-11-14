"""RiceShift - NASA POWER climate data and historical analog scenarios."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests

LAT, LON = 10.35, 105.28   # Pilot coordinates - verify the actual farming area
START_YEAR, END_YEAR = 2006, 2025
NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
TIME_STANDARD = "LST"
NASA_PARAMS = ("T2M_MAX", "T2M_MIN", "T2M", "PRECTOTCORR")
SEASONS = ("Dong_Xuan", "He_Thu", "Thu_Dong")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
TEMP_COLS = ["temp_avg_C", "temp_max_C", "temp_min_C"]
CLIMATE_COLS = TEMP_COLS + ["rain_mm"]


def get_cache_path(lat=LAT, lon=LON, start_year=START_YEAR, end_year=END_YEAR):
    return DATA_DIR / (
        f"nasa_raw_{lat:.6f}_{lon:.6f}_{start_year}_{end_year}_{TIME_STANDARD}.csv"
    )


def fetch_nasa_power_data(lat=LAT, lon=LON, start_year=START_YEAR, end_year=END_YEAR):
    """Fetch full baseline (once); the incremental updater is preferred later."""
    chunks = []
    for year in range(start_year, end_year + 1):
        response = requests.get(NASA_URL, params={
            "parameters": ",".join(NASA_PARAMS), "community": "AG",
            "latitude": lat, "longitude": lon,
            "start": f"{year}0101", "end": f"{year}1231",
            "format": "JSON", "time-standard": TIME_STANDARD,
        }, timeout=(10, 60))
        response.raise_for_status()
        values = response.json()["properties"]["parameter"]
        chunk = pd.DataFrame({col: values[col] for col in NASA_PARAMS})
        chunk.index = pd.to_datetime(chunk.index, format="%Y%m%d")
        chunks.append(chunk)
    df = pd.concat(chunks).sort_index()
    if df.index.has_duplicates:
        raise ValueError("NASA returned duplicate dates")
    df.index.name = "date"
    path = get_cache_path(lat, lon, start_year, end_year)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return df


def _longest_gap(series):
    missing = series.isna()
    if not missing.any():
        return 0
    groups = missing.ne(missing.shift()).cumsum()
    return int(missing.groupby(groups).sum().max())


def _interpolate_short(series, limit=5):
    missing = series.isna()
    groups = missing.ne(missing.shift()).cumsum()
    lengths = missing.groupby(groups).transform("sum")
    estimated = series.interpolate(method="time", limit_area="inside")
    out = series.copy()
    eligible = missing & (lengths <= limit)
    out.loc[eligible] = estimated.loc[eligible]
    return out


def clean_climate_data(raw, start_year=None, end_year=None, end_date=None):
    # Direct tests may pass an older subset; production passes its analysis window.
    if raw.empty:
        raise ValueError("Empty raw climate data")
    start_year = int(start_year if start_year is not None else raw.index.min().year)
    end_year = int(end_year if end_year is not None else raw.index.max().year)
    mapping = {"T2M": "temp_avg_C", "T2M_MAX": "temp_max_C",
               "T2M_MIN": "temp_min_C", "PRECTOTCORR": "rain_mm"}
    if not isinstance(raw.index, pd.DatetimeIndex):
        raise ValueError("Input must have a DatetimeIndex named date")
    if not set(mapping).issubset(raw.columns):
        raise ValueError(f"Missing NASA parameters: {set(mapping) - set(raw.columns)}")
    cutoff = pd.Timestamp(end_date or f"{end_year}-12-31")
    if not (pd.Timestamp(f"{start_year}-01-01") <= cutoff <= pd.Timestamp(f"{end_year}-12-31")):
        raise ValueError("end_date is outside the requested year range")

    df = raw[list(mapping)].rename(columns=mapping).sort_index().copy()
    if df.index.has_duplicates:
        raise ValueError("Duplicate days in raw input")
    for col in CLIMATE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").replace(
            [-999, np.inf, -np.inf], np.nan
        )
    # Conservative screening limits are pilot heuristics, not local station QC.
    bounds = {"temp_avg_C": (12, 45), "temp_max_C": (15, 48),
              "temp_min_C": (10, 38), "rain_mm": (0, 500)}
    for col, (low, high) in bounds.items():
        df[col] = df[col].where(df[col].between(low, high))
    df = df.reindex(pd.date_range(f"{start_year}-01-01", cutoff, freq="D", name="date"))
    missing_before = df[CLIMATE_COLS].isna()
    df["rain_observed"] = df["rain_mm"].notna()
    df["temp_observed"] = df[TEMP_COLS].notna().all(axis=1)
    max_gap = max(_longest_gap(df[col]) for col in TEMP_COLS)
    for col in TEMP_COLS:
        df[col] = _interpolate_short(df[col], limit=5)
    df["temp_available"] = df[TEMP_COLS].notna().all(axis=1)
    df[CLIMATE_COLS] = df[CLIMATE_COLS].round(2)
    df["year"], df["month"] = df.index.year, df.index.month
    quality = {
        "total_days": int(len(df)),
        "missing_cells_before": int(missing_before.sum().sum()),
        "repaired_cells": int((missing_before & df[CLIMATE_COLS].notna()).sum().sum()),
        "missing_cells_remaining": int(df[CLIMATE_COLS].isna().sum().sum()),
        "missing_rain_days": int((~df["rain_observed"]).sum()),
        "missing_original_temp_days": int((~df["temp_observed"]).sum()),
        "max_consecutive_missing_temp_days": max_gap,
        "date_range": f"{df.index.min():%Y-%m-%d} đến {df.index.max():%Y-%m-%d}",
    }
    return df, quality


def map_season_an_giang(month):
    if month in (11, 12, 1, 2, 3):
        return "Dong_Xuan"
    if month in (4, 5, 6, 7):
        return "He_Thu"
    if month in (8, 9, 10):
        return "Thu_Dong"
    raise ValueError(f"Invalid month: {month}")


def expected_season_days(year, season):
    year = int(year)
    if season == "Dong_Xuan":
        a, b = f"{year-1}-11-01", f"{year}-03-31"
    elif season == "He_Thu":
        a, b = f"{year}-04-01", f"{year}-07-31"
    elif season == "Thu_Dong":
        a, b = f"{year}-08-01", f"{year}-10-31"
    else:
        raise ValueError(f"Invalid season: {season}")
    return int((pd.Timestamp(b) - pd.Timestamp(a)).days + 1)


def aggregate_by_season(clean):
    df = clean.copy()
    df["season"] = df["month"].map(map_season_an_giang)
    df["crop_year"] = np.where(df["month"].isin((11, 12)), df["year"] + 1, df["year"])
    stats = df.groupby(["crop_year", "season"], sort=True).agg(
        days_present=("rain_mm", "size"),
        rain_days_observed=("rain_observed", "sum"),
        temp_days_observed=("temp_observed", "sum"),
        temp_days_available=("temp_available", "sum"),
        total_rain_mm=("rain_mm", lambda x: x.sum(min_count=1)),
        avg_temp_C=("temp_avg_C", "mean"),
        max_temp_C=("temp_max_C", "max"),
        hot_days_over_35C=("temp_max_C", lambda x: int((x > 35).sum())),
        dry_days=("rain_mm", lambda x: int((x < 1).sum())),
    ).reset_index()
    stats["expected_days"] = stats.apply(
        lambda r: expected_season_days(r["crop_year"], r["season"]), axis=1
    )
    stats["temp_original_coverage"] = stats["temp_days_observed"] / stats["expected_days"]
    stats["rain_original_coverage"] = stats["rain_days_observed"] / stats["expected_days"]
    stats = stats.loc[
        (stats["days_present"] == stats["expected_days"])
        & (stats["rain_days_observed"] == stats["expected_days"])
        & (stats["temp_original_coverage"] >= 0.98)
        & (stats["temp_days_available"] == stats["expected_days"])
    ].copy()
    for col in ("total_rain_mm", "avg_temp_C", "max_temp_C"):
        stats[col] = stats[col].round(2)
    return stats.reset_index(drop=True)


def build_climate_scenarios(seasonal):
    if seasonal.empty:
        raise ValueError("No complete seasons for climate scenarios")
    out = {"normal": {}, "low_rainfall": {}}
    for season in SEASONS:
        group = seasonal.loc[seasonal["season"] == season]
        if group.empty:
            continue
        for name, pct in (("normal", 0.50), ("low_rainfall", 0.25)):
            p = group["total_rain_mm"].quantile(pct)
            row = group.assign(delta=(group["total_rain_mm"] - p).abs()).sort_values(
                ["delta", "crop_year"]
            ).iloc[0]
            out[name][season] = {
                "total_rain_mm": float(row["total_rain_mm"]),
                "avg_temp_C": float(row["avg_temp_C"]),
                "max_temp_C": float(row["max_temp_C"]),
                "hot_days_over_35C": int(row["hot_days_over_35C"]),
                "dry_days": int(row["dry_days"]),
                "analog_year": int(row["crop_year"]),
                "target_rain_percentile": int(pct * 100),
                "method": "single_historical_analog_nearest_rain_percentile",
            }
    return out


def get_climate_payload_for_ui(lat=LAT, lon=LON, start_year=START_YEAR,
                               end_year=END_YEAR, use_cached_csv=True,
                               save_processed=True, raw_df=None, end_date=None):
    if raw_df is None:
        cache = get_cache_path(lat, lon, start_year, end_year)
        raw_df = (pd.read_csv(cache, index_col="date", parse_dates=True)
                  if use_cached_csv and cache.exists()
                  else fetch_nasa_power_data(lat, lon, start_year, end_year))
    clean, quality = clean_climate_data(raw_df, start_year, end_year, end_date)
    seasons = aggregate_by_season(clean)
    scenarios = build_climate_scenarios(seasons)
    quality["valid_complete_seasons"] = int(len(seasons))
    quality["valid_seasons_by_type"] = {
        s: int((seasons["season"] == s).sum()) for s in SEASONS
    }
    payload = {
        "location": {
            "name": "Khu vực thí điểm An Giang (cần xác nhận địa danh)",
            "lat": float(lat), "lon": float(lon),
            "period": f"{start_year}-{end_year}",
            "observed_through": end_date or f"{end_year}-12-31",
            "data_source": "NASA POWER Daily API (AG Community)",
            "time_standard": TIME_STANDARD,
            "spatial_note": "Dữ liệu dạng lưới, không phải phép đo tại thửa ruộng.",
            "season_calendar_note": "Đông Xuân 11–03, Hè Thu 04–07, Thu Đông 08–10 là giả định thí điểm.",
        },
        "data_quality": quality,
        "scenarios": scenarios,
        "scenario_note": "P50/P25 chọn mùa vụ lịch sử gần phân vị lượng mưa; không phải dự báo hay tính nhu cầu tưới.",
    }
    if save_processed:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        suffix = f"{lat:.6f}_{lon:.6f}_{start_year}_{end_year}_{TIME_STANDARD}"
        clean.to_csv(PROCESSED_DIR / f"daily_clean_{suffix}.csv", index_label="date")
        seasons.to_csv(PROCESSED_DIR / f"seasonal_stats_{suffix}.csv", index=False)
        (PROCESSED_DIR / f"climate_payload_{suffix}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return payload


def load_latest_climate_payload():
    path = PROCESSED_DIR / "climate_payload_latest.json"
    if not path.exists():
        raise FileNotFoundError("Run: python -m services.climate_updater")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps(get_climate_payload_for_ui(), ensure_ascii=False, indent=2))
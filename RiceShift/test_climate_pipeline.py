"""Offline sanity checks for RiceShift/services/climate_pipeline.py.

Put this file in RiceShift/test_climate_pipeline.py and run from the RiceShift root:
    python test_climate_pipeline.py

Does not call NASA API and does not modify cached or processed files.
"""

import numpy as np
import pandas as pd

from services import climate_pipeline as climate


def test_pipeline():
    dates = pd.date_range("2014-01-01", "2025-12-31", freq="D", name="date")
    rain = np.where(np.isin(dates.month, [6, 7, 8, 9, 10]), 5.0, 1.0)
    rain *= np.where(np.isin(dates.year, [2016, 2019, 2022]), 0.4, 1.0)

    raw = pd.DataFrame(
        {
            "T2M": 27.0 + np.cos(np.arange(len(dates)) / 50),
            "T2M_MAX": 35.2 + np.cos(np.arange(len(dates)) / 30),
            "T2M_MIN": 23.5 + np.cos(np.arange(len(dates)) / 60),
            "PRECTOTCORR": rain,
        },
        index=dates,
    )

    # Missing temperature runs: 2 days may be interpolated; 7 days must remain missing.
    raw.loc["2018-02-05":"2018-02-06", "T2M"] = -999.0
    raw.loc["2021-07-05":"2021-07-11", "T2M"] = -999.0

    clean, quality = climate.clean_climate_data(raw)
    assert clean.loc["2018-02-05":"2018-02-06", "temp_avg_C"].notna().all(), \
        "Short temperature gap was not repaired"
    assert clean.loc["2021-07-05":"2021-07-11", "temp_avg_C"].isna().all(), \
        "Long temperature gap should remain missing"
    assert quality["repaired_cells"] == 2, quality
    assert quality["max_consecutive_missing_temp_days"] == 7, quality

    seasons = climate.aggregate_by_season(clean)
    counts = seasons.groupby("season").size().to_dict()
    assert counts.get("Dong_Xuan") == 11, counts
    assert counts.get("He_Thu") == 11, counts
    assert counts.get("Thu_Dong") == 12, counts
    assert climate.expected_season_days(2016, "Dong_Xuan") == 152
    assert climate.expected_season_days(2015, "Dong_Xuan") == 151

    scenarios = climate.build_climate_scenarios(seasons)
    assert set(scenarios) == {"normal", "low_rainfall"}
    for season in climate.SEASONS:
        assert season in scenarios["normal"]
        assert season in scenarios["low_rainfall"]
        assert (scenarios["low_rainfall"][season]["total_rain_mm"]
                <= scenarios["normal"][season]["total_rain_mm"])

    # Missing rain must stay NaN and exclude the affected season.
    raw.loc["2019-05-03", "PRECTOTCORR"] = -999.0
    clean_with_missing_rain, _ = climate.clean_climate_data(raw)
    assert pd.isna(clean_with_missing_rain.loc["2019-05-03", "rain_mm"])
    reduced_seasons = climate.aggregate_by_season(clean_with_missing_rain)
    reduced_counts = reduced_seasons.groupby("season").size().to_dict()
    assert reduced_counts.get("He_Thu") == 10, reduced_counts

    print("Số mùa vụ hợp lệ trong dữ liệu giả lập:", counts)
    print("Kịch bản được tạo cho:", list(scenarios["normal"].keys()))
    print("PASS - Tất cả kiểm thử dữ liệu giả lập thành công.")


if __name__ == "__main__":
    test_pipeline()

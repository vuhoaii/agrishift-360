"""Offline provenance and consistency checks for the active historical dataset."""
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from services import climate_pipeline as c, climate_updater as u, scoring_engine as engine


METRICS = ("total_rain_mm", "avg_temp_C", "max_temp_C", "hot_days_over_35C", "dry_days")
EXPECTED_ANALOGS = {
    ("normal", "Dong_Xuan"): (2025, 218.73, 27.60, 39.66, 48, 113),
    ("normal", "He_Thu"): (2006, 594.07, 28.34, 40.35, 25, 35),
    ("normal", "Thu_Dong"): (2011, 581.63, 26.69, 31.98, 0, 22),
    ("low_rainfall", "Dong_Xuan"): (2008, 162.66, 27.58, 38.70, 54, 119),
    ("low_rainfall", "He_Thu"): (2013, 487.83, 28.56, 39.42, 21, 52),
    ("low_rainfall", "Thu_Dong"): (2010, 505.49, 26.99, 32.53, 0, 23),
}


class HistoricalDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = u.read_csv(u.master_path())
        cls.clean, cls.quality = c.clean_climate_data(cls.raw, 2006, 2025)
        cls.seasons = c.aggregate_by_season(cls.clean)
        cls.payload = c.load_latest_climate_payload()

    def test_original_daily_observations_and_coverage(self):
        self.assertEqual(len(self.clean), 7305)
        self.assertTrue(self.clean.index.equals(pd.date_range(
            "2006-01-01", "2025-12-31", name="date")))
        self.assertFalse(self.clean.index.has_duplicates)
        for key in ("missing_cells_before", "repaired_cells", "missing_cells_remaining"):
            self.assertEqual(self.quality[key], 0)
        original = self.raw.loc[self.clean.index, ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR"]].copy()
        original.columns = c.CLIMATE_COLS
        assert_frame_equal(self.clean[c.CLIMATE_COLS], original, check_freq=False)
        older = u.read_csv(c.get_cache_path(start_year=2014, end_year=2025))
        assert_frame_equal(self.raw.loc[older.index], older, check_freq=False)

    def test_exact_eligible_seasons_and_cross_year_boundaries(self):
        self.assertEqual(len(self.seasons), 59)
        for season in c.SEASONS:
            years = set(self.seasons.loc[self.seasons.season == season, "crop_year"])
            self.assertEqual(years, set(range(2007 if season == "Dong_Xuan" else 2006, 2026)))
        for row in self.seasons.itertuples():
            if row.season == "Dong_Xuan":
                start, end = f"{row.crop_year - 1}-11-01", f"{row.crop_year}-03-31"
            elif row.season == "He_Thu":
                start, end = f"{row.crop_year}-04-01", f"{row.crop_year}-07-31"
            else:
                start, end = f"{row.crop_year}-08-01", f"{row.crop_year}-10-31"
            days = pd.date_range(start, end, name="date")
            self.assertTrue(days.isin(self.clean.index).all())
            self.assertEqual(row.days_present, len(days))
            self.assertEqual(row.rain_days_observed, len(days))
            self.assertEqual(row.temp_days_observed, len(days))
            self.assertEqual(row.expected_days, len(days))
            self.assertEqual(row.total_rain_mm, round(self.raw.loc[days, "PRECTOTCORR"].sum(), 2))
        self.assertEqual(c.expected_season_days(2007, "Dong_Xuan"), 151)
        self.assertEqual(c.expected_season_days(2008, "Dong_Xuan"), 152)

    def test_all_analogs_match_independent_original_seasons(self):
        for (scenario, season), expected in EXPECTED_ANALOGS.items():
            with self.subTest(scenario=scenario, season=season):
                analog = self.payload["scenarios"][scenario][season]
                self.assertEqual(tuple([analog["analog_year"]] + [analog[k] for k in METRICS]), expected)
                row = self.seasons.loc[(self.seasons.season == season)
                    & (self.seasons.crop_year == analog["analog_year"])].iloc[0]
                self.assertEqual(tuple(row[k] for k in METRICS), expected[1:])
                year = analog["analog_year"]
                if season == "Dong_Xuan":
                    start, end = f"{year - 1}-11-01", f"{year}-03-31"
                elif season == "He_Thu":
                    start, end = f"{year}-04-01", f"{year}-07-31"
                else:
                    start, end = f"{year}-08-01", f"{year}-10-31"
                original = self.raw.loc[start:end]
                values = (round(original.PRECTOTCORR.sum(), 2), round(original.T2M.mean(), 2),
                          original.T2M_MAX.max(), int((original.T2M_MAX > 35).sum()),
                          int((original.PRECTOTCORR < 1).sum()))
                self.assertEqual(values, expected[1:])
                group = self.seasons.loc[self.seasons.season == season]
                target = group.total_rain_mm.quantile(0.5 if scenario == "normal" else 0.25)
                self.assertAlmostEqual(abs(analog["total_rain_mm"] - target),
                                       (group.total_rain_mm - target).abs().min())

    def test_published_artifacts_and_metadata_are_consistent(self):
        daily = pd.read_csv(c.PROCESSED_DIR / "daily_clean_latest.csv", index_col="date", parse_dates=True)
        seasonal = pd.read_csv(c.PROCESSED_DIR / "seasonal_stats_latest.csv")
        assert_frame_equal(daily, self.clean, check_freq=False, check_dtype=False)
        assert_frame_equal(seasonal, self.seasons, check_dtype=False)
        regenerated = c.get_climate_payload_for_ui(raw_df=self.raw, save_processed=False)
        for key, value in regenerated.items():
            self.assertEqual(self.payload[key], value)
        window = self.payload["analysis_window"]
        self.assertEqual(window["mode"], "fixed_historical_period")
        self.assertEqual(window["calendar_years"], 20)
        self.assertEqual(window["analysis_start_date"], "2006-01-01")
        self.assertEqual(window["analysis_end_date"], "2025-12-31")
        self.assertEqual(window["observed_through"], "2025-12-31")
        self.assertNotIn("rolling_complete_years", window)
        self.assertEqual(self.payload["data_quality"]["valid_seasons_by_type"],
                         {"Dong_Xuan": 19, "He_Thu": 20, "Thu_Dong": 20})

    def test_out_of_period_observations_cannot_change_scenarios(self):
        outside = pd.date_range("2005-01-01", "2027-12-31", name="date")
        extended = self.raw.reindex(outside)
        mask = (outside < "2006-01-01") | (outside > "2025-12-31")
        extended.loc[mask, :] = [48.0, 10.0, 45.0, 500.0]
        payload = c.get_climate_payload_for_ui(raw_df=extended, save_processed=False)
        self.assertEqual(payload["scenarios"], self.payload["scenarios"])
        self.assertEqual(payload["data_quality"], self.payload["data_quality"])

    def test_decision_engine_reads_the_same_fixed_payload(self):
        self.assertEqual(engine.PAYLOAD_PATH, c.PROCESSED_DIR / "climate_payload_latest.json")
        self.assertEqual(engine.load_payload(), self.payload)
        for (scenario, season), expected in EXPECTED_ANALOGS.items():
            with self.subTest(scenario=scenario, season=season):
                result = engine.evaluate_rotation(season=season, scenario=scenario)
                climate = result["climate"]
                self.assertEqual(climate["observed_through"], "2025-12-31")
                self.assertEqual(climate["analog_year"], expected[0])
                self.assertEqual(climate["rain_mm"], expected[1])
                self.assertEqual(climate["avg_temp_c"], expected[2])
                self.assertEqual(climate["hot_days"], expected[4])
                self.assertEqual(climate["dry_days"], expected[5])


if __name__ == "__main__":
    unittest.main(verbosity=2)

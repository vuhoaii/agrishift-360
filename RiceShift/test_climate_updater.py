"""Offline tests for the climate updater."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from services import climate_pipeline as c, climate_updater as u


class TestUpdater(unittest.TestCase):
    def test_incremental_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d)
            with patch.object(c, "DATA_DIR", data), patch.object(
                c, "PROCESSED_DIR", data / "processed"
            ):
                dates = pd.date_range(
                    "2006-01-01", "2025-12-31", name="date"
                )
                raw = pd.DataFrame({
                    "T2M_MAX": 36.0,
                    "T2M_MIN": 24.0,
                    "T2M": 28.0,
                    "PRECTOTCORR": np.where(
                        dates.month.isin([5, 6, 7, 8, 9, 10]),
                        5.0, 1.0
                    ),
                }, index=dates)

                path = u.master_path()
                path.parent.mkdir(parents=True)
                raw.to_csv(path)

                first = u.update(
                    offline=True,
                    start_year=2006,
                    as_of=date(2026, 1, 15)
                )
                self.assertEqual(first["stored_days"], 7305)
                self.assertEqual(first["valid_seasons"], 59)

                extra = pd.DataFrame({
                    "T2M_MAX": [36.0, 36.0],
                    "T2M_MIN": [24.0, 24.0],
                    "T2M": [28.0, 28.0],
                    "PRECTOTCORR": [0.0, 5.0],
                }, index=pd.date_range(
                    "2026-01-01", "2026-01-02", name="date"
                ))

                with patch.object(
                    u, "fetch_range", return_value=extra
                ):
                    result = u.update(
                        start_year=2006,
                        as_of=date(2026, 1, 15)
                    )
                    self.assertEqual(result["stored_days"], 7307)

                    result2 = u.update(
                        start_year=2006,
                        as_of=date(2026, 1, 15)
                    )
                    self.assertEqual(result2["status"], "unchanged")

                before = path.read_bytes()

                with patch.object(
                    u, "fetch_range",
                    side_effect=RuntimeError("API failed")
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "API failed"
                    ):
                        u.update(
                            start_year=2006,
                            as_of=date(2026, 1, 15)
                        )

                self.assertEqual(before, path.read_bytes())

                payload = c.load_latest_climate_payload()
                self.assertEqual(payload["location"]["period"], "2006-2025")
                self.assertEqual(payload["location"]["observed_through"], "2025-12-31")
                self.assertEqual(payload["data_quality"]["valid_complete_seasons"], 59)
                self.assertIn("normal", payload["scenarios"])
                self.assertIn("low_rainfall", payload["scenarios"])


class TestHistoricalPublication(unittest.TestCase):
    """Synthetic source fixtures; never change bundled NASA observations."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        self.enterContext(patch.object(c, "DATA_DIR", self.data))
        self.enterContext(patch.object(c, "PROCESSED_DIR", self.data / "processed"))
        dates = pd.date_range("2006-01-01", "2025-12-31", name="date")
        self.raw = pd.DataFrame({"T2M_MAX": 36.0, "T2M_MIN": 24.0,
                                 "T2M": 28.0, "PRECTOTCORR": 2.0}, index=dates)
        self.master = u.master_path()
        self.master.parent.mkdir(parents=True)
        self.raw.to_csv(self.master)

    def publish(self, **kwargs):
        return u.update(offline=True, as_of=date(2028, 1, 15), **kwargs)

    def artifacts(self):
        return {path.name: path.read_bytes() for path in c.PROCESSED_DIR.iterdir()}

    def test_stale_or_missing_artifacts_repaired_without_downloads(self):
        archive_before = self.master.read_bytes()
        with patch.object(u, "fetch_range", side_effect=AssertionError("Offline must not fetch")) as fetch:
            self.publish()
            expected = self.artifacts()
            for name in expected:
                for missing in (False, True):
                    with self.subTest(name=name, missing=missing):
                        path = c.PROCESSED_DIR / name
                        if missing:
                            path.unlink()
                        else:
                            path.write_text("{}", encoding="utf-8")
                        self.assertEqual(self.publish()["status"], "updated")
                        self.assertEqual(self.artifacts(), expected)
            fetch.assert_not_called()
        self.assertEqual(self.master.read_bytes(), archive_before)

    def test_identical_run_does_not_rewrite(self):
        self.publish()
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in [self.master, *c.PROCESSED_DIR.iterdir()]}
        self.assertEqual(self.publish()["status"], "unchanged")
        after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before}
        self.assertEqual(before, after)

    def test_future_archive_and_archival_start_do_not_shift_study(self):
        self.publish()
        original = c.load_latest_climate_payload()
        extended = self.raw.reindex(pd.date_range("2005-01-01", "2027-12-31", name="date"))
        extended = extended.fillna({"T2M_MAX": 48.0, "T2M_MIN": 10.0,
                                    "T2M": 45.0, "PRECTOTCORR": 500.0})
        extended.to_csv(self.master)
        archive_before = self.master.read_bytes()
        result = self.publish(start_year=2005)
        payload = c.load_latest_climate_payload()
        self.assertEqual(result["observed_through"], "2025-12-31")
        self.assertEqual(result["archive_observed_through"], "2027-12-31")
        for key in ("location", "scenarios", "data_quality"):
            self.assertEqual(payload[key], original[key])
        self.assertEqual(self.master.read_bytes(), archive_before)

    def test_invalid_original_baseline_retains_publications(self):
        self.publish()
        expected = self.artifacts()
        missing_temp = self.raw.copy()
        missing_temp.loc["2010-02-01", "T2M"] = -999.0
        missing_rain = self.raw.copy()
        missing_rain.loc["2010-05-01", "PRECTOTCORR"] = np.nan
        invalid_temp = self.raw.copy()
        invalid_temp.loc["2010-02-01", "T2M_MAX"] = 99.0
        variants = {
            "missing_day": self.raw.drop(pd.Timestamp("2010-02-01")),
            "missing_last_day": self.raw.iloc[:-1],
            "duplicate_day": pd.concat([self.raw, self.raw.iloc[:1]]),
            "missing_temperature": missing_temp,
            "missing_rain": missing_rain,
            "invalid_temperature": invalid_temp,
        }
        for name, raw in variants.items():
            with self.subTest(name=name):
                raw.to_csv(self.master)
                archive_before = self.master.read_bytes()
                with self.assertRaises((RuntimeError, ValueError)):
                    self.publish()
                self.assertEqual(self.artifacts(), expected)
                self.assertEqual(self.master.read_bytes(), archive_before)

    def test_failed_staging_retains_existing_artifacts(self):
        self.publish()
        (c.PROCESSED_DIR / "climate_payload_latest.json").write_text("{}", encoding="utf-8")
        before = self.artifacts()
        original_write = Path.write_text

        def failing_write(path, *args, **kwargs):
            if path.name == "seasonal_stats_latest.csv.tmp":
                raise OSError("Simulated disk full")
            return original_write(path, *args, **kwargs)

        with patch.object(Path, "write_text", new=failing_write):
            with self.assertRaisesRegex(OSError, "Simulated disk full"):
                self.publish()
        self.assertEqual(self.artifacts(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
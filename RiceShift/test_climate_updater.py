"""Offline tests for the climate updater."""
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
                self.assertIn("normal", payload["scenarios"])
                self.assertIn("low_rainfall", payload["scenarios"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
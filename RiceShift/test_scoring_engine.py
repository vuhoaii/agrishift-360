"""Offline v2 behavior, sensitivity, data-quality and screening tests."""
import itertools
import json
import math
import unittest
from copy import deepcopy
from unittest.mock import patch

from services import scoring_engine as e
from presentation_messages import is_message_translated, translate_message


BASE = dict(season="He_Thu", scenario="low_rainfall", drainage="good",
            irrigation="limited", salinity="no", soil_ph=6.5,
            crop_calendar_confirmed=True)


class DecisionEngineV2Tests(unittest.TestCase):
    def setUp(self):
        self.payload = e.load_payload()

    def evaluate(self, **changes):
        return e.evaluate_rotation(payload=self.payload, **(BASE | changes))

    def selected(self):
        return self.payload["scenarios"]["low_rainfall"]["He_Thu"]

    def test_invalid_payload_file_reports_a_translatable_error(self):
        from unittest.mock import Mock
        path = Mock(is_file=lambda: True, read_text=lambda **kwargs: "{bad json")
        with patch.object(e, "PAYLOAD_PATH", path):
            with self.assertRaises(ValueError) as error:
                e.load_payload()
        self.assertTrue(is_message_translated(str(error.exception)))

    def test_complete_matrix_is_finite_bounded_and_deterministic(self):
        for season, scenario, irrigation, goal in itertools.product(
                e.SEASONS, e.SCENARIOS, ("available", "limited"), e.WEIGHTS):
            with self.subTest(season=season, scenario=scenario, irrigation=irrigation, goal=goal):
                args = dict(season=season, scenario=scenario, irrigation=irrigation, goal=goal)
                result = self.evaluate(**args)
                self.assertEqual(result, self.evaluate(**args))
                self.assertEqual([o["id"] for o in result["options"]], ["rice_rice", "rice_sesame"])
                self.assertEqual(result["engine_version"], "2.0")
                for option in result["options"]:
                    self.assertEqual(option["status"], "review")
                    self.assertTrue(0 <= option["score"] <= 100)
                    self.assertTrue(all(0 <= n <= 2 for n in option["components"].values()))
                json.dumps(result, allow_nan=False)

    def test_actual_corrected_analogs_remain_independent(self):
        results = e.compare_scenarios(payload=self.payload, **BASE)
        normal, low = results["normal"]["climate"], results["low_rainfall"]["climate"]
        self.assertLess(low["rain_mm"], normal["rain_mm"])
        self.assertGreater(low["avg_temp_c"], normal["avg_temp_c"])
        self.assertLess(low["hot_days"], normal["hot_days"])
        self.assertGreater(low["dry_days"], normal["dry_days"])
        self.assertEqual(low["observed_through"], "2025-12-31")
        self.assertEqual(results["normal"]["provenance"]["location"]["period"], "2006-2025")

    def test_rainfall_magnitude_not_just_sign_changes_water(self):
        scores = []
        for rain in (594.07, 590, 500, 300, 0):
            self.selected()["total_rain_mm"] = rain
            scores.append([o["components"]["water"] for o in self.evaluate()["options"]])
        for crop in (0, 1):
            self.assertTrue(all(a[crop] > b[crop] for a, b in zip(scores, scores[1:])))

    def test_rainfall_boundary_is_continuous_before_display_rounding(self):
        ref = self.payload["scenarios"]["normal"]["He_Thu"]["total_rain_mm"]
        values = []
        for factor in (1.000001, 1, 0.999999):
            self.selected()["total_rain_mm"] = ref * factor
            values.append(self.evaluate()["options"][0])
        self.assertEqual(values[0]["components"]["water"], values[1]["components"]["water"])
        self.assertGreater(values[1]["components"]["water"], values[2]["components"]["water"])
        self.assertLess(abs(values[1]["components"]["water"] - values[2]["components"]["water"]), 0.00001)
        self.assertEqual(values[1]["score"], values[2]["score"])
        self.assertEqual(self.evaluate()["climate"]["rain_change_pct"], 0)

    def test_zero_rain_and_all_dry_remain_bounded(self):
        self.selected().update(total_rain_mm=0, dry_days=122)
        result = self.evaluate()
        self.assertEqual(result["options"][0]["components"]["water"], 0)
        self.assertEqual(result["options"][1]["components"]["water"], 0.5)
        self.assertTrue(all(o["status"] == "review" for o in result["options"]))

    def test_excess_rain_does_not_create_unlimited_benefit(self):
        self.selected()["total_rain_mm"] = 1000
        first = self.evaluate()
        self.selected()["total_rain_mm"] = 2000
        second = self.evaluate()
        self.assertEqual([o["score"] for o in first["options"]], [o["score"] for o in second["options"]])

    def test_irrigation_attenuates_without_erasing_climate_sensitivity(self):
        for irrigation in ("available", "limited"):
            wet = self.evaluate(irrigation=irrigation)
            self.selected()["total_rain_mm"] *= 0.8
            dry = self.evaluate(irrigation=irrigation)
            for index in (0, 1):
                self.assertGreater(wet["options"][index]["components"]["water"],
                                   dry["options"][index]["components"]["water"])
        limited = self.evaluate(irrigation="limited")
        available = self.evaluate(irrigation="available")
        for index in (0, 1):
            self.assertGreater(available["options"][index]["components"]["water"],
                               limited["options"][index]["components"]["water"])

    def test_dry_days_influence_score_independently_of_rain_and_heat(self):
        initial = self.evaluate()
        self.selected()["dry_days"] += 20
        changed = self.evaluate()
        for a, b in zip(initial["options"], changed["options"]):
            self.assertGreater(a["score"], b["score"])
        for key in ("rain_mm", "avg_temp_c", "hot_days"):
            self.assertEqual(initial["climate"][key], changed["climate"][key])
        self.assertTrue(any("not a consecutive dry spell" in w for w in changed["options"][0]["warnings"]))

    def test_mean_temperature_changes_context_without_inventing_penalties(self):
        initial = self.evaluate()
        self.selected()["avg_temp_C"] += 2
        changed = self.evaluate()
        for a, b in zip(initial["options"], changed["options"]):
            self.assertEqual(a["score"], b["score"])
            self.assertNotEqual(a["risk_indicators"]["mean_temperature"],
                                b["risk_indicators"]["mean_temperature"])
            self.assertNotEqual(a["warnings"], b["warnings"])
        self.assertEqual(initial["climate"]["hot_days"], changed["climate"]["hot_days"])

    def test_hot_days_independently_trigger_rice_phenology_check(self):
        self.selected()["hot_days_over_35C"] = 0
        zero = self.evaluate()
        self.selected()["hot_days_over_35C"] = 40
        hot = self.evaluate()
        self.assertNotEqual(zero["options"][0]["risk_indicators"]["hot_days"]["effect"],
                            hot["options"][0]["risk_indicators"]["hot_days"]["effect"])
        self.assertEqual(hot["options"][1]["risk_indicators"]["hot_days"]["effect"], "context_only")
        self.assertTrue(any("does not establish sterility" in w for w in hot["options"][0]["warnings"]))
        self.assertTrue(any("not a validated sesame" in w for w in hot["options"][1]["warnings"]))
        self.assertEqual(hot["climate"]["avg_temp_c"], zero["climate"]["avg_temp_c"])
        self.assertEqual([o["score"] for o in hot["options"]], [o["score"] for o in zero["options"]])

    def test_missing_essential_farm_information_prevents_a_leader(self):
        for field, value in (("irrigation", "unknown"), ("salinity", "unknown"),
                             ("salinity", "yes"), ("crop_calendar_confirmed", False)):
            with self.subTest(field=field, value=value):
                result = self.evaluate(**{field: value})
                self.assertIsNone(result["leading_option_id"])
                self.assertEqual(result["ranked_ids"], [])
                self.assertTrue(result["missing_info"])
                self.assertTrue(all(o["score"] is None for o in result["options"]))

    def test_drainage_withholds_sesame_without_claiming_rice_wins(self):
        for drainage in ("poor", "unknown"):
            result = self.evaluate(drainage=drainage)
            rice, sesame = result["options"]
            self.assertIsNotNone(rice["score"])
            self.assertIsNone(sesame["score"])
            self.assertEqual(sesame["status"], "needs_info")
            self.assertIsNone(result["leading_option_id"])
            check = next(c for c in sesame["screening_checks"] if c["rule"] == "drainage")
            self.assertEqual(check["classification"], "local_verification" if drainage == "poor" else "missing_information")

    def test_ph_guidance_is_a_warning_not_a_universal_exclusion(self):
        for ph in (5.49, 5.5, 7, 7.01, None):
            result = self.evaluate(soil_ph=ph)
            self.assertIsNotNone(result["options"][1]["score"])
            warnings = result["options"][1]["warnings"]
            self.assertEqual(any("5.5-7.0" in w for w in warnings), ph is not None and not 5.5 <= ph <= 7)

    def test_invalid_rain_is_rejected_in_selected_or_baseline(self):
        for role, value in itertools.product(("low_rainfall", "normal"),
                (None, -1, math.nan, math.inf, -math.inf, 10**1000, "500", True, [], {})):
            payload = deepcopy(self.payload)
            payload["scenarios"][role]["He_Thu"]["total_rain_mm"] = value
            with self.subTest(role=role, value=value), self.assertRaises(ValueError) as error:
                e.evaluate_rotation(payload=payload, **BASE)
            self.assertTrue(is_message_translated(str(error.exception)))
        self.payload["scenarios"]["normal"]["He_Thu"]["total_rain_mm"] = 0
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_missing_or_invalid_optional_indicators_never_become_zero_risk(self):
        bad = {
            "avg_temp_C": (None, -999, 101, math.nan, math.inf, 10**1000, "28", True),
            "hot_days_over_35C": (None, -1, 123, 1.5, math.nan, "2", True),
            "dry_days": (None, -1, 123, 1.5, math.inf, "2", False),
            "analog_year": (None, 2000, 2026, 2013.5, "2013", True),
        }
        for scenario, (field, values) in itertools.product(e.SCENARIOS, bad.items()):
            for value in values:
                payload = deepcopy(self.payload)
                payload["scenarios"][scenario]["He_Thu"][field] = value
                result = e.evaluate_rotation(payload=payload, **BASE)
                self.assertFalse(result["climate"]["usable"], (scenario, field, value))
                self.assertIsNone(result["leading_option_id"])
                self.assertEqual(result["ranked_ids"], [])
                for option in result["options"]:
                    self.assertIsNone(option["score"])
                for message in result["notes"]:
                    self.assertTrue(is_message_translated(message), message)
                json.dumps(result, allow_nan=False)

    def test_absent_indicators_and_records_are_handled_explicitly(self):
        for field in ("avg_temp_C", "hot_days_over_35C", "dry_days", "analog_year"):
            payload = deepcopy(self.payload)
            del payload["scenarios"]["low_rainfall"]["He_Thu"][field]
            result = e.evaluate_rotation(payload=payload, **BASE)
            self.assertFalse(result["climate"]["usable"])
        for payload in (None, [], {}, {"scenarios": []}, {"scenarios": {"normal": None, "low_rainfall": {}}}):
            if payload is None:
                continue
            with self.subTest(payload=payload), self.assertRaises(ValueError) as error:
                e.evaluate_rotation(payload=payload, **BASE)
            self.assertTrue(is_message_translated(str(error.exception)))

    def test_cross_year_season_lengths_include_leap_day(self):
        for scenario, days in (("normal", 151), ("low_rainfall", 152)):
            climate = self.evaluate(season="Dong_Xuan", scenario=scenario)["climate"]
            self.assertEqual(climate["season_days"], days)
            self.assertAlmostEqual(climate["dry_day_fraction"], climate["dry_days"] / days)
        self.payload["scenarios"]["normal"]["Dong_Xuan"]["analog_year"] = 2006
        self.assertFalse(self.evaluate(season="Dong_Xuan", scenario="normal")["climate"]["usable"])

    def test_priorities_change_weights_not_observations_or_components(self):
        results = [self.evaluate(goal=goal) for goal in e.WEIGHTS]
        self.assertEqual(sum(results[0]["weights"].values()), 1)
        self.assertEqual(results[0]["climate"], results[1]["climate"])
        for index in (0, 1):
            self.assertEqual(results[0]["options"][index]["components"],
                             results[2]["options"][index]["components"])
        self.assertGreater(len({r["leading_option_id"] for r in results}), 1)

    def test_no_scenario_label_or_crop_winner_override(self):
        self.payload["scenarios"]["low_rainfall"]["He_Thu"] = deepcopy(
            self.payload["scenarios"]["normal"]["He_Thu"])
        normal, low = self.evaluate(scenario="normal"), self.evaluate(scenario="low_rainfall")
        self.assertEqual([o["score"] for o in normal["options"]], [o["score"] for o in low["options"]])
        self.assertEqual(normal["leading_option_id"], low["leading_option_id"])

    def test_ties_do_not_create_an_arbitrary_winner(self):
        with patch.object(e, "_weighted_score", return_value=50.0):
            result = self.evaluate()
        self.assertIsNone(result["leading_option_id"])
        self.assertEqual(result["ranked_ids"], ["rice_rice", "rice_sesame"])

    def test_score_breakdown_reconstructs_final_score(self):
        result = self.evaluate()
        for option in result["options"]:
            self.assertEqual(round(sum(option["score_breakdown"].values()), 1), option["score"])
            self.assertTrue(option["water_assessment"]["experimental"])
        self.assertIn("EXPERIMENTAL", result["method"])

    def test_validation_and_all_new_explanations_are_bilingual(self):
        cases = (dict(season="bad"), dict(scenario="bad"), dict(irrigation=[]),
                 dict(soil_ph=math.nan), dict(soil_ph=True), dict(soil_ph="bad"),
                 dict(crop_calendar_confirmed="yes"))
        for changes in cases:
            with self.assertRaises(ValueError) as error:
                self.evaluate(**changes)
            self.assertTrue(is_message_translated(str(error.exception)), str(error.exception))
        result = self.evaluate()
        messages = [result["summary"], result["method"], *result["notes"], *result["missing_info"]]
        messages += [w for o in result["options"] for w in o["warnings"]]
        for message in messages:
            for lang in ("vi", "en"):
                self.assertNotIn("chưa được dịch", translate_message(message, lang))
                self.assertNotIn("Untranslated", translate_message(message, lang))
        self.assertIn("Nhiệt độ", translate_message(next(m for m in messages if m.startswith("Historical mean")), "vi"))
        self.assertIn("not flowering-stage", translate_message(next(m for m in messages if m.startswith("Historical mean")), "en"))

    def test_evaluation_does_not_mutate_payload_or_global_parameters(self):
        original = deepcopy(self.payload)
        first = self.evaluate()
        first["weights"]["water"] = 999
        first["experimental_parameters"]["crop_exposure"]["rice"] = 999
        first["provenance"]["location"]["period"] = "bad"
        second = self.evaluate()
        self.assertEqual(self.payload, original)
        self.assertEqual(second["weights"], e.WEIGHTS["save_water"])
        self.assertEqual(second["experimental_parameters"], e.PARAMETERS)
        self.assertEqual(second["provenance"]["location"]["period"], "2006-2025")

    def test_compare_uses_one_snapshot_and_preserves_input_dictionary(self):
        arguments = BASE.copy()
        with patch.object(e, "load_payload", wraps=e.load_payload) as loader:
            results = e.compare_scenarios(**arguments)
        self.assertEqual(loader.call_count, 1)
        self.assertEqual(tuple(results), e.SCENARIOS)
        self.assertEqual(arguments, BASE)


class ComparisonMatrixTests(unittest.TestCase):
    def test_frozen_matrix_is_complete_and_reproducible(self):
        from scripts.compare_decision_engines import compare, input_matrix, summarize
        rows = compare()
        self.assertEqual(len(list(input_matrix())), 144)
        self.assertEqual(len(rows), 288)
        self.assertEqual(len({(row["case_id"], row["option"]) for row in rows}), 288)
        self.assertEqual(rows, compare())
        self.assertEqual(summarize(rows)["comparable_option_rows"], 108)

    def test_score_differences_are_attributed_without_thermal_penalties(self):
        from scripts.compare_decision_engines import compare
        for row in compare():
            if row["old_score"] is not None and row["new_score"] is not None:
                calculated = (row["rainfall_rule_delta_points_unrounded"]
                              + row["dry_day_delta_points_unrounded"])
                displayed = row["new_score"] - row["old_score"]
                self.assertLessEqual(abs(calculated - displayed), 0.0500001)
                self.assertEqual(row["temperature_delta_points"], 0)
                self.assertEqual(row["hot_day_delta_points"], 0)

    def test_comparison_refuses_a_changed_payload(self):
        from scripts import compare_decision_engines as matrix
        from unittest.mock import Mock
        with patch.object(matrix.e, "PAYLOAD_PATH", Mock(read_bytes=lambda: b"different dataset")):
            with self.assertRaisesRegex(ValueError, "different datasets"):
                matrix.compare()


if __name__ == "__main__":
    unittest.main()

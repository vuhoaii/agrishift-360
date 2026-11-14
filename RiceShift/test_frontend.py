"""Presentation regression tests. Run: python -B -m unittest test_frontend."""
import itertools
import unittest
import json
from copy import deepcopy
from unittest.mock import patch
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from web import app
from services.scoring_engine import evaluate_rotation, load_payload
from presentation_messages import is_message_translated, translate_message


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        self.elements.append((tag, dict(attributes)))


class FrontendTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.state = dict(season="Dong_Xuan", scenario="normal", drainage="good",
                          irrigation="limited", salinity="no", soil_ph="6,5",
                          goal="protect_soil", calendar="yes")

    def test_six_views_in_both_languages_keep_state(self):
        for language, view in itertools.product(("vi", "en"),
                ("dashboard", "farm", "climate", "comparison", "insights", "method")):
            with self.subTest(language=language, view=view):
                response = self.client.get("/", query_string=dict(self.state, lang=language, view=view))
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('<html lang="' + language + '">', html)
                self.assertNotIn("[Untranslated source message]", html)
                page = Page(html)
                for tag, attrs in page.elements:
                    if tag != "a":
                        continue
                    query = parse_qs(urlparse(attrs.get("href", "")).query)
                    if "view" not in query:
                        continue
                    for key, value in self.state.items():
                        self.assertEqual(query.get(key), [value], (view, key))
                    self.assertIn(query.get("lang"), (["vi"], ["en"]))

    def test_every_current_engine_explanation_has_a_translation(self):
        payload = load_payload()
        cases = itertools.product(
            ("Dong_Xuan", "He_Thu", "Thu_Dong"), ("normal", "low_rainfall"),
            ("good", "poor", "unknown"), ("available", "limited", "unknown"),
            ("yes", "no", "unknown"), ("save_water", "protect_soil", "keep_practice"),
            (None, 6.5, 8), (False, True),
        )
        messages = set()
        for season, scenario, drainage, irrigation, salinity, goal, ph, calendar in cases:
            result = evaluate_rotation(
                season=season, scenario=scenario, drainage=drainage,
                irrigation=irrigation, salinity=salinity, goal=goal,
                soil_ph=ph, crop_calendar_confirmed=calendar, payload=payload,
            )
            messages.update([result["summary"], result["method"], result["climate"]["location"]])
            messages.update(result["notes"])
            messages.update(result["missing_info"])
            for option in result["options"]:
                messages.update([option["name"], *option["reasons"], *option["warnings"]])
        for message in messages:
            self.assertTrue(is_message_translated(message), message)
            self.assertNotIn("[Untranslated source message]", translate_message(message, "en"))

    def test_complete_message_matching_and_unknown_fallback(self):
        sentence = "Kiem tra do man dat va nuoc."
        self.assertTrue(is_message_translated(sentence))
        self.assertFalse(is_message_translated("prefix " + sentence))
        self.assertFalse(is_message_translated(sentence + " extra"))
        self.assertIn("[Untranslated source message]", translate_message("new message", "en"))

    def test_invalid_inputs_are_translated_and_preserved(self):
        for value in ("bad", "15", "<script>alert(1)</script>"):
            response = self.client.get("/", query_string=dict(self.state, view="farm", lang="en", soil_ph=value))
            html = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Soil pH must", html)
            self.assertNotIn("[Untranslated source message]", html)
            self.assertNotIn("<script>alert(1)</script>", html)
            fields = [attrs for tag, attrs in Page(html).elements
                      if tag == "input" and attrs.get("name") == "soil_ph"]
            self.assertEqual(fields[0]["value"], value)
        for key in ("season", "scenario", "drainage", "irrigation", "salinity", "goal"):
            parameters = dict(self.state, view="farm", lang="en")
            parameters[key] = "invalid"
            html = self.client.get("/", query_string=parameters).get_data(as_text=True)
            self.assertIn("selection is invalid", html)
            self.assertNotIn("[Untranslated source message]", html)

    def test_null_scores_and_verification_options_are_not_ranked(self):
        html = self.client.get("/", query_string=dict(view="comparison", lang="en",
            drainage="poor", irrigation="unknown")).get_data(as_text=True)
        self.assertIn("Important information missing", html)
        self.assertIn("Poor drainage requires field verification", html)
        self.assertNotIn('class="score-value"', html)
        self.assertNotIn("sesame leading", html)
        self.assertNotIn("rice leading", html)
        self.assertNotIn("[Untranslated source message]", html)

    def test_language_does_not_change_report(self):
        vi = self.client.get("/report.json", query_string=dict(self.state, lang="vi"))
        en = self.client.get("/report.json", query_string=dict(self.state, lang="en"))
        self.assertEqual(vi.status_code, 200)
        self.assertEqual(vi.json, en.json)
        self.assertEqual(en.json["context"]["soil_ph"], 6.5)
        self.assertTrue(en.json["context"]["crop_calendar_confirmed"])
        self.assertIn("attachment", en.headers["Content-Disposition"])

    def test_selected_climate_updates_from_real_payload(self):
        normal = self.client.get("/report.json", query_string=dict(self.state, scenario="normal")).json
        dry = self.client.get("/report.json", query_string=dict(self.state, scenario="low_rainfall")).json
        self.assertNotEqual(normal["climate"]["rain_mm"], dry["climate"]["rain_mm"])
        for scenario, report in (("normal", normal), ("low_rainfall", dry)):
            html = self.client.get("/", query_string=dict(self.state, scenario=scenario,
                view="climate", lang="en")).get_data(as_text=True)
            self.assertIn("%.2f" % report["climate"]["rain_mm"], html)
            self.assertIn("not a weather forecast", html)

    def test_post_and_existing_health_route(self):
        response = self.client.post("/?view=comparison&lang=en", data=self.state)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Rice →", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/health").json["status"], "ok")


    def test_v2_routes_and_reports_across_climates_and_priorities(self):
        for season, scenario, irrigation, goal, language in itertools.product(
                ("Dong_Xuan", "He_Thu", "Thu_Dong"), ("normal", "low_rainfall"),
                ("available", "limited"), ("save_water", "protect_soil", "keep_practice"),
                ("vi", "en")):
            params = dict(self.state, season=season, scenario=scenario,
                          irrigation=irrigation, goal=goal, lang=language)
            with self.subTest(params=params):
                response = self.client.get("/report.json", query_string=params)
                self.assertEqual(response.status_code, 200)
                report = response.json
                self.assertEqual(report["engine_version"], "2.0")
                self.assertEqual(report["provenance"]["analysis_window"]["analysis_end_year"], 2025)
                self.assertEqual(len(report["options"]), 2)
                self.assertEqual(set(report["weights"]), {"water", "diversity", "continuity"})
                self.assertIn("rainfall_penalty", report["options"][0]["water_assessment"])
                json.dumps(report, allow_nan=False)
                html = self.client.get("/", query_string=dict(params, view="comparison")).get_data(as_text=True)
                self.assertNotIn("Untranslated source", html)
                self.assertNotIn("chưa được dịch", html)
                self.assertIn('class="score-value"', html)

    def test_drainage_salinity_calendar_gates_survive_json_export(self):
        for changes in (dict(drainage="poor"), dict(drainage="unknown"),
                        dict(irrigation="unknown"), dict(salinity="yes"),
                        dict(salinity="unknown"), dict(calendar="")):
            params = dict(self.state, **changes)
            report = self.client.get("/report.json", query_string=params).json
            self.assertIsNone(report["leading_option_id"])
            self.assertIsNone(report["options"][1]["score"])
            self.assertEqual(report["options"][1]["status"], "needs_info")
            for language in ("vi", "en"):
                html = self.client.get("/", query_string=dict(params, lang=language, view="comparison")).get_data(as_text=True)
                self.assertNotIn("Untranslated source", html)
                self.assertNotIn("chưa được dịch", html)
                self.assertNotIn("sesame leading", html)
                self.assertNotIn("rice leading", html)

    def test_invalid_rain_is_a_localized_error_and_report_400(self):
        payload = deepcopy(load_payload())
        payload["scenarios"]["normal"]["Dong_Xuan"]["total_rain_mm"] = float("nan")
        with patch("services.scoring_engine.load_payload", return_value=payload):
            for lang, expected in (("en", "Rainfall data is missing or invalid"),
                                   ("vi", "Dữ liệu lượng mưa thiếu hoặc không hợp lệ")):
                response = self.client.get("/report.json", query_string=dict(self.state, lang=lang))
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
                html = self.client.get("/", query_string=dict(self.state, lang=lang)).get_data(as_text=True)
                self.assertIn(expected, html)
                self.assertNotIn("Untranslated", html)

    def test_missing_thermal_or_dry_indicators_export_null_scores_and_render_all_views(self):
        for field in ("avg_temp_C", "hot_days_over_35C", "dry_days", "analog_year"):
            payload = deepcopy(load_payload())
            payload["scenarios"]["normal"]["Dong_Xuan"][field] = None
            with patch("services.scoring_engine.load_payload", return_value=payload):
                report = self.client.get("/report.json", query_string=self.state)
                self.assertEqual(report.status_code, 200)
                self.assertEqual(report.json["ranked_ids"], [])
                self.assertIsNone(report.json["leading_option_id"])
                json.dumps(report.json, allow_nan=False)
                for lang, view in itertools.product(("vi", "en"),
                        ("dashboard", "farm", "climate", "comparison", "insights", "method")):
                    response = self.client.get("/", query_string=dict(self.state, lang=lang, view=view))
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertNotIn("Untranslated", html)
                    self.assertNotIn("chưa được dịch", html)

    def test_v2_methodology_matches_formula_in_both_languages(self):
        en = self.client.get("/", query_string=dict(self.state, lang="en", view="method")).get_data(as_text=True)
        vi = self.client.get("/", query_string=dict(self.state, lang="vi", view="method")).get_data(as_text=True)
        self.assertIn("0.5 x D + 0.5 x F", en)
        self.assertIn("EXPERIMENTAL", en)
        self.assertIn("0,5 × D + 0,5 × F", vi)
        self.assertIn("THỬ NGHIỆM", vi)


if __name__ == "__main__":
    unittest.main()

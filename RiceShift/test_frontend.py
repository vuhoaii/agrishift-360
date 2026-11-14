"""Presentation regression tests. Run: python -B -m unittest test_frontend."""
import itertools
import unittest
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

    def test_null_scores_and_blocked_options_are_not_ranked(self):
        html = self.client.get("/", query_string=dict(view="comparison", lang="en",
            drainage="poor", irrigation="unknown")).get_data(as_text=True)
        self.assertIn("Excluded from current screening", html)
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


if __name__ == "__main__":
    unittest.main()

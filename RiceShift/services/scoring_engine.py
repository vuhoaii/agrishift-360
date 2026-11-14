"""RiceShift Decision Engine v2: explainable, experimental historical screening.

NASA observations are never forecasts or field measurements. Numerical mappings
below are prototype assumptions, not calibrated crop response functions.
"""

from __future__ import annotations

import calendar
import json
import math
from copy import deepcopy
from numbers import Real
from pathlib import Path

PAYLOAD_PATH = Path(__file__).resolve().parents[1] / "data/processed/climate_payload_latest.json"
ENGINE_VERSION = "2.0"
SOURCES = {
    "nasa": "https://power.larc.nasa.gov/",
    "rice_water": "https://www.fao.org/4/S2022E/s2022e08.htm",
    "sesame": "https://content.ces.ncsu.edu/sesame-production-fact-sheet",
    "rice_heat": "https://ricetoday.irri.org/rice-feels-the-heat/",
    "salinity": "https://www.fao.org/4/t0234e/t0234e03.htm",
    "dry_days": "https://etccdi.pacificclimate.org/list_27_indices.shtml",
}
# All point mappings, attenuation factors and goal weights are EXPERIMENTAL.
# Qualitative crop differences do not validate these numerical ratios.
PARAMETERS = {
    "rainfall_share": 0.5,
    "dry_day_share": 0.5,
    "irrigation_exposure": {"available": 0.25, "limited": 1.0},
    "water_base": {"available": 2.0, "limited": 1.0},
    "crop_exposure": {"rice": 1.0, "sesame": 0.5},
}
WEIGHTS = {
    "save_water": {"water": 0.70, "diversity": 0.10, "continuity": 0.20},
    "protect_soil": {"water": 0.25, "diversity": 0.60, "continuity": 0.15},
    "keep_practice": {"water": 0.25, "diversity": 0.10, "continuity": 0.65},
}
LABELS = {
    "save_water": "Ưu tiên giảm áp lực nước",
    "protect_soil": "Ưu tiên đa dạng luân canh",
    "keep_practice": "Ưu tiên ít thay đổi cách canh tác",
}
SEASONS = ("Dong_Xuan", "He_Thu", "Thu_Dong")
SCENARIOS = ("normal", "low_rainfall")
METHOD = (
    "Decision Engine v2: score = 50 x sum(weight x component 0-2). "
    "Water = B - E x C x (0.5 x D + 0.5 x F), where D = max(0, 1 - rain/P50 analog rain), "
    "F = dry days/season days, B = 2 with available irrigation or 1 with limited irrigation, "
    "E = 0.25 or 1 respectively, and C = 1 for rice or 0.5 for sesame. "
    "All coefficients and weights are EXPERIMENTAL. Temperature and hot days inform separate "
    "verification warnings, without numerical penalties. This is not validated suitability, "
    "a yield forecast or a probability of success."
)


def load_payload():
    """Read the processed local archive without calling NASA."""
    if not PAYLOAD_PATH.is_file():
        raise FileNotFoundError(f"Thieu du lieu NASA: {PAYLOAD_PATH}")
    try:
        return json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Historical climate payload is invalid.") from exc


def _number(value, minimum=None, maximum=None, whole=False):
    """Strict JSON-number validation: do not turn bools/strings into observations."""
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        value = float(value)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(value):
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    if whole and not value.is_integer():
        return None
    return int(value) if whole else value


def _season_days(season, year):
    year = _number(year, 1, 9999, whole=True)
    if year is None:
        return None
    months = {"Dong_Xuan": (11, 12, 1, 2, 3), "He_Thu": (4, 5, 6, 7),
              "Thu_Dong": (8, 9, 10)}[season]
    # November/December are in the previous year; their lengths are invariant.
    return sum(calendar.monthrange(year, month)[1] for month in months)


def analyze_climate(payload, season, scenario):
    if not isinstance(payload, dict):
        raise ValueError("Historical climate payload is invalid.")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, dict) or scenario not in scenarios or "normal" not in scenarios:
        raise ValueError("Kich ban khong hop le hoac thieu normal.")
    records = []
    for key in (scenario, "normal"):
        group = scenarios[key]
        if not isinstance(group, dict) or not isinstance(group.get(season), dict):
            raise ValueError(f"Khong co du lieu mua vu: {season}")
        records.append(group[season])
    current, baseline = records
    rain = _number(current.get("total_rain_mm"), 0)
    ref = _number(baseline.get("total_rain_mm"), 0)
    if rain is None or ref is None or ref <= 0:
        raise ValueError("Du lieu luong mua thieu hoac khong hop le.")
    ratio = rain / ref
    if not math.isfinite(ratio) or not math.isfinite(100 * (ratio - 1)):
        raise ValueError("Du lieu luong mua thieu hoac khong hop le.")

    issues = []
    window = payload.get("analysis_window", {})
    location = payload.get("location", {})
    if not isinstance(window, dict) or not isinstance(location, dict):
        raise ValueError("Historical climate payload is invalid.")

    def read_indicators(record, role):
        year = _number(record.get("analog_year"), 1, 9999, whole=True)
        days = _season_days(season, year)
        start = window.get("analysis_start_year")
        end = window.get("analysis_end_year")
        if isinstance(start, int) and isinstance(end, int) and year is not None:
            first = start + (1 if season == "Dong_Xuan" else 0)
            if not first <= year <= end:
                days = None
        if days is None:
            issues.append(f"Historical indicator is missing or invalid: analog_year ({role}).")
        # Broad technical sanity bounds reject NASA fill values; not crop thresholds.
        temp = _number(record.get("avg_temp_C"), -100, 100)
        hot = _number(record.get("hot_days_over_35C"), 0, days, whole=True)
        dry = _number(record.get("dry_days"), 0, days, whole=True)
        for field, value in (("avg_temp_C", temp), ("hot_days_over_35C", hot), ("dry_days", dry)):
            if value is None:
                issues.append(f"Historical indicator is missing or invalid: {field} ({role}).")
        return year, days, temp, hot, dry

    year, days, temp, hot, dry = read_indicators(current, "selected")
    ref_year, ref_days, ref_temp, ref_hot, ref_dry = read_indicators(baseline, "baseline")
    deficit = max(0.0, 1.0 - ratio)
    dry_fraction = dry / days if dry is not None and days else None
    return {
        "season": season, "scenario": scenario, "analog_year": year,
        "rain_mm": round(rain, 2), "normal_rain_mm": round(ref, 2),
        "rain_change_pct": round(100 * (ratio - 1), 1),
        "rainfall_deficit_fraction": deficit,
        "avg_temp_c": temp, "hot_days": hot, "dry_days": dry,
        "season_days": days, "normal_season_days": ref_days,
        "normal_analog_year": ref_year, "normal_avg_temp_c": ref_temp,
        "normal_hot_days": ref_hot, "normal_dry_days": ref_dry,
        "temperature_change_c": temp - ref_temp if temp is not None and ref_temp is not None else None,
        "hot_day_fraction": hot / days if hot is not None and days else None,
        "dry_day_fraction": dry_fraction,
        "observed_through": location.get("observed_through"),
        "location": location.get("name", "Địa điểm thí điểm"),
        "usable": not issues, "issues": issues,
    }


def _water_assessment(crop, irrigation, climate):
    if irrigation == "unknown" or not climate["usable"]:
        return None
    p = PARAMETERS
    deficit = climate["rainfall_deficit_fraction"]
    dry_fraction = climate["dry_day_fraction"]
    base = p["water_base"][irrigation]
    exposure = p["irrigation_exposure"][irrigation] * p["crop_exposure"][crop]
    rain_penalty = exposure * p["rainfall_share"] * deficit
    dry_penalty = exposure * p["dry_day_share"] * dry_fraction
    return {
        "base": base, "exposure": exposure,
        "rainfall_deficit_fraction": deficit, "dry_day_fraction": dry_fraction,
        "rainfall_penalty": rain_penalty, "dry_day_penalty": dry_penalty,
        "score": max(0.0, min(2.0, base - rain_penalty - dry_penalty)),
        "experimental": True,
    }


def _weighted_score(components, goal):
    if any(components.get(key) is None for key in WEIGHTS[goal]):
        return None
    return round(50 * sum(components[key] * weight for key, weight in WEIGHTS[goal].items()), 1)


def evaluate_rotation(
    season="He_Thu", scenario="low_rainfall", drainage="unknown",
    irrigation="unknown", goal="save_water", salinity="unknown",
    soil_ph=None, crop_calendar_confirmed=False, payload=None,
):
    """Conservatively screen the same two options; preserve the Flask/JSON API."""
    choices = {
        "season": (season, SEASONS), "scenario": (scenario, SCENARIOS),
        "drainage": (drainage, ("good", "poor", "unknown")),
        "irrigation": (irrigation, ("available", "limited", "unknown")),
        "salinity": (salinity, ("no", "yes", "unknown")), "goal": (goal, WEIGHTS),
    }
    for name, (value, allowed) in choices.items():
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(f"{name} khong hop le: {value}")
    if not isinstance(crop_calendar_confirmed, bool):
        raise ValueError("The crop calendar confirmation must be true or false.")
    if soil_ph is not None:
        try:
            ph = float(soil_ph) if not isinstance(soil_ph, bool) else math.nan
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("pH phai nam trong khoang 0-14.") from exc
        if not math.isfinite(ph) or not 0 <= ph <= 14:
            raise ValueError("pH phai nam trong khoang 0-14.")
        soil_ph = ph

    source_payload = payload if payload is not None else load_payload()
    climate = analyze_climate(source_payload, season, scenario)
    missing = []
    notes = [
        "Hai kich ban la cac mua lich su, khong phai du bao.",
        "Tong mua ca vu khong du de ket luan nguon nuoc hoac nguy co ngap tai ruong.",
        "NASA POWER is gridded historical data, not a measurement from the field.",
        "Rainfall and dry-day frequency share a bounded experimental water component; they are not statistically independent.",
        "Temperature and hot days are assessed separately from rainfall. Seasonal summaries cannot establish exposure during flowering.",
        "Categorical drainage and salinity inputs require local verification; they are not universal crop exclusion thresholds.",
    ]
    if not crop_calendar_confirmed:
        missing.append("Xac minh lich trong va giong tai dia phuong.")
        notes.append("Lich mua vu trong pipeline la gia dinh thi diem.")
    if salinity == "unknown":
        missing.append("Kiem tra do man dat va nuoc.")
    elif salinity == "yes":
        missing.append("Reported salinity needs measured soil and water conductivity and local variety advice before ranking either option.")
    if soil_ph is None:
        missing.append("Bo sung pH dat neu co ket qua do.")
    if irrigation == "unknown":
        missing.append("Kha nang chu dong tuoi cua ruong?")
    if drainage == "unknown":
        missing.append("Ruong co dong nuoc sau mua lon khong?")
    elif drainage == "poor":
        missing.append("Poor drainage requires field verification or improvement before sesame can be ranked.")
    if not climate["usable"]:
        missing.append("Incomplete or invalid historical indicators prevent ranking; missing values are not assumed safe.")
        notes.extend(climate["issues"])

    options = []
    for crop, option_id, title in (
        ("rice", "rice_rice", "Lúa → Lúa"),
        ("sesame", "rice_sesame", "Lúa → Mè"),
    ):
        reasons, warnings, checks = [], [], []

        def check(rule, classification, message):
            checks.append({"rule": rule, "classification": classification, "effect": "withhold_ranking"})
            warnings.append(message)

        if irrigation == "unknown":
            check("irrigation", "missing_information", "Kha nang chu dong tuoi cua ruong?")
        if salinity != "no":
            check("salinity", "local_verification" if salinity == "yes" else "missing_information",
                  "Reported salinity needs measured soil and water conductivity and local variety advice before ranking either option."
                  if salinity == "yes" else "Chua co thong tin do man.")
        if not crop_calendar_confirmed:
            check("crop_calendar", "missing_information", "Xac minh lich trong va giong tai dia phuong.")
        if not climate["usable"]:
            check("historical_indicators", "missing_information",
                  "Incomplete or invalid historical indicators prevent ranking; missing values are not assumed safe.")

        if crop == "sesame":
            if drainage == "poor":
                check("drainage", "local_verification",
                      "Poor drainage requires field verification or improvement before sesame can be ranked.")
            elif drainage == "unknown":
                check("drainage", "missing_information",
                      "Chua ro kha nang thoat nuoc. Chua the xep hang phuong an me.")
            else:
                reasons.append("Thoat nuoc tot la dieu kien thuan loi de can nhac trong me.")
            if soil_ph is not None and not 5.5 <= soil_ph <= 7:
                warnings.append("pH ngoai khoang tham khao 5.5-7.0 cua NC State. Can kiem tra giong va dat.")
            reasons.append("Thay doi loai cay giup da dang hoa chuoi luan canh. Loi ich voi dat can duoc kiem chung.")
            warnings.append("Sesame tolerates drought relatively well but still needs moisture for germination and establishment.")
        else:
            reasons.append("Tiep tuc phuong thuc trong lua quen thuoc, it thay doi ky thuat.")
            if irrigation == "limited":
                warnings.append("Nguon tuoi han che co the gay kho khan cho lua nuoc.")

        if climate["rain_change_pct"] < 0:
            warnings.append(
                f"Mua lich su nay co tong mua thap hon {abs(climate['rain_change_pct']):.1f}% "
                "so voi moc dien hinh. Day khong phai chan doan han."
            )
        if climate["avg_temp_c"] is not None and climate["temperature_change_c"] is not None:
            warnings.append(
                f"Historical mean temperature: {climate['avg_temp_c']:.2f} C; "
                f"difference from P50: {climate['temperature_change_c']:+.2f} C. "
                "This is not flowering-stage temperature."
            )
        if climate["hot_days"] is not None:
            warnings.append(
                f"Historical days with Tmax above 35 C: {climate['hot_days']}. "
                "The timing and duration of heat exposure are unknown."
            )
            if crop == "rice" and climate["hot_days"] > 0:
                warnings.append("Rice flowering is heat-sensitive. Check whether hot days overlapped flowering; this count does not establish sterility or yield loss.")
            elif crop == "sesame":
                warnings.append("The 35 C hot-day indicator is not a validated sesame injury threshold; no crop-specific heat penalty is assigned.")
        if climate["dry_days"] is not None and climate["season_days"]:
            warnings.append(
                f"Historical dry days below 1 mm: {climate['dry_days']} of {climate['season_days']}. "
                "This is a seasonal count, not a consecutive dry spell or a diagnosis of crop drought."
            )
        water = _water_assessment(crop, irrigation, climate)
        components = {
            "water": water["score"] if water else None,
            "diversity": 0 if crop == "rice" else 2,
            "continuity": 2 if crop == "rice" else 0,
        }
        status = "needs_info" if checks else "review"
        score = _weighted_score(components, goal) if status == "review" else None
        breakdown = {key: 50 * components[key] * weight if components[key] is not None else None
                     for key, weight in WEIGHTS[goal].items()}
        options.append({
            "id": option_id, "name": title, "status": status, "score": score,
            "components": components, "reasons": reasons, "warnings": warnings,
            "sources": [SOURCES["nasa"], SOURCES["rice_water"] if crop == "rice" else SOURCES["sesame"],
                        SOURCES["rice_heat"], SOURCES["salinity"], SOURCES["dry_days"]] if crop == "rice" else
                       [SOURCES["nasa"], SOURCES["sesame"], SOURCES["salinity"], SOURCES["dry_days"]],
            "water_assessment": water, "score_breakdown": breakdown, "screening_checks": checks,
            "risk_indicators": {
                "mean_temperature": {"value_c": climate["avg_temp_c"],
                    "change_c": climate["temperature_change_c"], "effect": "context_only"},
                "hot_days": {"count": climate["hot_days"], "threshold_c": 35,
                    "effect": "verify_flowering_exposure" if crop == "rice" and climate["hot_days"] else "context_only"},
                "dry_days": {"count": climate["dry_days"], "threshold_mm": 1,
                    "fraction": climate["dry_day_fraction"], "effect": "experimental_water_score"},
                "rainfall": {"deficit_fraction": climate["rainfall_deficit_fraction"],
                    "effect": "experimental_water_score"},
            },
        })

    ranked = sorted((o for o in options if o["score"] is not None), key=lambda o: (-o["score"], o["id"]))
    winner = ranked[0]["id"] if len(ranked) == 2 and ranked[0]["score"] > ranked[1]["score"] else None
    summary = (
        f"Theo thang diem uu tien THU NGHIEM: {ranked[0]['name']} dang dung truoc "
        "trong hai phuong an du thong tin de so sanh."
        if winner else "Chua du co so de xac dinh phuong an dan dau mot cach co the so sanh."
    )
    return {
        "engine_version": ENGINE_VERSION, "climate": climate,
        "context": {"drainage": drainage, "irrigation": irrigation, "goal": goal,
                    "salinity": salinity, "soil_ph": soil_ph,
                    "crop_calendar_confirmed": crop_calendar_confirmed},
        "weights": dict(WEIGHTS[goal]), "options": options,
        "ranked_ids": [o["id"] for o in ranked], "leading_option_id": winner,
        "summary": summary, "missing_info": missing, "notes": notes, "method": METHOD,
        "experimental_parameters": deepcopy(PARAMETERS),
        "provenance": {key: deepcopy(source_payload.get(key))
                       for key in ("location", "analysis_window", "data_quality", "scenario_note")},
    }


def compare_scenarios(**kwargs):
    kwargs.pop("scenario", None)
    if kwargs.get("payload") is None:
        kwargs["payload"] = load_payload()
    return {scenario: evaluate_rotation(scenario=scenario, **kwargs) for scenario in SCENARIOS}

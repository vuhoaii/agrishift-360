"""Reproduce v1/v2 comparisons from the frozen pre-edit v1 matrix.

Run from repository root:
  .\\RiceShift\\.venv\\Scripts\\python.exe -B -X utf8 RiceShift/scripts/compare_decision_engines.py --summary
Add --output docs/decision-engine-v2-comparison.csv to write the full CSV.
"""
import argparse
import csv
import hashlib
import itertools
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
from services import scoring_engine as e

BASELINE_PATH = APP_DIR / "tests/fixtures/decision_engine_v1_baseline.json"
FARMS = (
    ("known_good", "good", "limited", "no", True),
    ("reliable_irrigation", "good", "available", "no", True),
    ("poor_drainage", "poor", "limited", "no", True),
    ("unknown_drainage", "unknown", "limited", "no", True),
    ("unknown_irrigation", "good", "unknown", "no", True),
    ("reported_salinity", "good", "limited", "yes", True),
    ("unknown_salinity", "good", "limited", "unknown", True),
    ("unconfirmed_calendar", "good", "limited", "no", False),
)


def input_matrix():
    for season, scenario, goal, farm in itertools.product(e.SEASONS, e.SCENARIOS, e.WEIGHTS, FARMS):
        name, drainage, irrigation, salinity, calendar = farm
        yield ":".join((season, scenario, goal, name)), dict(
            season=season, scenario=scenario, goal=goal, drainage=drainage,
            irrigation=irrigation, salinity=salinity, soil_ph=6.5,
            crop_calendar_confirmed=calendar)


def compare():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256(e.PAYLOAD_PATH.read_bytes()).hexdigest()
    if actual_hash != baseline["payload_sha256"]:
        raise ValueError("Payload differs from the captured v1 baseline; do not compare different datasets.")
    frozen = {row[0]: row[1:] for row in baseline["cases"]}
    if set(frozen) != {key for key, _ in input_matrix()}:
        raise ValueError("The input matrix differs from the frozen v1 baseline.")
    payload = e.load_payload()
    rows = []
    for case_id, inputs in input_matrix():
        before = frozen[case_id]
        result = e.evaluate_rotation(payload=payload, **inputs)
        for index, option in enumerate(result["options"]):
            old_status, old_score, old_water = before[index]
            new_score = option["score"]
            water = option["water_assessment"]
            comparable = old_score is not None and new_score is not None
            scale = 50 * result["weights"]["water"]
            rain_delta = scale * (water["base"] - water["rainfall_penalty"] - old_water) if comparable else None
            dry_delta = -scale * water["dry_day_penalty"] if comparable else None
            rows.append({
                "case_id": case_id, "option": option["id"], **inputs,
                "rain_mm": result["climate"]["rain_mm"],
                "rain_deficit_fraction": result["climate"]["rainfall_deficit_fraction"],
                "dry_days": result["climate"]["dry_days"],
                "season_days": result["climate"]["season_days"],
                "avg_temp_c": result["climate"]["avg_temp_c"],
                "hot_days": result["climate"]["hot_days"],
                "old_status": old_status, "new_status": option["status"],
                "old_score": old_score, "new_score": new_score,
                "score_delta": round(new_score - old_score, 1) if comparable else None,
                "old_water": old_water, "new_water": option["components"]["water"],
                "rainfall_rule_delta_points_unrounded": rain_delta,
                "dry_day_delta_points_unrounded": dry_delta,
                "temperature_delta_points": 0, "hot_day_delta_points": 0,
                "old_leader": before[2], "new_leader": result["leading_option_id"],
                "ranking_gate_causes": "|".join(check["rule"] for check in option["screening_checks"]),
                "numeric_change_causes": "continuous_rainfall_rule|dry_day_frequency" if comparable else "",
            })
    return rows


def summarize(rows):
    cases = {r["case_id"]: r for r in rows}
    paired = [r for r in rows if r["old_score"] is not None and r["new_score"] is not None]
    return {
        "cases": len(cases), "option_rows": len(rows),
        "comparable_option_rows": len(paired),
        "score_changed_rows": sum(r["old_score"] != r["new_score"] for r in paired),
        "status_changed_rows": sum(r["old_status"] != r["new_status"] for r in rows),
        "leader_changed_cases": sum(r["old_leader"] != r["new_leader"] for r in cases.values()),
        "known_farm_leader_changes": [
            {"case_id": r["case_id"], "old": r["old_leader"], "new": r["new_leader"]}
            for r in cases.values()
            if r["case_id"].endswith((":known_good", ":reliable_irrigation"))
            and r["old_leader"] != r["new_leader"]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    rows = compare()
    if args.output:
        with args.output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
    if args.summary:
        print(json.dumps(summarize(rows), ensure_ascii=False, indent=2))
    elif not args.output:
        writer = csv.DictWriter(sys.stdout, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

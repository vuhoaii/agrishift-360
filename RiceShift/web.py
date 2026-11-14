
"""RiceShift public website - Flask."""

import json

from flask import (
    Flask, Response, jsonify,
    render_template, request,
)

from services.scoring_engine import (
    evaluate_rotation,
    compare_scenarios,
    LABELS,
)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024


SEASONS = {
    "Dong_Xuan": "Đông Xuân (11–03)",
    "He_Thu": "Hè Thu (04–07)",
    "Thu_Dong": "Thu Đông (08–10)",
}

SCENARIOS = {
    "normal": "Mùa điển hình (P50)",
    "low_rainfall": "Mùa ít mưa (P25)",
}

STATUS = {
    "review": "Có thể khảo sát thêm",
    "needs_info": "Thiếu thông tin quan trọng",
    "blocked": "Tạm loại khỏi sàng lọc",
}

DEFAULTS = {
    "season": "He_Thu",
    "scenario": "low_rainfall",
    "drainage": "good",
    "irrigation": "limited",
    "salinity": "unknown",
    "goal": "save_water",
    "soil_ph": "",
    "calendar": "",
}


# ======================================
# 1. ĐỌC VÀ KIỂM TRA INPUT NGƯỜI DÙNG
# ======================================

def parse_inputs(source):

    selected = {
        key: str(source.get(key, default)).strip()
        for key, default in DEFAULTS.items()
    }

    valid = {
        "season": set(SEASONS),
        "scenario": set(SCENARIOS),
        "drainage": {"good", "poor", "unknown"},
        "irrigation": {
            "available", "limited", "unknown"
        },
        "salinity": {"yes", "no", "unknown"},
        "goal": set(LABELS),
    }

    for key, options in valid.items():
        if selected[key] not in options:
            raise ValueError(
                f"Lựa chọn {key} không hợp lệ."
            )

    try:
        ph = (
            float(
                selected["soil_ph"].replace(",", ".")
            )
            if selected["soil_ph"]
            else None
        )
    except ValueError as exc:
        raise ValueError(
            "pH đất cần là số, ví dụ 6.5."
        ) from exc

    if ph is not None and not 0 <= ph <= 14:
        raise ValueError(
            "pH đất phải nằm trong khoảng 0–14."
        )

    selected["calendar"] = (
        "yes"
        if selected["calendar"] == "yes"
        else ""
    )

    params = {
        "season": selected["season"],
        "drainage": selected["drainage"],
        "irrigation": selected["irrigation"],
        "salinity": selected["salinity"],
        "goal": selected["goal"],
        "soil_ph": ph,
        "crop_calendar_confirmed": (
            selected["calendar"] == "yes"
        ),
    }

    return selected, params


# ======================================
# 2. TRANG WEB CHÍNH
# ======================================

@app.route("/", methods=["GET", "POST"])
def home():

    selected = dict(DEFAULTS)
    result = None
    rows = []
    error = None

    try:
        source = (
            request.form
            if request.method == "POST"
            else request.args
        )

        # Preserve entered values when validation fails so the form can be corrected.
        selected = {
            key: str(source.get(key, default)).strip()
            for key, default in DEFAULTS.items()
        }

        selected, params = parse_inputs(source)

        # Gọi Decision Engine của m
        result = evaluate_rotation(
            scenario=selected["scenario"],
            **params,
        )

        # So sánh hai kịch bản NASA
        comparison = compare_scenarios(**params)

        for key, item in comparison.items():
            rows.append({
                "scenario": SCENARIOS[key],
                "rain": item["climate"]["rain_mm"],
                "rice": item["options"][0],
                "sesame": item["options"][1],
            })

    except (
        ValueError,
        KeyError,
        FileNotFoundError,
        TypeError,
    ) as exc:
        error = str(exc)

    return render_template(
        "index.html",
        selected=selected,
        result=result,
        rows=rows,
        error=error,
        seasons=SEASONS,
        scenarios=SCENARIOS,
        goals=LABELS,
        statuses=STATUS,
    )


# ======================================
# 3. XUẤT BÁO CÁO JSON
# ======================================

@app.get("/report.json")
def report():

    try:
        selected, params = parse_inputs(
            request.args
        )

        result = evaluate_rotation(
            scenario=selected["scenario"],
            **params,
        )

    except (
        ValueError,
        KeyError,
        FileNotFoundError,
        TypeError,
    ) as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    content = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )

    return Response(
        content,
        mimetype="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                "filename=RiceShift-report.json"
            )
        },
    )


# ======================================
# 4. KIỂM TRA WEB ĐANG HOẠT ĐỘNG
# ======================================

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "RiceShift",
    })


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )


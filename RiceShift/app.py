
"""RiceShift - Streamlit Web Demo."""

import streamlit as st

from services.scoring_engine import (
    evaluate_rotation,
    compare_scenarios,
    LABELS,
)


st.set_page_config(
    page_title="RiceShift | NASA Space Apps",
    page_icon="🌾",
    layout="wide",
)


SEASON_LABELS = {
    "Dong_Xuan": "Đông Xuân",
    "He_Thu": "Hè Thu",
    "Thu_Dong": "Thu Đông",
}

SCENARIO_LABELS = {
    "normal": "Mùa điển hình (P50)",
    "low_rainfall": "Mùa ít mưa (P25)",
}

STATUS_LABELS = {
    "review": "Có thể khảo sát thêm",
    "needs_info": "Cần hỏi thêm",
    "blocked": "Tạm loại khỏi sàng lọc",
}


def format_score(value):
    if value is None:
        return "Chưa tính"
    return f"{value:.1f}/100"


# ==========================================
# 1. TIEU DE
# ==========================================

st.title("🌾 RiceShift")
st.subheader("Cùng xem phương án luân canh phù hợp")

st.caption(
    "Mission Impastable | NASA Space Apps Challenge 2026"
)

st.info(
    "Đây là hệ thống hỗ trợ đánh giá sơ bộ, "
    "không thay thế tư vấn nông học."
)


# ==========================================
# 2. NHAP THONG TIN
# ==========================================

with st.sidebar:

    st.header("1. Điều kiện ruộng")

    season = st.selectbox(
        "Bác đang cân nhắc vụ nào?",
        list(SEASON_LABELS),
        index=1,
        format_func=SEASON_LABELS.get,
    )

    scenario = st.selectbox(
        "Kịch bản khí hậu lịch sử",
        list(SCENARIO_LABELS),
        index=1,
        format_func=SCENARIO_LABELS.get,
    )

    drainage = st.radio(
        "Sau mưa lớn, ruộng thoát nước thế nào?",
        ["good", "poor", "unknown"],
        format_func={
            "good": "Thoát nhanh",
            "poor": "Hay đọng nước",
            "unknown": "Chưa rõ",
        }.get,
    )

    irrigation = st.radio(
        "Có chủ động nguồn nước tưới không?",
        ["limited", "available", "unknown"],
        format_func={
            "limited": "Khó chủ động",
            "available": "Có thể chủ động",
            "unknown": "Chưa rõ",
        }.get,
    )

    salinity = st.radio(
        "Đã ghi nhận độ mặn bất thường chưa?",
        ["unknown", "no", "yes"],
        format_func={
            "unknown": "Chưa rõ",
            "no": "Chưa ghi nhận",
            "yes": "Có ghi nhận",
        }.get,
    )

    ph_text = st.text_input(
        "pH đất (nếu có kết quả đo)",
        placeholder="Ví dụ: 6.5",
    )

    goal = st.selectbox(
        "Điều gì quan trọng nhất?",
        list(LABELS),
        format_func=LABELS.get,
    )

    calendar = st.checkbox(
        "Đã kiểm tra lịch gieo trồng và giống "
        "tại địa phương",
        value=False,
    )


# ==========================================
# 3. GOI DECISION ENGINE
# ==========================================

try:

    if ph_text.strip():
        soil_ph = float(
            ph_text.replace(",", ".")
        )
    else:
        soil_ph = None

    params = {
        "season": season,
        "drainage": drainage,
        "irrigation": irrigation,
        "goal": goal,
        "salinity": salinity,
        "soil_ph": soil_ph,
        "crop_calendar_confirmed": calendar,
    }

    result = evaluate_rotation(
        scenario=scenario,
        **params,
    )

except (
    ValueError,
    FileNotFoundError,
    KeyError,
) as exc:

    st.error(
        f"Chưa thể phân tích: {exc}"
    )

    st.stop()


# ==========================================
# 4. HIEN THI NASA DATA
# ==========================================

climate = result["climate"]

st.header("2. Dữ liệu khí hậu NASA")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Tổng mưa trong mùa",
    f"{climate['rain_mm']:.1f} mm",
    (
        f"{climate['rain_change_pct']:+.1f}% "
        "so với mùa điển hình"
    ),
)

c2.metric(
    "Nhiệt độ trung bình",
    f"{climate['avg_temp_c']} °C",
)

c3.metric(
    "Số ngày trên 35°C",
    f"{climate['hot_days']}",
)

c4.metric(
    "Năm lịch sử tham chiếu",
    f"{climate['analog_year']}",
)

st.info(
    "Các kịch bản P50/P25 được chọn từ những mùa "
    "lịch sử. Đây không phải dự báo thời tiết "
    "hay số đo trực tiếp tại ruộng."
)

st.caption(
    f"{climate['location']} | "
    f"Quan trắc đến {climate['observed_through']}"
)


# ==========================================
# 5. SO SANH HAI PHUONG AN
# ==========================================

st.header("3. So sánh chiến lược luân canh")

col1, col2 = st.columns(2)

for col, option in zip(
    (col1, col2),
    result["options"],
):

    with col:

        with st.container(border=True):

            st.subheader(option["name"])

            st.write(
                "**Trạng thái:**",
                STATUS_LABELS[option["status"]],
            )

            st.metric(
                "Điểm ưu tiên thử nghiệm",
                format_score(option["score"]),
            )

            for reason in option["reasons"]:
                st.success(reason)

            for warning in option["warnings"]:
                st.warning(warning)

            with st.expander(
                "Xem cách tính điểm và nguồn"
            ):

                st.write(
                    "Mỗi tiêu chí có mức 0–2. "
                    "Đây không phải điểm chất lượng "
                    "canh tác thực tế."
                )

                st.json(option["components"])

                for source in option["sources"]:
                    st.write(source)


# ==========================================
# 6. GIAI THICH KET QUA
# ==========================================

st.header("4. Kết luận hỗ trợ")

st.write(result["summary"])

if result["missing_info"]:

    st.warning(
        "Cần xác minh thêm: "
        + "; ".join(result["missing_info"])
    )

with st.expander(
    "Phương pháp đánh giá và giới hạn"
):

    st.write(result["method"])

    st.write(
        "Trọng số:",
        result["weights"],
    )

    for note in result["notes"]:
        st.write("•", note)


# ==========================================
# 7. MO PHONG HAI KICH BAN
# ==========================================

st.header(
    "5. Điều gì thay đổi nếu lượng mưa khác đi?"
)

comparison = compare_scenarios(**params)

rows = []

for key, output in comparison.items():

    for option in output["options"]:

        rows.append({
            "Kịch bản": SCENARIO_LABELS[key],
            "Phương án": option["name"],
            "Mưa (mm/vụ)": (
                output["climate"]["rain_mm"]
            ),
            "Điểm ưu tiên thử nghiệm": (
                option["score"]
            ),
            "Trạng thái": (
                STATUS_LABELS[option["status"]]
            ),
        })

st.dataframe(
    rows,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Điểm thể hiện mức ưu tiên theo quy tắc "
    "thử nghiệm của đội, không phải dự báo "
    "năng suất hay mức nước tiết kiệm."
)


# ==========================================
# 8. NGUON VA GIOI HAN
# ==========================================

st.divider()

st.caption(
    "Dữ liệu: NASA POWER. "
    "Căn cứ tham khảo: FAO, NC State Extension, "
    "Agronomy 2024. "
    "Không sử dụng kết quả để quyết định "
    "canh tác thực tế nếu chưa kiểm định."
)

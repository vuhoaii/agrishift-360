
from services.scoring_engine import (
    evaluate_rotation,
    compare_scenarios,
)


base = {
    "season": "He_Thu",
    "drainage": "good",
    "irrigation": "limited",
    "salinity": "no",
}

normal = evaluate_rotation(
    scenario="normal",
    **base,
)

dry = evaluate_rotation(
    scenario="low_rainfall",
    **base,
)

# 1. Kịch bản ít mưa thực sự có mưa thấp hơn.
assert (
    dry["climate"]["rain_mm"]
    < normal["climate"]["rain_mm"]
)

# 2. Độ lệch lượng mưa phải âm.
assert dry["climate"]["rain_change_pct"] < 0

# 3. Luôn có 2 phương án.
assert len(normal["options"]) == 2

# 4. Kết quả thay đổi theo kịch bản.
assert normal["leading_option_id"] == "rice_rice"
assert dry["leading_option_id"] == "rice_sesame"

# 5. Thoát nước kém phải cảnh báo mạnh cho mè.
poor = evaluate_rotation(
    scenario="normal",
    drainage="poor",
    irrigation="available",
    salinity="no",
)

assert poor["options"][1]["status"] == "blocked"
assert poor["options"][1]["score"] is None

# 6. Thiếu thông tin không tự kết luận.
unknown = evaluate_rotation(
    scenario="normal",
    drainage="unknown",
    irrigation="unknown",
)

assert unknown["leading_option_id"] is None
assert unknown["missing_info"]

# 7. Phát hiện độ mặn.
salt = evaluate_rotation(
    scenario="normal",
    drainage="good",
    irrigation="available",
    salinity="yes",
)

assert salt["options"][1]["status"] == "blocked"

# 8. Thay đổi ưu tiên có thể thay đổi thứ tự.
water_goal = evaluate_rotation(
    scenario="normal",
    drainage="good",
    irrigation="available",
    salinity="no",
    goal="save_water",
)

soil_goal = evaluate_rotation(
    scenario="normal",
    drainage="good",
    irrigation="available",
    salinity="no",
    goal="protect_soil",
)

assert water_goal["leading_option_id"] == "rice_rice"
assert soil_goal["leading_option_id"] == "rice_sesame"

# 9. Kiểm tra hàm so sánh kịch bản.
result = compare_scenarios(**base)
assert len(result) == 2

print("PASS: Decision Engine kiểm thử thành công!")

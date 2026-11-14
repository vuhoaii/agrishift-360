"""Complete-message translations for existing Decision Engine output.

This module formats display text only. It never alters the original result,
JSON report, scores, weights, thresholds or internal identifiers.
"""
import re

MESSAGES = {
    "Hai kich ban la cac mua lich su, khong phai du bao.": [
        "Hai kịch bản là các mùa trong lịch sử, không phải dự báo.",
        "Both scenarios represent historical seasons, not forecasts."
    ],
    "Tong mua ca vu khong du de ket luan nguon nuoc hoac nguy co ngap tai ruong.": [
        "Tổng mưa cả vụ chưa đủ để kết luận nguồn nước hoặc nguy cơ ngập tại khu đất.",
        "Seasonal rainfall alone cannot establish water availability or flooding risk on your land."
    ],
    "Xac minh lich trong va giong tai dia phuong.": [
        "Xác minh lịch trồng và giống tại địa phương.",
        "Confirm the local planting calendar and suitable varieties."
    ],
    "Lich mua vu trong pipeline la gia dinh thi diem.": [
        "Lịch mùa vụ đang dùng là giả định cho giai đoạn thí điểm.",
        "The current seasonal calendar is a pilot assumption."
    ],
    "Kiem tra do man dat va nuoc.": [
        "Kiểm tra độ mặn của đất và nước.",
        "Check soil and water salinity."
    ],
    "Bo sung pH dat neu co ket qua do.": [
        "Bổ sung pH đất nếu có kết quả đo.",
        "Provide soil pH if a measurement is available."
    ],
    "Kha nang chu dong tuoi cua ruong?": [
        "Khu đất có thể chủ động nước tưới ở mức nào?",
        "How reliably can you supply irrigation water?"
    ],
    "Ruong co dong nuoc sau mua lon khong?": [
        "Khu đất có đọng nước sau mưa lớn không?",
        "Does water remain on your land after heavy rain?"
    ],
    "Me nhay cam voi ngap ung. Can kiem tra hoac cai thien kha nang thoat nuoc.": [
        "Mè nhạy cảm với ngập úng. Cần kiểm tra hoặc cải thiện khả năng thoát nước.",
        "Sesame is sensitive to waterlogging. Check or improve drainage."
    ],
    "Chua ro kha nang thoat nuoc. Chua the xep hang phuong an me.": [
        "Chưa rõ khả năng thoát nước. Chưa thể xếp hạng phương án mè.",
        "Drainage is unknown. The sesame option cannot yet be ranked."
    ],
    "Thoat nuoc tot la dieu kien thuan loi de can nhac trong me.": [
        "Thoát nước tốt là điều kiện thuận lợi để cân nhắc trồng mè.",
        "Good drainage is a favourable condition for considering sesame."
    ],
    "Da ghi nhan man. Me nhay voi muoi; can do va tu van tai ruong.": [
        "Đã ghi nhận mặn. Mè nhạy với muối; cần đo và tư vấn tại khu đất.",
        "Salinity has been reported. Sesame is sensitive to salt; field measurements and local advice are needed."
    ],
    "Chua co thong tin do man.": [
        "Chưa có thông tin độ mặn.",
        "Salinity information is not yet available."
    ],
    "pH ngoai khoang tham khao 5.5-7.0 cua NC State. Can kiem tra giong va dat.": [
        "pH ngoài khoảng tham khảo 5.5–7.0 của NC State. Cần kiểm tra giống và đất.",
        "Soil pH is outside the NC State reference range of 5.5–7.0. Check the variety and soil conditions."
    ],
    "Thay doi loai cay giup da dang hoa chuoi luan canh. Loi ich voi dat can duoc kiem chung.": [
        "Thay đổi loại cây giúp đa dạng hóa chuỗi luân canh. Lợi ích với đất cần được kiểm chứng.",
        "Changing crop types diversifies the rotation. Soil benefits still need to be verified."
    ],
    "Tiep tuc phuong thuc trong lua quen thuoc, it thay doi ky thuat.": [
        "Tiếp tục phương thức trồng lúa quen thuộc, ít thay đổi kỹ thuật.",
        "Continues familiar rice-growing practices with fewer changes in technique."
    ],
    "Nguon tuoi han che co the gay kho khan cho lua nuoc.": [
        "Nguồn tưới hạn chế có thể gây khó khăn cho lúa nước.",
        "Limited irrigation may make paddy rice production difficult."
    ],
    "Do man cung co the anh huong lua. Can danh gia theo giong.": [
        "Độ mặn cũng có thể ảnh hưởng lúa. Cần đánh giá theo giống.",
        "Salinity can also affect rice. Assess the risk for the specific variety."
    ],
    "Chua xac minh me co phu hop voi dung vu dang chon khong.": [
        "Chưa xác minh mè có phù hợp với mùa vụ đang chọn hay không.",
        "Sesame's suitability for the selected season has not yet been confirmed."
    ],
    "Chua du co so de xac dinh phuong an dan dau mot cach co the so sanh.": [
        "Chưa đủ cơ sở để xác định phương án dẫn đầu trên cùng cơ sở so sánh.",
        "There is not enough information to identify a leading option on a comparable basis."
    ],
    "Diem 0-100 = 50 x tong(trong so x muc 0/1/2). Ba tieu chi: ap luc nuoc, da dang cay trong, muc thay doi canh tac. Day la he thong uu tien THU NGHIEM, khong phai do phu hop nong hoc, du bao nang suat hoac xac suat thanh cong.": [
        "Điểm 0–100 = 50 × tổng (trọng số × mức 0/1/2). Ba tiêu chí: áp lực nước, đa dạng cây trồng, mức thay đổi canh tác. Đây là hệ thống ưu tiên THỬ NGHIỆM, không phải độ phù hợp nông học, dự báo năng suất hoặc xác suất thành công.",
        "Score 0–100 = 50 × sum (weight × level 0/1/2). Three criteria: water pressure, crop diversity and changes in farming practice. This is an EXPERIMENTAL priority system; it does not measure agronomic suitability or predict yield or probability of success."
    ],
    "Kich ban khong hop le hoac thieu normal.": [
        "Kịch bản không hợp lệ hoặc thiếu mốc mùa điển hình.",
        "The scenario is invalid or the typical-season baseline is missing."
    ],
    "Du lieu luong mua thieu hoac khong hop le.": [
        "Dữ liệu lượng mưa thiếu hoặc không hợp lệ.",
        "Rainfall data is missing or invalid."
    ],
    "Luong mua khong the am.": [
        "Lượng mưa không thể âm.",
        "Rainfall cannot be negative."
    ],
    "pH phai nam trong khoang 0-14.": [
        "pH phải nằm trong khoảng 0–14.",
        "pH must be between 0 and 14."
    ],
    "pH đất cần là số, ví dụ 6.5.": [
        "pH đất cần là số, ví dụ 6.5.",
        "Soil pH must be a number, for example 6.5."
    ],
    "pH đất phải nằm trong khoảng 0–14.": [
        "pH đất phải nằm trong khoảng 0–14.",
        "Soil pH must be between 0 and 14."
    ],
    "Khu vực thí điểm An Giang (cần xác nhận địa danh)": [
        "Khu vực thí điểm An Giang (cần xác nhận địa danh)",
        "An Giang pilot area (place name to be confirmed)"
    ],
    "Địa điểm thí điểm": [
        "Địa điểm thí điểm",
        "Pilot location"
    ],
    "Lúa → Lúa": [
        "Lúa → Lúa",
        "Rice → Rice"
    ],
    "Lúa → Mè": [
        "Lúa → Mè",
        "Rice → Sesame"
    ]
}

MESSAGES.update({
    'Historical climate payload is invalid.': (
        'Tệp dữ liệu khí hậu lịch sử không hợp lệ.',
        'Historical climate payload is invalid.',
    ),
    'The crop calendar confirmation must be true or false.': (
        'Xác nhận lịch mùa vụ phải là giá trị đúng hoặc sai.',
        'The crop calendar confirmation must be true or false.',
    ),
    'NASA POWER is gridded historical data, not a measurement from the field.': (
        'NASA POWER là dữ liệu lịch sử dạng lưới, không phải số đo tại ruộng.',
        'NASA POWER is gridded historical data, not a measurement from the field.',
    ),
    'Rainfall and dry-day frequency share a bounded experimental water component; they are not statistically independent.': (
        'Lượng mưa và tần suất ngày khô cùng đóng góp vào tiêu chí nước thử nghiệm có giới hạn; hai chỉ báo không độc lập về thống kê.',
        'Rainfall and dry-day frequency share a bounded experimental water component; they are not statistically independent.',
    ),
    'Temperature and hot days are assessed separately from rainfall. Seasonal summaries cannot establish exposure during flowering.': (
        'Nhiệt độ và ngày nóng được xem xét riêng với lượng mưa. Tổng hợp theo vụ không xác định được mức phơi nhiễm lúc ra hoa.',
        'Temperature and hot days are assessed separately from rainfall. Seasonal summaries cannot establish exposure during flowering.',
    ),
    'Categorical drainage and salinity inputs require local verification; they are not universal crop exclusion thresholds.': (
        'Thông tin phân loại thoát nước và độ mặn cần được xác minh tại địa phương; đây không phải ngưỡng loại trừ cây trồng áp dụng chung.',
        'Categorical drainage and salinity inputs require local verification; they are not universal crop exclusion thresholds.',
    ),
    'Reported salinity needs measured soil and water conductivity and local variety advice before ranking either option.': (
        'Khi ghi nhận mặn, cần đo độ dẫn điện của đất và nước, đồng thời tư vấn về giống tại địa phương trước khi xếp hạng cả hai phương án.',
        'Reported salinity needs measured soil and water conductivity and local variety advice before ranking either option.',
    ),
    'Poor drainage requires field verification or improvement before sesame can be ranked.': (
        'Thoát nước kém cần được kiểm tra tại ruộng hoặc cải thiện trước khi xếp hạng phương án mè.',
        'Poor drainage requires field verification or improvement before sesame can be ranked.',
    ),
    'Incomplete or invalid historical indicators prevent ranking; missing values are not assumed safe.': (
        'Chỉ báo lịch sử thiếu hoặc không hợp lệ khiến hệ thống chưa thể xếp hạng; giá trị thiếu không được coi là an toàn.',
        'Incomplete or invalid historical indicators prevent ranking; missing values are not assumed safe.',
    ),
    'Sesame tolerates drought relatively well but still needs moisture for germination and establishment.': (
        'Mè tương đối chịu khô nhưng vẫn cần đủ ẩm để nảy mầm và hình thành cây con.',
        'Sesame tolerates drought relatively well but still needs moisture for germination and establishment.',
    ),
    'Rice flowering is heat-sensitive. Check whether hot days overlapped flowering; this count does not establish sterility or yield loss.': (
        'Lúa nhạy cảm với nóng khi ra hoa. Cần kiểm tra ngày nóng có trùng giai đoạn này không; số ngày nóng không chứng minh hiện tượng bất dục hoặc mất năng suất.',
        'Rice flowering is heat-sensitive. Check whether hot days overlapped flowering; this count does not establish sterility or yield loss.',
    ),
    'The 35 C hot-day indicator is not a validated sesame injury threshold; no crop-specific heat penalty is assigned.': (
        'Chỉ báo ngày nóng trên 35°C chưa phải ngưỡng gây hại đã kiểm chứng cho mè; không áp dụng điểm phạt nhiệt riêng cho cây này.',
        'The 35 C hot-day indicator is not a validated sesame injury threshold; no crop-specific heat penalty is assigned.',
    ),
    'Decision Engine v2: score = 50 x sum(weight x component 0-2). Water = B - E x C x (0.5 x D + 0.5 x F), where D = max(0, 1 - rain/P50 analog rain), F = dry days/season days, B = 2 with available irrigation or 1 with limited irrigation, E = 0.25 or 1 respectively, and C = 1 for rice or 0.5 for sesame. All coefficients and weights are EXPERIMENTAL. Temperature and hot days inform separate verification warnings, without numerical penalties. This is not validated suitability, a yield forecast or a probability of success.': (
        'Decision Engine v2: điểm = 50 × tổng (trọng số × thành phần 0–2). Nước = B − E × C × (0,5 × D + 0,5 × F), với D = max(0, 1 − mưa/mưa mùa tham chiếu P50), F = số ngày khô/số ngày trong vụ; B = 2 khi chủ động tưới hoặc 1 khi tưới hạn chế; E tương ứng = 0,25 hoặc 1; C = 1 cho lúa hoặc 0,5 cho mè. Tất cả hệ số và trọng số đều là giả định THỬ NGHIỆM. Nhiệt độ và ngày nóng được dùng để cảnh báo xác minh riêng, không trừ điểm. Đây không phải độ phù hợp đã kiểm chứng, dự báo năng suất hoặc xác suất thành công.',
        'Decision Engine v2: score = 50 x sum(weight x component 0-2). Water = B - E x C x (0.5 x D + 0.5 x F), where D = max(0, 1 - rain/P50 analog rain), F = dry days/season days, B = 2 with available irrigation or 1 with limited irrigation, E = 0.25 or 1 respectively, and C = 1 for rice or 0.5 for sesame. All coefficients and weights are EXPERIMENTAL. Temperature and hot days inform separate verification warnings, without numerical penalties. This is not validated suitability, a yield forecast or a probability of success.',
    ),
})

FIELD_NAMES = {
    "season": ("mùa vụ", "season"),
    "scenario": ("bối cảnh khí hậu", "climate scenario"),
    "drainage": ("thoát nước", "drainage"),
    "irrigation": ("nguồn tưới", "irrigation"),
    "salinity": ("độ mặn", "salinity"),
    "goal": ("mục tiêu ưu tiên", "priority"),
}

def _dynamic_message(message):

    match = re.fullmatch(
        r"Historical mean temperature: (-?\d+\.\d{2}) C; difference from P50: ([+-]\d+\.\d{2}) C\. This is not flowering-stage temperature\.", message)
    if match:
        return (
            f"Nhiệt độ trung bình lịch sử: {match[1]}°C; chênh lệch với P50: {match[2]}°C. Đây không phải nhiệt độ lúc ra hoa.",
            message)
    match = re.fullmatch(
        r"Historical days with Tmax above 35 C: (\d+)\. The timing and duration of heat exposure are unknown\.", message)
    if match:
        return (
            f"Số ngày lịch sử có Tmax trên 35°C: {match[1]}. Chưa biết thời điểm và thời lượng phơi nhiễm nhiệt.",
            message)
    match = re.fullmatch(
        r"Historical dry days below 1 mm: (\d+) of (\d+)\. This is a seasonal count, not a consecutive dry spell or a diagnosis of crop drought\.", message)
    if match:
        return (
            f"Số ngày khô lịch sử có mưa dưới 1 mm: {match[1]}/{match[2]} ngày. Đây là tổng số ngày trong vụ, không phải đợt khô liên tiếp hoặc chẩn đoán hạn cho cây.",
            message)
    match = re.fullmatch(
        r"Historical indicator is missing or invalid: (analog_year|avg_temp_C|hot_days_over_35C|dry_days) \((selected|baseline)\)\.", message)
    if match:
        fields = {"analog_year": "năm mùa vụ tham chiếu", "avg_temp_C": "nhiệt độ trung bình",
                  "hot_days_over_35C": "số ngày nóng", "dry_days": "số ngày khô"}
        role = "mùa được chọn" if match[2] == "selected" else "mùa điển hình"
        return f"Chỉ báo lịch sử thiếu hoặc không hợp lệ: {fields[match[1]]} ({role}).", message

    # Anchored complete templates preserve the exact engine statement.
    match = re.fullmatch(
        r"Mua lich su nay co tong mua thap hon (\d+\.\d)% so voi moc dien hinh\. Day khong phai chan doan han\.",
        message,
    )
    if match:
        value = match[1]
        return (
            f"Mùa lịch sử này có tổng mưa thấp hơn {value}% so với mốc điển hình. Đây không phải chẩn đoán hạn.",
            f"This historical season received {value}% less total rainfall than the typical baseline. This is not a drought diagnosis.",
        )
    match = re.fullmatch(
        r"Theo thang diem uu tien THU NGHIEM: (Lúa → Lúa|Lúa → Mè) dang dung truoc trong hai phuong an du thong tin de so sanh\.",
        message,
    )
    if match:
        crop = MESSAGES[match[1]]
        return (
            f"Theo thang điểm ưu tiên THỬ NGHIỆM: {crop[0]} đang xếp trước trong hai phương án đủ thông tin để so sánh.",
            f"On the EXPERIMENTAL priority scale, {crop[1]} currently ranks ahead among the two options with enough information to compare.",
        )
    match = re.fullmatch(r"Lựa chọn (season|scenario|drainage|irrigation|salinity|goal) không hợp lệ\.", message)
    if match:
        field = FIELD_NAMES[match[1]]
        return f"Lựa chọn {field[0]} không hợp lệ.", f"The {field[1]} selection is invalid."
    match = re.fullmatch(r"(season|scenario|drainage|irrigation|salinity|goal) khong hop le: ([^\r\n]*)", message)
    if match:
        field = FIELD_NAMES[match[1]]
        return f"Giá trị {field[0]} không hợp lệ: {match[2]}", f"Invalid {field[1]} value: {match[2]}"
    match = re.fullmatch(r"Khong co du lieu mua vu: ([^\r\n]+)", message)
    if match:
        return f"Không có dữ liệu cho mùa vụ: {match[1]}", f"No data is available for this season: {match[1]}"
    match = re.fullmatch(r"Thieu du lieu NASA: ([^\r\n]+)", message)
    if match:
        return f"Thiếu dữ liệu NASA: {match[1]}", f"NASA data is missing: {match[1]}"
    return None

def is_message_translated(message):
    return message in MESSAGES or _dynamic_message(message) is not None

def translate_message(message, lang="vi"):
    position = 1 if lang == "en" else 0
    translations = MESSAGES.get(message) or _dynamic_message(message)
    if translations:
        return translations[position]
    # New/unrecognized backend text remains visible and is honestly identified.
    label = "Untranslated source message" if position else "Thông báo gốc chưa được dịch"
    return f"[{label}] {message}"

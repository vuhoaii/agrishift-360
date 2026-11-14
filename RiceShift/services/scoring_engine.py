
"""RiceShift v1.0 - Decision Support Engine.

Du lieu NASA duoc doc tu JSON do Nguoi 1 tao ra.
Diem 0-100 la thang diem UU TIEN THU NGHIEM,
khong phai diem phu hop nong hoc da duoc kiem chung.
"""

from __future__ import annotations

import json
from pathlib import Path


# ==========================================
# 1. CAU HINH VA NGUON KHOA HOC
# ==========================================

PAYLOAD_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/processed/climate_payload_latest.json"
)

SOURCES = {
    "nasa": "https://power.larc.nasa.gov/",
    "rice_water": "https://www.fao.org/4/S2022E/s2022e08.htm",
    "sesame": (
        "https://content.ces.ncsu.edu/"
        "sesame-production-fact-sheet"
    ),
    "rotation": "https://doi.org/10.3390/agronomy14061185",
}

# Trong so do nhom de xuat, khong phai
# he so khoa hoc da duoc hieu chuan.
WEIGHTS = {
    "save_water": {
        "water": 0.70,
        "diversity": 0.10,
        "continuity": 0.20,
    },
    "protect_soil": {
        "water": 0.25,
        "diversity": 0.60,
        "continuity": 0.15,
    },
    "keep_practice": {
        "water": 0.25,
        "diversity": 0.10,
        "continuity": 0.65,
    },
}

LABELS = {
    "save_water": "Ưu tiên giảm áp lực nước",
    "protect_soil": "Ưu tiên đa dạng luân canh",
    "keep_practice": "Ưu tiên ít thay đổi cách canh tác",
}


# ==========================================
# 2. DOC DU LIEU CUA BAN 1
# ==========================================

def load_payload():
    """Doc JSON da xu ly, khong goi lai NASA API."""

    if not PAYLOAD_PATH.is_file():
        raise FileNotFoundError(
            f"Thieu du lieu NASA: {PAYLOAD_PATH}"
        )

    return json.loads(
        PAYLOAD_PATH.read_text(encoding="utf-8")
    )


# ==========================================
# 3. PHAN TICH KHI HAU
# ==========================================

def analyze_climate(payload, season, scenario):

    scenarios = payload.get("scenarios", {})

    if (
        scenario not in scenarios
        or "normal" not in scenarios
    ):
        raise ValueError(
            "Kich ban khong hop le hoac thieu normal."
        )

    current = scenarios[scenario].get(season)
    baseline = scenarios["normal"].get(season)

    if current is None or baseline is None:
        raise ValueError(
            f"Khong co du lieu mua vu: {season}"
        )

    rain = current.get("total_rain_mm")
    ref = baseline.get("total_rain_mm")

    if rain is None or ref is None or ref <= 0:
        raise ValueError(
            "Du lieu luong mua thieu hoac khong hop le."
        )

    if rain < 0:
        raise ValueError("Luong mua khong the am.")

    change_pct = round(
        100 * (float(rain) - float(ref)) / float(ref),
        1,
    )

    return {
        "season": season,
        "scenario": scenario,
        "analog_year": current.get("analog_year"),
        "rain_mm": round(float(rain), 2),
        "normal_rain_mm": round(float(ref), 2),
        "rain_change_pct": change_pct,
        "avg_temp_c": current.get("avg_temp_C"),
        "hot_days": current.get("hot_days_over_35C"),
        "dry_days": current.get("dry_days"),
        "observed_through": payload.get(
            "location", {}
        ).get("observed_through"),
        "location": payload.get(
            "location", {}
        ).get("name", "Địa điểm thí điểm"),
    }


# ==========================================
# 4. THANG DANH GIA AP LUC NUOC
# ==========================================

def _water_score(crop, irrigation, rain_change_pct):
    """
    Thang 0, 1, 2 (thu nghiem).

    Khong tinh nhu cau tuoi thuc te.
    Khong suy ra nang suat hoac xac suat han han.
    """

    if irrigation == "unknown":
        return None

    # Chu dong tuoi: chua thay ap luc truc tiep
    # tu yeu to kha nang chu dong nguon tuoi.
    if irrigation == "available":
        return 2

    # Khong chu dong tuoi.
    less_rain = rain_change_pct < 0

    if crop == "rice":
        return 0 if less_rain else 1

    # Me tuong doi chiu kho nhung van can am
    # de nay mam va sinh truong.
    return 1


# ==========================================
# 5. TINH DIEM DA TIEU CHI
# ==========================================

def _weighted_score(components, goal):

    weights = WEIGHTS[goal]

    # Khong tinh diem neu thieu tieu chi.
    if any(
        components.get(key) is None
        for key in weights
    ):
        return None

    # Moi tieu chi co diem 0, 1, 2.
    # Chuan hoa tong diem ve thang 100.
    total = sum(
        components[key] * weight
        for key, weight in weights.items()
    )

    return round(total * 50, 1)


# ==========================================
# 6. DECISION ENGINE CHINH
# ==========================================

def evaluate_rotation(
    season="He_Thu",
    scenario="low_rainfall",
    drainage="unknown",
    irrigation="unknown",
    goal="save_water",
    salinity="unknown",
    soil_ph=None,
    crop_calendar_confirmed=False,
    payload=None,
):
    """
    Danh gia 2 phuong an:
    - Lua -> Lua
    - Lua -> Me

    Ket qua chi de sang loc va so sanh so bo.
    """

    # --------------------------------------
    # A. Kiem tra input
    # --------------------------------------

    choices = {
        "drainage": (
            drainage, {"good", "poor", "unknown"}
        ),
        "irrigation": (
            irrigation,
            {"available", "limited", "unknown"},
        ),
        "salinity": (
            salinity, {"no", "yes", "unknown"}
        ),
        "goal": (
            goal, set(WEIGHTS)
        ),
    }

    for name, (value, allowed) in choices.items():
        if value not in allowed:
            raise ValueError(
                f"{name} khong hop le: {value}"
            )

    if soil_ph is not None:
        if not 0 <= float(soil_ph) <= 14:
            raise ValueError(
                "pH phai nam trong khoang 0-14."
            )

    # --------------------------------------
    # B. Lay du lieu khi hau NASA
    # --------------------------------------

    climate = analyze_climate(
        payload if payload is not None else load_payload(),
        season,
        scenario,
    )

    # --------------------------------------
    # C. Phat hien thong tin con thieu
    # --------------------------------------

    missing = []

    notes = [
        "Hai kich ban la cac mua lich su, khong phai du bao.",
        "Tong mua ca vu khong du de ket luan "
        "nguon nuoc hoac nguy co ngap tai ruong.",
    ]

    if not crop_calendar_confirmed:
        missing.append(
            "Xac minh lich trong va giong tai dia phuong."
        )
        notes.append(
            "Lich mua vu trong pipeline la gia dinh thi diem."
        )

    if salinity == "unknown":
        missing.append(
            "Kiem tra do man dat va nuoc."
        )

    if soil_ph is None:
        missing.append(
            "Bo sung pH dat neu co ket qua do."
        )

    if irrigation == "unknown":
        missing.append(
            "Kha nang chu dong tuoi cua ruong?"
        )

    if drainage == "unknown":
        missing.append(
            "Ruong co dong nuoc sau mua lon khong?"
        )

    # --------------------------------------
    # D. Danh gia tung phuong an
    # --------------------------------------

    options = []

    crop_options = [
        ("rice", "rice_rice", "Lúa → Lúa"),
        ("sesame", "rice_sesame", "Lúa → Mè"),
    ]

    for crop, option_id, title in crop_options:

        reasons = []
        warnings = []
        status = "review"

        # Ba tieu chi cho diem uu tien.
        components = {
            "water": _water_score(
                crop,
                irrigation,
                climate["rain_change_pct"],
            ),
            "diversity": (
                0 if crop == "rice" else 2
            ),
            "continuity": (
                2 if crop == "rice" else 0
            ),
        }

        # ----------------------------------
        # D1. Phuong an Lua -> Me
        # ----------------------------------

        if crop == "sesame":

            if drainage == "poor":
                status = "blocked"

                warnings.append(
                    "Me nhay cam voi ngap ung. "
                    "Can kiem tra hoac cai thien "
                    "kha nang thoat nuoc."
                )

            elif drainage == "unknown":
                status = "needs_info"

                warnings.append(
                    "Chua ro kha nang thoat nuoc. "
                    "Chua the xep hang phuong an me."
                )

            else:
                reasons.append(
                    "Thoat nuoc tot la dieu kien "
                    "thuan loi de can nhac trong me."
                )

            if salinity == "yes":
                status = "blocked"

                warnings.append(
                    "Da ghi nhan man. Me nhay voi "
                    "muoi; can do va tu van tai ruong."
                )

            elif salinity == "unknown":
                warnings.append(
                    "Chua co thong tin do man."
                )

            if soil_ph is not None:
                if not 5.5 <= float(soil_ph) <= 7.0:
                    warnings.append(
                        "pH ngoai khoang tham khao "
                        "5.5-7.0 cua NC State. "
                        "Can kiem tra giong va dat."
                    )

            reasons.append(
                "Thay doi loai cay giup da dang "
                "hoa chuoi luan canh. Loi ich "
                "voi dat can duoc kiem chung."
            )

        # ----------------------------------
        # D2. Phuong an Lua -> Lua
        # ----------------------------------

        else:

            reasons.append(
                "Tiep tuc phuong thuc trong lua "
                "quen thuoc, it thay doi ky thuat."
            )

            if irrigation == "limited":
                warnings.append(
                    "Nguon tuoi han che co the "
                    "gay kho khan cho lua nuoc."
                )

            if salinity == "yes":
                warnings.append(
                    "Do man cung co the anh huong "
                    "lua. Can danh gia theo giong."
                )

        # ----------------------------------
        # D3. Ket hop tin hieu NASA
        # ----------------------------------

        if climate["rain_change_pct"] < 0:

            warnings.append(
                "Mua lich su nay co tong mua "
                f"thap hon {abs(climate['rain_change_pct']):.1f}% "
                "so voi moc dien hinh. "
                "Day khong phai chan doan han."
            )

        # ----------------------------------
        # D4. Du lieu thieu va mua vu
        # ----------------------------------

        if irrigation == "unknown":
            if status != "blocked":
                status = "needs_info"

        if (
            crop == "sesame"
            and status != "blocked"
            and not crop_calendar_confirmed
        ):
            warnings.append(
                "Chua xac minh me co phu hop "
                "voi dung vu dang chon khong."
            )

        # ----------------------------------
        # D5. Tinh diem neu du dieu kien
        # ----------------------------------

        if status == "review":
            score = _weighted_score(
                components,
                goal,
            )
        else:
            score = None

        if crop == "rice":
            sources = [
                SOURCES["nasa"],
                SOURCES["rice_water"],
            ]
        else:
            sources = [
                SOURCES["nasa"],
                SOURCES["sesame"],
                SOURCES["rotation"],
            ]

        options.append({
            "id": option_id,
            "name": title,
            "status": status,
            "score": score,
            "components": components,
            "reasons": reasons,
            "warnings": warnings,
            "sources": sources,
        })

    # --------------------------------------
    # E. Xep thu tu cac phuong an
    # --------------------------------------

    ranked = sorted(
        [
            option
            for option in options
            if option["score"] is not None
        ],
        key=lambda x: (
            -x["score"],
            x["id"],
        ),
    )

    # Chi so sanh khi ca hai du dieu kien.
    winner = None

    if len(ranked) == 2:
        if ranked[0]["score"] > ranked[1]["score"]:
            winner = ranked[0]["id"]

    # --------------------------------------
    # F. Tao giai thich ket qua
    # --------------------------------------

    if winner:

        summary = (
            "Theo thang diem uu tien THU NGHIEM: "
            f"{ranked[0]['name']} dang dung truoc "
            "trong hai phuong an du thong tin "
            "de so sanh."
        )

    else:

        summary = (
            "Chua du co so de xac dinh phuong an "
            "dan dau mot cach co the so sanh."
        )

    # --------------------------------------
    # G. Tra ket qua cho Streamlit
    # --------------------------------------

    return {
        "climate": climate,
        "context": {
            "drainage": drainage,
            "irrigation": irrigation,
            "goal": goal,
            "salinity": salinity,
            "soil_ph": soil_ph,
            "crop_calendar_confirmed": (
                crop_calendar_confirmed
            ),
        },
        "weights": WEIGHTS[goal],
        "options": options,
        "ranked_ids": [
            option["id"] for option in ranked
        ],
        "leading_option_id": winner,
        "summary": summary,
        "missing_info": missing,
        "notes": notes,
        "method": (
            "Diem 0-100 = 50 x tong("
            "trong so x muc 0/1/2). "
            "Ba tieu chi: ap luc nuoc, da dang "
            "cay trong, muc thay doi canh tac. "
            "Day la he thong uu tien THU NGHIEM, "
            "khong phai do phu hop nong hoc, "
            "du bao nang suat hoac xac suat "
            "thanh cong."
        ),
    }


# ==========================================
# 7. SO SANH HAI KICH BAN NASA
# ==========================================

def compare_scenarios(**kwargs):

    kwargs.pop("scenario", None)

    results = {}

    for scenario in ("normal", "low_rainfall"):

        results[scenario] = evaluate_rotation(
            scenario=scenario,
            **kwargs,
        )

    return results


# ==========================================
# 8. TEST NHANH
# ==========================================

if __name__ == "__main__":

    from pprint import pprint

    result = evaluate_rotation(
        season="He_Thu",
        scenario="low_rainfall",
        drainage="good",
        irrigation="limited",
        goal="save_water",
        salinity="no",
        crop_calendar_confirmed=False,
    )

    pprint(result, sort_dicts=False)

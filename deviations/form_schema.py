"""Company form 2026-10-26: stable field groups, no source-company data."""

from django.core.exceptions import ValidationError

FORM_VERSION = 2
QUESTIONS = (
    ("who", "WHO — Ai phát hiện?"),
    ("when", "WHEN — Phát hiện khi nào?"),
    ("where", "WHERE — Xảy ra ở đâu?"),
    ("what", "WHAT — Điều gì xảy ra?"),
    ("which", "WHICH — Cái gì thay đổi?"),
    ("how", "HOW — Phát hiện bằng cách nào?"),
)
FACTORS = (
    ("measurement", "Đo lường"),
    ("people", "Con người"),
    ("method", "Phương pháp"),
    ("environment", "Môi trường"),
    ("machinery", "Máy móc"),
    ("equipment", "Thiết bị"),
)
FACTOR_STATES = [
    ("", "Chưa đánh giá"),
    ("RELATED", "Có liên quan"),
    ("EXCLUDED", "Đã loại trừ"),
    ("NA", "Không áp dụng"),
]
LIKELIHOOD = [
    (1, "Ít khi xảy ra"),
    (2, "Không chắc xảy ra"),
    (3, "Có thể xảy ra"),
    (4, "Có khả năng xảy ra"),
    (5, "Chắc chắn xảy ra"),
]
CONSEQUENCE = [
    (1, "Không đáng kể"),
    (2, "Thứ yếu"),
    (3, "Trung bình"),
    (4, "Nghiêm trọng"),
    (5, "Thảm khốc"),
]
REPORT_EXTRA = (
    "reported_at",
    "reporter_job_title",
    "discoverer_name",
    "discoverer_job_title",
    "what_changed",
    "detection_method",
    "gap_analysis",
    "special_comments",
    "department_reviewer",
    "control_reviewer",
)
ANALYSIS_EXTRA = (
    "investigation_5w1h",
    "investigation_expected",
    "investigation_gap",
    "affected_steps",
    "has_history",
    "history_details",
    "event_sequence",
    "cause_factors",
    "five_whys",
    "causal_factors",
    "likelihood",
    "consequence",
    "risk_details",
)
ACTION_EXTRA = (
    "problem",
    "corrective_action",
    "preventive_action",
    "responsible_department",
)
PARTICIPANTS = (
    "owner",
    "department_reviewer",
    "control_reviewer",
    "specialist_reviewer",
    "related_reviewer",
    "director_reviewer",
)
ROLES = {
    "department": (
        "Trưởng bộ phận phát hiện",
        "department_reviewer",
        "deviations_department_approve",
    ),
    "specialist": (
        "Trưởng bộ phận chuyên môn",
        "specialist_reviewer",
        "deviations_specialist_approve",
    ),
    "related": ("Bộ phận liên quan", "related_reviewer", "deviations_related_approve"),
    "control": ("Kiểm soát nội bộ", "control_reviewer", "deviations_control_approve"),
    "director": ("Tổng giám đốc", "director_reviewer", "deviations_director_approve"),
}
CHAINS = {
    "REPORT": ("department", "control"),
    "ANALYSIS": ("specialist", "control"),
    "CAPA": ("related", "control", "director"),
}
STAGE_LABELS = {
    "REPORT": "Báo cáo phát hiện sai lệch",
    "ANALYSIS": "Điều tra và phân tích nguyên nhân",
    "CAPA": "Kế hoạch hành động CAPA",
}


def risk_band(score):
    if score is None:
        return "Chưa đánh giá"
    return "Cao" if score >= 10 else "Trung bình" if score >= 5 else "Thấp"


def structured_data(data, *, complete=False):
    """Validate structure at the service boundary, not just in browser formsets."""
    questions = data.get("investigation_5w1h") or {}
    factors = data.get("cause_factors") or {}
    whys = data.get("five_whys") or []
    if not isinstance(questions, dict) or set(questions) - {
        key for key, _ in QUESTIONS
    }:
        raise ValidationError("Bảng 5W1H không hợp lệ.")
    if not isinstance(factors, dict) or set(factors) - {key for key, _ in FACTORS}:
        raise ValidationError("Bảng xương cá không hợp lệ.")
    for key, label in QUESTIONS:
        row = questions.get(key, {})
        if (
            not isinstance(row, dict)
            or set(row) - {"answer", "evidence"}
            or any(not isinstance(v, str) or len(v) > 3000 for v in row.values())
        ):
            raise ValidationError("Dữ liệu 5W1H không hợp lệ.")
        if complete and (
            not row.get("answer", "").strip() or not row.get("evidence", "").strip()
        ):
            raise ValidationError(
                f"{label}: bổ sung trả lời và dữ liệu/căn cứ đối chiếu."
            )
    for key, label in FACTORS:
        row = factors.get(key, {})
        if (
            not isinstance(row, dict)
            or set(row) - {"status", "details"}
            or row.get("status", "") not in dict(FACTOR_STATES)
            or not isinstance(row.get("details", ""), str)
            or len(row.get("details", "")) > 3000
        ):
            raise ValidationError("Dữ liệu xương cá không hợp lệ.")
        if complete and (not row.get("status") or not row.get("details", "").strip()):
            raise ValidationError(
                f"{label}: chọn kết luận và giải thích, kể cả khi loại trừ/không áp dụng."
            )
    if not isinstance(whys, list) or len(whys) > 20:
        raise ValidationError("Tối đa 20 dòng nguyên nhân / 5 Why.")
    for row in whys:
        if (
            not isinstance(row, dict)
            or set(row) - {"cause", *[f"why{i}" for i in range(1, 6)]}
            or any(not isinstance(v, str) or len(v) > 1500 for v in row.values())
        ):
            raise ValidationError("Bảng 5 Why không hợp lệ.")
        if not row.get("cause", "").strip() or not row.get("why1", "").strip():
            raise ValidationError(
                "Mỗi dòng 5 Why cần nguyên nhân và ít nhất câu trả lời Tại sao 1."
            )
        missing = False
        for i in range(1, 6):
            value = row.get(f"why{i}", "").strip()
            if missing and value:
                raise ValidationError(
                    "Điền chuỗi Tại sao liên tục; không bỏ trống ở giữa."
                )
            missing = missing or not value
    if complete and not whys:
        raise ValidationError("Bổ sung ít nhất một nguyên nhân phân tích 5 Why.")

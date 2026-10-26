"""Validation of the three company forms, shared by HTML and state transitions."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from deviations.form_schema import ANALYSIS_EXTRA, ROLES, structured_data
from inventory.access import has_function, is_admin


def display_name(user):
    return user.get_full_name().strip() or user.username


def job_title(user):
    from inventory.models import FunctionAccess

    return (
        FunctionAccess.objects.filter(user=user)
        .values_list("job_title", flat=True)
        .first()
        or ""
    )


def role_allowed(user, role):
    return bool(
        user
        and user.is_active
        and (is_admin(user) or has_function(user, ROLES[role][2]))
    )


def participants_valid(case, roles):
    users = []
    for role in roles:
        label, field, _ = ROLES[role]
        user = getattr(case, field)
        if not role_allowed(user, role):
            raise ValidationError(
                f"Phân công {label} bằng tài khoản đang hoạt động, đúng quyền."
            )
        if user.pk == case.created_by_id and not is_admin(user):
            raise ValidationError(f"{label} không được là người lập hồ sơ.")
        users.append(user)
    nonadmin = [u.pk for u in users if not is_admin(u)]
    if len(set(nonadmin)) != len(nonadmin):
        raise ValidationError(
            "Các cấp duyệt trong cùng một phiếu cần người khác nhau; Admin được xử lý thay và lưu ngoại lệ."
        )


def report(case, *, complete=False):
    if case.reported_at:
        if case.reported_at > timezone.now() or case.reported_at < case.detected_at:
            raise ValidationError(
                "Thời điểm đã báo Trưởng bộ phận phải sau/phù hợp thời điểm phát hiện và không ở tương lai."
            )
    if complete:
        required = (
            "reporter_job_title",
            "discoverer_name",
            "discoverer_job_title",
            "location",
            "actual",
            "expected",
            "what_changed",
            "detection_method",
            "gap_analysis",
            "immediate_response",
        )
        if (
            any(not getattr(case, key).strip() for key in required)
            or not case.reported_at
        ):
            raise ValidationError(
                "Hoàn tất thông tin người lập/người phát hiện, thời điểm báo TBP, 5W1H, phân tích chênh lệch và biện pháp tức thời trước khi gửi. Nếu chưa thực hiện biện pháp, ghi rõ tình trạng."
            )


def investigation(case, *, complete=False):
    structured_data(
        {key: getattr(case, key) for key in ANALYSIS_EXTRA}, complete=complete
    )
    if complete:
        fields = (
            "findings",
            "investigation_expected",
            "investigation_gap",
            "affected_steps",
            "history_details",
            "event_sequence",
            "causal_factors",
            "root_cause",
            "severity",
            "impact",
            "risk_details",
        )
        if (
            any(not getattr(case, key).strip() for key in fields)
            or not case.likelihood
            or not case.consequence
        ):
            raise ValidationError(
                "Hoàn tất phân tích chênh lệch, lịch sử, trình tự, nguyên nhân, đánh giá rủi ro và phân loại trước khi gửi điều tra."
            )


def action(action, *, complete=False):
    if complete and (
        not action.problem.strip() or not action.responsible_department.strip()
    ):
        raise ValidationError("Mỗi dòng CAPA cần tồn tại và bộ phận chịu trách nhiệm.")
    if (
        complete
        and action.kind in {"IMMEDIATE", "CORRECTIVE", "COMBINED"}
        and not action.corrective_action.strip()
    ):
        raise ValidationError("Bổ sung hành động khắc phục / tức thời.")
    if (
        complete
        and action.kind in {"PREVENTIVE", "COMBINED"}
        and not action.preventive_action.strip()
    ):
        raise ValidationError("Bổ sung hành động ngăn ngừa.")

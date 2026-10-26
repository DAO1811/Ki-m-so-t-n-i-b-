from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from deviations import access
from deviations.constants import CaseStatus
from deviations.form_schema import (
    ANALYSIS_EXTRA,
    FORM_VERSION,
    PARTICIPANTS,
    REPORT_EXTRA,
    ROLES,
)
from deviations.models import Case, Event
from inventory.access import has_function, is_admin
from inventory.hierarchy import approval_level

from . import form_data
from .common import active_actors, locked_case, record, snapshot

REPORT_FIELDS = (
    "title",
    "category",
    "department",
    "location",
    "occurred_at",
    "detected_at",
    "actual",
    "expected",
    "immediate_response",
    "impact",
    "estimated_loss",
    "source_document",
    "source_product",
    "source_stocktake",
)
ANALYSIS_FIELDS = (
    "findings",
    "direct_cause",
    "root_cause",
    "related_people",
    "severity",
    "impact",
)


def validate_sources(case, user):
    from inventory.services import (
        can_approve_adjustments,
        documents_for,
        warehouses_for,
    )

    if (
        case.source_document_id
        and not documents_for(user).filter(pk=case.source_document_id).exists()
    ):
        raise PermissionDenied("Chưa có quyền liên kết phiếu nguồn này.")
    if case.source_product_id and not has_function(user, "products_view"):
        raise PermissionDenied("Chưa có quyền liên kết mã hàng.")
    if case.source_stocktake_id:
        session = case.source_stocktake
        if (
            getattr(session, "is_deleted", False)
            or not has_function(user, "stocktakes_view")
            or not (
                can_approve_adjustments(user)
                or warehouses_for(user).filter(pk=session.warehouse_id).exists()
            )
        ):
            raise PermissionDenied("Chưa có quyền liên kết biên bản kiểm kê.")


def validate_report(case, user):
    case.full_clean()
    if not case.category.active:
        raise ValidationError("Nhóm sai lệch đã ngừng sử dụng.")
    if case.detected_at > timezone.now() or (
        case.occurred_at and case.occurred_at > case.detected_at
    ):
        raise ValidationError(
            "Thời điểm phát hiện không ở tương lai; xảy ra không sau phát hiện. Để trống thời điểm xảy ra nếu chưa rõ."
        )
    validate_sources(case, user)
    if case.form_version >= 2:
        form_data.report(case)


@transaction.atomic
def create_case(user, data):
    user = active_actors(user)[user.pk]
    access.require(user, "deviations_create")
    case = Case(
        created_by=user,
        creator_level=approval_level(user),
        form_version=FORM_VERSION,
        reporter_name=form_data.display_name(user),
        **{key: data[key] for key in REPORT_FIELDS},
    )
    for key in REPORT_EXTRA:
        if key in data:
            setattr(case, key, data[key])
    if not case.reporter_job_title:
        case.reporter_job_title = form_data.job_title(user)
    validate_report(case, user)
    case.save()
    Event.objects.create(
        case=case, actor=user, action="Tạo hồ sơ", after=snapshot(case)
    )
    return case


@transaction.atomic
def edit_case(pk, user, revision, data):
    case = locked_case(pk, revision)
    user = active_actors(user)[user.pk]
    access.require(user, "deviations_create")
    if (not is_admin(user) and case.created_by_id != user.pk) or case.status not in {
        CaseStatus.DRAFT,
        CaseStatus.NEEDS_INFO,
    }:
        raise PermissionDenied(
            "Chỉ sửa báo cáo của mình khi nháp hoặc đang được yêu cầu bổ sung."
        )
    before = snapshot(case)
    for key in REPORT_FIELDS + (REPORT_EXTRA if case.form_version >= 2 else ()):
        if key in data:
            setattr(case, key, data[key])
    validate_report(case, user)
    return record(
        case,
        user,
        "Bổ sung thông tin" if case.status == CaseStatus.NEEDS_INFO else "Sửa bản nháp",
        before,
    )


@transaction.atomic
def assign_case(pk, user, revision, owner):
    case = locked_case(pk, revision)
    actors = active_actors(user, owner)
    user, owner = actors[user.pk], actors[owner.pk]
    access.require(user, "deviations_manage")
    if case.is_terminal or case.status == CaseStatus.DRAFT:
        raise ValidationError("Chỉ phân công hồ sơ đã gửi và chưa kết thúc.")
    if not owner.is_active or not has_function(owner, "deviations_manage"):
        raise ValidationError(
            "Người phụ trách cần tài khoản hoạt động và quyền quản lý hồ sơ sai lệch."
        )
    before = snapshot(case)
    case.owner = owner
    return record(case, user, "Phân công phụ trách", before)


@transaction.atomic
def save_analysis(pk, user, revision, data):
    from .policies import require_enabled

    case = locked_case(pk, revision)
    user = active_actors(user)[user.pk]
    access.manage(case, user)
    require_enabled()
    if case.status not in {CaseStatus.INVESTIGATING, CaseStatus.PLANNING}:
        raise ValidationError(
            "Chỉ cập nhật xác minh khi đang xác minh hoặc lập kế hoạch."
        )
    before = snapshot(case)
    if case.form_version >= 2 and case.status != CaseStatus.INVESTIGATING:
        raise ValidationError(
            "Điều tra đã được xác nhận; yêu cầu mở lại điều tra trước khi sửa."
        )
    for key in ANALYSIS_FIELDS + (ANALYSIS_EXTRA if case.form_version >= 2 else ()):
        if key in data:
            setattr(case, key, data[key])
    if case.form_version >= 2:
        form_data.investigation(case)
    case.full_clean()
    return record(case, user, "Cập nhật xác minh", before)


@transaction.atomic
def assign_participants(pk, user, revision, data):
    case = locked_case(pk, revision)
    actors = active_actors(user, *[data.get(key) for key in PARTICIPANTS])
    user = actors[user.pk]
    access.require(user, "deviations_manage")
    if case.is_terminal or case.status == CaseStatus.DRAFT:
        raise ValidationError("Chỉ phân công hồ sơ đã gửi, chưa kết thúc.")
    pending = case.approval_runs.filter(status="PENDING").first()
    if pending and (
        pending.stage != "REPORT"
        or any(
            getattr(case, key + "_id") != (data[key].pk if data.get(key) else None)
            for key in PARTICIPANTS
            if key != "owner"
        )
    ):
        raise ValidationError(
            "Rút phiếu / trả lại bổ sung trước khi thay người đã chốt trong chuỗi duyệt."
        )
    before = snapshot(case)
    for key in PARTICIPANTS:
        person = data.get(key)
        setattr(case, key, actors[person.pk] if person else None)
    if case.owner and (
        not case.owner.is_active or not has_function(case.owner, "deviations_manage")
    ):
        raise ValidationError(
            "Người phụ trách cần quyền quản lý hồ sơ và tài khoản hoạt động."
        )
    for role, (_, field, _) in ROLES.items():
        if getattr(case, field) and not form_data.role_allowed(
            getattr(case, field), role
        ):
            raise ValidationError("Người được phân công chưa có quyền tương ứng.")
    case.full_clean()
    return record(case, user, "Phân công theo biểu mẫu", before)

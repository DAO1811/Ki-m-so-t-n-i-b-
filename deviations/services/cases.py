from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from deviations import access
from deviations.constants import CaseStatus
from deviations.models import Case, Event
from inventory.access import has_function, is_admin
from inventory.hierarchy import approval_level

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
            session.is_deleted
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


@transaction.atomic
def create_case(user, data):
    user = active_actors(user)[user.pk]
    access.require(user, "deviations_create")
    case = Case(
        created_by=user,
        creator_level=approval_level(user),
        **{key: data[key] for key in REPORT_FIELDS},
    )
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
    for key in REPORT_FIELDS:
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
    for key in ANALYSIS_FIELDS:
        setattr(case, key, data[key])
    case.full_clean()
    return record(case, user, "Cập nhật xác minh", before)

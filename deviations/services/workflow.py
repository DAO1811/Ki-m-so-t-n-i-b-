from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from deviations import access
from deviations.constants import ActionStatus, CaseStatus
from deviations.models import Case, Evaluation
from deviations.workflow import TRANSITIONS
from inventory.access import is_admin

from .cases import validate_report
from .common import active_actors, locked_case, reason_required, record, snapshot
from .policies import policy_snapshot, require_enabled


def actions_for_round(case):
    return case.actions.filter(round=case.round)


def guard_actions(case, *, completed=False):
    actions = list(actions_for_round(case).select_related("assignee"))
    if not actions:
        raise ValidationError("Cần ít nhất một hành động cho lượt xử lý hiện tại.")
    if any(not a.due_date or not a.assignee.is_active for a in actions):
        raise ValidationError(
            "Mỗi hành động cần hạn và người thực hiện đang hoạt động."
        )
    if completed and any(
        a.status != ActionStatus.DONE or not a.result.strip() for a in actions
    ):
        raise ValidationError("Còn công việc chưa hoàn thành hoặc thiếu kết quả.")
    if case.actions.filter(extensions__status="PENDING").exists():
        raise ValidationError(
            "Xử lý các đề nghị gia hạn đang chờ trước khi chuyển bước."
        )


@transaction.atomic
def transition(
    pk, user, revision, command, *, reason="", confirm=False, duplicate_of=None
):
    spec = TRANSITIONS.get(command)
    if spec is None:
        raise ValidationError("Thao tác không hợp lệ.")
    if command == "duplicate" and duplicate_of:
        # Both cases are locked in ID order to prevent cycles and deadlocks.
        locked = {
            c.pk: c
            for c in Case.objects.select_for_update()
            .filter(pk__in=[pk, duplicate_of.pk])
            .order_by("pk")
        }
        duplicate_of = locked.get(duplicate_of.pk)
    case = locked_case(pk, revision)
    actors = active_actors(user, case.created_by)
    user, case.created_by = actors[user.pk], actors[case.created_by_id]
    access.require_member(user)
    if case.status not in spec.sources:
        raise ValidationError("Hồ sơ đã đổi bước. Tải lại trước khi tiếp tục.")
    if command == "cancel":
        if not is_admin(user):
            if case.created_by_id == user.pk and case.status in {
                CaseStatus.DRAFT,
                CaseStatus.NEEDS_INFO,
            }:
                access.require(user, "deviations_create")
            else:
                access.manage(case, user)
    elif command == "submit":
        access.require(user, spec.permission)
        if not is_admin(user) and case.created_by_id != user.pk:
            raise PermissionDenied("Chỉ người lập hoặc Admin được gửi ghi nhận.")
    else:
        access.require(user, spec.permission)
        if (
            command not in {"accept", "need_info", "decline", "duplicate"}
            and not spec.review
        ):
            access.manage(case, user)
    if spec.reason:
        reason = reason_required(reason)
    before = snapshot(case)
    # Initial reporting is usable while the company has not configured reviews.
    policy = require_enabled() if command not in {"submit", "cancel"} else None
    if spec.review:
        access.review(case, user, confirm)
    if spec.guard == "report":
        validate_report(case, user)
        case.submitted_at = timezone.now()
    elif spec.guard == "accept":
        if not case.owner_id or not case.owner.is_active:
            raise ValidationError("Phân công người phụ trách trước khi tiếp nhận.")
        if not case.policy_snapshot:
            case.policy_snapshot = policy_snapshot(policy)
    elif spec.guard == "analysis":
        if any(
            not getattr(case, key).strip()
            for key in ("findings", "root_cause", "severity", "impact")
        ):
            raise ValidationError(
                "Bổ sung kết quả xác minh, nguyên nhân gốc, mức độ và ảnh hưởng."
            )
    elif spec.guard == "actions":
        guard_actions(case)
    elif spec.guard == "completed":
        guard_actions(case, completed=True)
    elif spec.guard == "duplicate":
        if (
            not duplicate_of
            or duplicate_of.pk == case.pk
            or duplicate_of.status
            in {CaseStatus.DRAFT, CaseStatus.DUPLICATE, CaseStatus.CANCELLED}
        ):
            raise ValidationError(
                "Chọn hồ sơ gốc đã ghi nhận, khác hồ sơ này và không phải hồ sơ trùng/hủy."
            )
        case.duplicate_of = duplicate_of
    if command == "reopen":
        case.round += 1
        case.closed_at = None
    case.status = spec.target
    return record(
        case,
        user,
        spec.label,
        before,
        reason,
        {
            "admin_self_review_confirmed": bool(
                spec.review and is_admin(user) and confirm
            )
        },
    )


@transaction.atomic
def evaluate(
    pk, user, revision, *, criteria, result, effective, checked_at, confirm=False
):
    case = locked_case(pk, revision)
    actors = active_actors(user, case.created_by)
    user, case.created_by = actors[user.pk], actors[case.created_by_id]
    require_enabled()
    access.review(case, user, confirm)
    if case.status != CaseStatus.VERIFYING:
        raise ValidationError("Chỉ đánh giá hồ sơ đang chờ đánh giá hiệu quả.")
    guard_actions(case, completed=True)
    if (
        not criteria.strip()
        or not result.strip()
        or type(effective) is not bool
        or not checked_at
        or checked_at > timezone.now()
        # The datetime-local form records minutes, not sub-minute precision.
        or checked_at.replace(second=0, microsecond=0)
        < case.submitted_at.replace(second=0, microsecond=0)
    ):
        raise ValidationError(
            "Ghi tiêu chí, kết quả, kết luận và thời điểm kiểm tra hợp lệ sau khi báo cáo."
        )
    before = snapshot(case)
    evaluation = Evaluation(
        case=case,
        round=case.round,
        criteria=criteria,
        result=result,
        effective=effective,
        checked_at=checked_at,
        checked_by=user,
        policy_snapshot=case.policy_snapshot,
    )
    evaluation.full_clean()
    evaluation.save()
    if effective:
        case.status, case.closed_at = CaseStatus.CLOSED, timezone.now()
    else:
        case.status = CaseStatus.PLANNING
        case.round += 1
    return record(
        case,
        user,
        "Xác nhận kết thúc" if effective else "Chưa hiệu quả, bổ sung hành động",
        before,
        extra={
            "evaluation_id": evaluation.pk,
            "admin_self_review_confirmed": bool(is_admin(user) and confirm),
        },
    )

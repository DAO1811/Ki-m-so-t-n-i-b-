from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from deviations import access
from deviations.constants import ActionStatus, CaseStatus
from deviations.models import Action, Extension
from inventory.access import has_function

from .common import active_actors, locked_case, reason_required, record, snapshot
from .policies import require_enabled


def action_snapshot(action):
    return {
        field.name: str(getattr(action, field.attname)) for field in action._meta.fields
    }


def action_lock(case, pk, revision):
    action = Action.objects.select_for_update().get(pk=pk, case=case)
    if (
        type(revision) is not int
        or action.revision != revision
        or action.round != case.round
    ):
        raise ValidationError(
            "Công việc đã thay đổi hoặc thuộc lượt xử lý cũ. Tải lại trước khi tiếp tục."
        )
    return action


@transaction.atomic
def save_action(pk, user, revision, data, *, action_id=None, action_revision=None):
    case = locked_case(pk, revision)
    actors = active_actors(user, data["assignee"])
    user, assignee = actors[user.pk], actors[data["assignee"].pk]
    access.manage(case, user)
    require_enabled()
    if case.status not in {CaseStatus.INVESTIGATING, CaseStatus.PLANNING}:
        raise ValidationError(
            "Chỉ sửa kế hoạch trong bước xác minh/lập kế hoạch; không thay kế hoạch đã xác nhận."
        )
    if not assignee.is_active or not has_function(assignee, "deviations_work"):
        raise ValidationError(
            "Người thực hiện cần tài khoản hoạt động và quyền thực hiện công việc sai lệch."
        )
    action = (
        action_lock(case, action_id, action_revision)
        if action_id
        else Action(case=case, round=case.round)
    )
    before = snapshot(case)
    old = action_snapshot(action) if action_id else {}
    for key in ("kind", "title", "assignee", "collaborators", "due_date"):
        setattr(action, key, data[key])
    if action_id:
        action.revision += 1
    action.full_clean()
    action.save()
    record(
        case,
        user,
        "Sửa hành động" if action_id else "Thêm hành động",
        before,
        extra={"action_before": old, "action_after": action_snapshot(action)},
    )
    return action


@transaction.atomic
def work_action(pk, user, revision, action_id, action_revision, status, result):
    case = locked_case(pk, revision)
    action = action_lock(case, action_id, action_revision)
    user = active_actors(user)[user.pk]
    require_enabled()
    access.work(action, user)
    if case.status != CaseStatus.EXECUTING or action.status == ActionStatus.DONE:
        raise ValidationError(
            "Chỉ cập nhật công việc chưa hoàn thành khi hồ sơ đang thực hiện."
        )
    if (
        status not in {ActionStatus.IN_PROGRESS, ActionStatus.DONE}
        or not result.strip()
    ):
        raise ValidationError("Chọn trạng thái và ghi kết quả/căn cứ thực hiện.")
    if (
        status == ActionStatus.DONE
        and action.extensions.filter(status="PENDING").exists()
    ):
        raise ValidationError(
            "Cần xử lý đề nghị gia hạn đang chờ trước khi xác nhận hoàn thành."
        )
    before, old = snapshot(case), action_snapshot(action)
    action.status, action.result = status, result
    action.completed_at = timezone.now() if status == ActionStatus.DONE else None
    action.revision += 1
    action.full_clean()
    action.save()
    record(
        case,
        user,
        "Cập nhật thực hiện",
        before,
        extra={"action_before": old, "action_after": action_snapshot(action)},
    )
    return action


@transaction.atomic
def request_extension(
    pk, user, revision, action_id, action_revision, new_due_date, reason
):
    case = locked_case(pk, revision)
    action = action_lock(case, action_id, action_revision)
    user = active_actors(user)[user.pk]
    require_enabled()
    access.work(action, user)
    limit = case.policy_snapshot.get("max_extensions")
    if limit is None:
        raise ValidationError(
            "Quy tắc của hồ sơ chưa cấu hình gia hạn; không tự áp số lần từ tài liệu tham khảo."
        )
    if (
        case.status != CaseStatus.EXECUTING
        or action.status == ActionStatus.DONE
        or not action.due_date
    ):
        raise ValidationError(
            "Chỉ đề nghị gia hạn công việc đang thực hiện và đã có hạn."
        )
    if (
        action.extensions.filter(status="PENDING").exists()
        or action.extensions.filter(status="APPROVED").count() >= limit
    ):
        raise ValidationError(
            "Đang có đề nghị chờ quyết định hoặc đã hết số lần gia hạn được cấu hình."
        )
    if (
        not new_due_date
        or new_due_date <= action.due_date
        or new_due_date < timezone.localdate()
    ):
        raise ValidationError("Hạn mới phải sau hạn cũ và không trước hôm nay.")
    before = snapshot(case)
    extension = Extension.objects.create(
        action=action,
        old_due_date=action.due_date,
        new_due_date=new_due_date,
        reason=reason_required(reason),
        requested_by=user,
    )
    action.revision += 1
    action.save(update_fields=["revision"])
    record(
        case,
        user,
        "Đề nghị gia hạn",
        before,
        extra={
            "extension_id": extension.pk,
            "old_due_date": str(action.due_date),
            "requested_due_date": str(new_due_date),
        },
    )
    return extension


@transaction.atomic
def decide_extension(
    pk, user, revision, extension_id, approve, reason, *, confirm=False
):
    case = locked_case(pk, revision)
    extension = (
        Extension.objects.select_for_update()
        .select_related("action")
        .get(pk=extension_id, action__case=case)
    )
    actors = active_actors(user, case.created_by)
    user, case.created_by = actors[user.pk], actors[case.created_by_id]
    require_enabled()
    access.review(case, user, confirm, extra_people=[extension.requested_by_id])
    action = Action.objects.select_for_update().get(pk=extension.action_id)
    if (
        type(approve) is not bool
        or extension.status != "PENDING"
        or case.status != CaseStatus.EXECUTING
        or action.round != case.round
        or action.status == ActionStatus.DONE
        or action.due_date != extension.old_due_date
    ):
        raise ValidationError(
            "Đề nghị hoặc công việc đã thay đổi. Tải lại trước khi quyết định."
        )
    before = snapshot(case)
    extension.status = "APPROVED" if approve else "REJECTED"
    extension.decision_reason = reason_required(reason)
    extension.decided_by, extension.decided_at = user, timezone.now()
    extension.save()
    if approve:
        action.due_date = extension.new_due_date
        action.revision += 1
        action.save(update_fields=["due_date", "revision"])
    record(
        case,
        user,
        "Đồng ý gia hạn" if approve else "Không đồng ý gia hạn",
        before,
        reason,
        {
            "extension_id": extension.pk,
            "old_due_date": str(extension.old_due_date),
            "new_due_date": str(action.due_date),
            "admin_self_review_confirmed": bool(confirm),
        },
    )
    return extension

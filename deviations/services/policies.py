from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from deviations.models import PolicyEvent, WorkflowPolicy
from inventory.access import is_admin

POLICY_FIELDS = (
    "enabled",
    "minimum_review_level",
    "independent_review",
    "require_higher_level",
    "max_extensions",
    "revision",
)


def policy_snapshot(policy):
    return {"schema_version": 1, **{key: getattr(policy, key) for key in POLICY_FIELDS}}


def require_enabled():
    policy = WorkflowPolicy.objects.filter(pk=1).first()
    if not policy or not policy.enabled:
        raise ValidationError(
            "Đã mở ghi nhận hồ sơ. Các bước xử lý đang chờ công ty chốt và cấu hình quy trình."
        )
    return policy


@transaction.atomic
def update_policy(user, data, revision, reason):
    from .common import active_actors, reason_required

    user = active_actors(user)[user.pk]
    if not is_admin(user):
        raise PermissionDenied
    policy, _ = WorkflowPolicy.objects.get_or_create(pk=1)
    policy = WorkflowPolicy.objects.select_for_update().get(pk=1)
    if policy.revision != revision:
        raise ValidationError("Cấu hình vừa thay đổi. Tải lại trước khi lưu.")
    reason = reason_required(reason)
    if data["enabled"] and (
        data["minimum_review_level"] not in {10, 20, 30, 40}
        or any(
            type(data[key]) is not bool
            for key in ("independent_review", "require_higher_level")
        )
    ):
        raise ValidationError(
            "Chốt cấp xác nhận và hai quy tắc kiểm soát trước khi mở xử lý."
        )
    limit = data.get("max_extensions")
    if limit is not None and (type(limit) is not int or not 0 <= limit <= 100):
        raise ValidationError("Số lần gia hạn phải từ 0 đến 100 hoặc để chưa cấu hình.")
    before = policy_snapshot(policy)
    for key in POLICY_FIELDS:
        if key != "revision":
            setattr(policy, key, data[key])
    policy.revision += 1
    policy.updated_by = user
    policy.save()
    PolicyEvent.objects.create(
        actor=user, reason=reason, before=before, after=policy_snapshot(policy)
    )
    return policy

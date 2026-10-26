from django.core.exceptions import ValidationError
from django.db import transaction

from deviations.models import Case, Event


def snapshot(case):
    return {
        field.name: str(getattr(case, field.attname))
        if getattr(case, field.attname) is not None
        else None
        for field in case._meta.fields
    }


def locked_case(pk, revision):
    case = Case.objects.select_for_update().get(pk=pk)
    if type(revision) is not int or revision != case.revision:
        raise ValidationError(
            "Hồ sơ đã thay đổi. Tải lại và kiểm tra bản mới trước khi tiếp tục."
        )
    return case


def record(case, actor, action, before, reason="", extra=None):
    case.revision += 1
    case.save()
    after = snapshot(case)
    event_before = before
    if case.form_version >= 2:
        # A full signed submission lives on ApprovalRun. Avoid repeating every
        # long analysis field for each signature while retaining actual changes.
        changed = {key for key, value in after.items() if value != before.get(key)}
        event_before = {key: before.get(key) for key in changed}
        after = {key: after[key] for key in changed}
        after["_format"] = "delta-v2"
    if extra:
        after.update(extra)
    Event.objects.create(
        case=case,
        actor=actor,
        action=action,
        before=event_before,
        after=after,
        reason=reason,
    )
    return case


def reason_required(reason):
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ValidationError("Ghi lý do từ 1 đến 1000 ký tự.")
    return reason


@transaction.atomic
def active_actors(*users):
    """Same account-lock ordering as the common employee editor."""
    from django.contrib.auth import get_user_model

    from inventory.models import FunctionAccess

    ids = sorted({u.pk for u in users if u is not None})
    accounts = {
        u.pk: u
        for u in get_user_model()
        .objects.select_for_update()
        .filter(pk__in=ids)
        .order_by("pk")
    }
    list(
        FunctionAccess.objects.select_for_update()
        .filter(user_id__in=ids)
        .order_by("user_id")
    )
    return accounts

"""Approval rank is separate from function grants and warehouse assignments."""

from django.contrib.auth import get_user_model

LEVEL_CHOICES = [(10, "Nhân viên"), (20, "Leader"), (30, "Trưởng phòng")]
LEVEL_LABELS = dict(LEVEL_CHOICES + [(40, "Admin tổng")])


def approval_level(user):
    if not user or not user.is_authenticated:
        return 0
    if user.is_superuser:
        return 40
    from .models import FunctionAccess

    return (
        FunctionAccess.objects.filter(user_id=user.pk)
        .values_list("approval_level", flat=True)
        .first()
        or 10
    )


def maker_level(doc):
    # Demoting a maker never lowers the review requirement of an existing record.
    return max(doc.creator_level, approval_level(doc.created_by))


def lock_approval_accounts(doc, user):
    """Serialize approval against account/role changes made through EmployeeForm."""
    from .models import FunctionAccess

    accounts = {
        account.pk: account
        for account in get_user_model()
        .objects.select_for_update()
        .filter(pk__in=[doc.created_by_id, user.pk])
        .order_by("pk")
    }
    list(
        FunctionAccess.objects.select_for_update()
        .filter(user_id__in=accounts)
        .order_by("user_id")
    )
    doc.created_by = accounts[doc.created_by_id]
    return accounts[user.pk]

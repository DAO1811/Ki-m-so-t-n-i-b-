"""Shared authorization helpers for company records and storage."""


def explicit_permission(user, codename):
    return bool(
        user.is_authenticated
        and user.is_active
        and user.user_permissions.filter(
            content_type__app_label="inventory", codename=codename
        ).exists()
    )


def may_attach(doc, user):
    return bool(
        user.is_active
        and doc.kind == "IN"
        and doc.status != "CANCELLED"
        and (
            user.is_superuser
            or (
                user.has_perm("inventory.add_document") and doc.created_by_id == user.pk
            )
            or doc.destination.managers.filter(pk=user.pk).exists()
        )
    )

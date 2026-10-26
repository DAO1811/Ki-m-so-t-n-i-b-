"""Visibility is company-wide; write privileges remain explicit and current."""

from django.core.exceptions import PermissionDenied

from inventory.access import has_function, is_admin
from inventory.hierarchy import approval_level


def require_member(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Cần đăng nhập bằng tài khoản đang hoạt động.")


def require(user, permission):
    require_member(user)
    if not has_function(user, permission):
        raise PermissionDenied("Bạn chưa được cấp quyền thao tác hồ sơ sai lệch này.")


def manage(case, user):
    require(user, "deviations_manage")
    if not is_admin(user) and case.owner_id != user.pk:
        raise PermissionDenied(
            "Chỉ người phụ trách hồ sơ hoặc Admin được thực hiện bước này."
        )


def work(action, user):
    require(user, "deviations_work")
    if not is_admin(user) and action.assignee_id != user.pk:
        raise PermissionDenied(
            "Chỉ người được giao công việc hoặc Admin được cập nhật kết quả."
        )


def review(case, user, confirm=False, *, extra_people=()):
    return review_as(
        case, user, "deviations_review", confirm, extra_people=extra_people
    )


def review_as(
    case, user, permission, confirm=False, *, extra_people=(), proposer_level=0
):
    require(user, permission)
    policy = case.policy_snapshot
    if policy.get("schema_version") != 1 or not {
        "minimum_review_level",
        "independent_review",
        "require_higher_level",
    }.issubset(policy):
        from django.core.exceptions import ValidationError

        raise ValidationError("Hồ sơ chưa có phiên bản quy tắc xác nhận hợp lệ.")
    related = {case.created_by_id, case.owner_id, *extra_people}
    related.update(case.actions.values_list("assignee_id", flat=True))
    if is_admin(user):
        if user.pk in related and not confirm:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                "Admin đang xác nhận hồ sơ có công việc của chính mình. Đánh dấu xác nhận sau khi kiểm tra."
            )
        return
    if approval_level(user) < policy["minimum_review_level"]:
        raise PermissionDenied("Chưa đủ cấp xác nhận theo quy tắc của hồ sơ.")
    if policy["independent_review"] and user.pk in related:
        raise PermissionDenied(
            "Người xác nhận phải độc lập với người lập, phụ trách và thực hiện."
        )
    if policy["require_higher_level"] and approval_level(user) <= max(
        case.creator_level, approval_level(case.created_by), proposer_level
    ):
        raise PermissionDenied("Người xác nhận phải cao cấp hơn người lập.")


def route_allowed(user, name, method):
    from .constants import READ_ROUTES, ROUTE_PERMISSIONS

    if not user.is_active:
        return False
    if name in READ_ROUTES:
        return method in {"GET", "HEAD"}
    permission = ROUTE_PERMISSIONS.get(name)
    if permission == "admin":
        return is_admin(user)
    if permission == "authenticated":
        return True  # Case ownership and operation-specific grants checked in services.
    return bool(permission and has_function(user, permission))


def control_review(case, user, confirm=False, *, extra_people=()):
    if case.form_version < 2:
        return review(case, user, confirm, extra_people=extra_people)
    if not is_admin(user) and case.control_reviewer_id != user.pk:
        raise PermissionDenied(
            "Chỉ KSNB được phân công hoặc Admin được đánh giá/kết thúc hồ sơ này."
        )
    return review_as(
        case, user, "deviations_control_approve", confirm, extra_people=extra_people
    )

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from inventory.access import (
    FUNCTION_KEYS,
    FUNCTION_ROWS,
    function_codes,
    normalize_permissions,
)
from inventory.forms import EmployeeForm
from inventory.models import FunctionAccess


def require_admin(user):
    if not user.is_superuser:
        raise PermissionDenied(
            "Chỉ quản trị viên được quản lý nhân viên và phân quyền."
        )


@login_required
def team(request):
    qs = (
        get_user_model()
        .objects.all()
        .prefetch_related(
            "groups", "warehouses", "managed_warehouses", "issue_warehouses"
        )
        .select_related("function_access")
        .order_by("username")
    )
    if request.GET.get("q"):
        qs = qs.filter(
            Q(username__icontains=request.GET["q"])
            | Q(first_name__icontains=request.GET["q"])
            | Q(last_name__icontains=request.GET["q"])
        )
    return render(
        request,
        "team.html",
        {
            "employees": qs,
            "ceo_ids": {
                e.user_id
                for e in FunctionAccess.objects.filter(user__in=qs)
                if "adjustments_approve" in e.permissions
            },
        },
    )


@login_required
def employee_form(request, pk=None):
    require_admin(request.user)
    employee = get_object_or_404(get_user_model(), pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, instance=employee, actor=request.user)
    if request.method == "POST" and form.is_valid():
        if (
            employee
            and employee.pk == request.user.pk
            and not form.cleaned_data["is_active"]
        ):
            form.add_error("is_active", "Bạn không thể khóa tài khoản đang sử dụng.")
        else:
            try:
                with transaction.atomic():
                    import json

                    from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
                    from django.contrib.contenttypes.models import ContentType

                    from inventory.models import FunctionAccess

                    previous = (
                        FunctionAccess.objects.filter(user=employee).first()
                        if employee
                        else None
                    )
                    before = list(previous.permissions) if previous else []
                    before_role = (
                        {
                            "job_title": previous.job_title,
                            "approval_level": previous.approval_level,
                        }
                        if previous
                        else {}
                    )
                    saved = form.save()
                    details = {
                        "active": saved.is_active,
                        "role_before": before_role,
                        "job_title": saved.function_access.job_title,
                        "approval_level": saved.function_access.approval_level,
                        "warehouses": list(
                            saved.warehouses.values_list("code", flat=True)
                        ),
                        "managed_warehouses": list(
                            saved.managed_warehouses.values_list("code", flat=True)
                        ),
                        "issue_warehouses": list(
                            saved.issue_warehouses.values_list("code", flat=True)
                        ),
                        "function_permissions_before": before,
                        "function_permissions": sorted(function_codes(saved)),
                    }
                    LogEntry.objects.create(
                        user=request.user,
                        content_type=ContentType.objects.get_for_model(saved),
                        object_id=str(saved.pk),
                        object_repr=saved.username[:200],
                        action_flag=CHANGE if employee else ADDITION,
                        change_message="Cập nhật tài khoản / quyền chức năng: "
                        + json.dumps(details, ensure_ascii=False),
                    )
                if saved.pk == request.user.pk:
                    update_session_auth_hash(request, saved)
                messages.success(
                    request,
                    "Đã lưu nhân viên và quyền chức năng. Quyền mới áp dụng từ lần truy cập tiếp theo.",
                )
                return redirect("team")
            except ValidationError as exc:
                form.add_error(None, exc)
    selected = set(form["function_permissions"].value() or [])
    rows = [
        {
            "label": title,
            "cells": [
                {
                    "key": f"{module}_{action}",
                    "label": label,
                    "checked": f"{module}_{action}" in selected,
                }
                for action, label in actions
            ],
        }
        for module, title, actions in FUNCTION_ROWS
    ]
    return render(
        request,
        "employee_form.html",
        {
            "form": form,
            "editing": bool(employee),
            "editing_admin": bool(employee and employee.is_superuser),
            "permission_rows": rows,
            "permission_dependencies": {
                key: sorted(set(normalize_permissions([key])) - {key})
                for key in FUNCTION_KEYS
            },
        },
    )


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Đã đổi mật khẩu. Bạn vẫn đang đăng nhập.")
        return redirect("password_change")
    return render(request, "password_change.html", {"form": form})

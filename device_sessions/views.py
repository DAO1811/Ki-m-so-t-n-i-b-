from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inventory.access import is_admin

from . import services
from .models import DeviceSession


@login_required
def my_sessions(request):
    current = request.session.session_key
    rows = DeviceSession.objects.filter(user=request.user)
    return render(
        request,
        "device_sessions/list.html",
        {
            "rows": rows,
            "current_key": current,
            "page_name": "Thiết bị đang đăng nhập",
        },
    )


@login_required
@require_POST
def logout_device(request, pk):
    row = get_object_or_404(DeviceSession, pk=pk, user=request.user)
    if row.session_key == request.session.session_key:
        messages.error(request, "Đây là thiết bị bạn đang dùng; hãy bấm Đăng xuất.")
    else:
        services.revoke([row])
        messages.success(request, f"Đã đăng xuất {row.device or 'thiết bị'}.")
    return redirect("device_sessions")


@login_required
@require_POST
def logout_others(request):
    rows = DeviceSession.objects.filter(user=request.user).exclude(
        session_key=request.session.session_key
    )
    count = services.revoke(rows)
    messages.success(request, f"Đã đăng xuất {count} thiết bị khác.")
    return redirect("device_sessions")


@login_required
@require_POST
def admin_logout_user(request, pk):
    """Admin signs an employee out everywhere, e.g. when they leave."""
    if not is_admin(request.user):
        raise PermissionDenied("Chỉ Admin được đăng xuất tài khoản khác.")
    target = get_object_or_404(get_user_model(), pk=pk)
    rows = DeviceSession.objects.filter(user=target)
    if target.pk == request.user.pk:
        rows = rows.exclude(session_key=request.session.session_key)
    count = services.revoke(rows)
    messages.success(request, f"Đã đăng xuất {target.username} khỏi {count} thiết bị.")
    return redirect("employee_edit", pk=target.pk)

"""Unlock screen for Face ID sessions (bank-app style)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import services
from .views import api


def back(data):
    target = services.safe_next(data.get("next", "/"))
    return "/" if target.startswith("/unlock") else target


@login_required
@require_GET
@never_cache
def unlock(request):
    target = services.safe_next(request.GET.get("next", "/"))
    if target.startswith("/unlock"):
        target = "/"
    if not services.app_lock_applies(request):
        return redirect(target)
    # Opening this page locks the session, so "back" cannot skip Face ID.
    services.lock(request)
    return render(
        request,
        "passkeys/unlock.html",
        {
            "next": target,
            "display_name": request.user.get_full_name() or request.user.get_username(),
        },
    )


@api(authenticated=True)
def unlock_options(request, data):
    return services.unlock_options(request)


@api(authenticated=True)
def unlock_verify(request, data):
    services.unlock_finish(request, data.get("ceremony_id"), data.get("credential"))
    return {"redirect": back(data)}


@api(authenticated=True)
def unlock_password(request, data):
    password = data.get("password", "")
    if not isinstance(password, str) or not 1 <= len(password) <= 1024:
        raise services.PasskeyError("Nhập mật khẩu để mở khóa.")
    services.unlock_with_password(request, password)
    return {"redirect": back(data)}


@api(authenticated=True)
def ping(request, data):
    """Keep an in-use Face ID session unlocked; report if it is locked."""
    if not services.app_lock_applies(request):
        return {"ok": True}
    if request.session.get("app_locked") is True:
        return {"locked": True}
    request.session["app_seen_at"] = services.now_seconds()
    return {"ok": True}


@api(authenticated=True)
def lock_now(request, data):
    if services.app_lock_applies(request):
        services.lock(request)
    return {"ok": True}

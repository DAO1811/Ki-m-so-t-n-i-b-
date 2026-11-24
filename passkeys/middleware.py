from django.contrib.auth import logout
from django.db import DatabaseError

from .models import PasskeyCredential


class PasskeySessionMiddleware:
    """Revocation affects passkey sessions; ordinary password sessions are untouched."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.session.get("passkey_credential_id")
        if raw is not None:
            raw = str(raw)
            valid = False
            if (
                request.user.is_authenticated
                and raw.isascii()
                and raw.isdigit()
                and len(raw) <= 18
            ):
                try:
                    valid = PasskeyCredential.objects.filter(
                        pk=raw, user_id=request.user.pk, revoked_at__isnull=True
                    ).exists()
                except DatabaseError:
                    valid = False
            if not valid:
                logout(request)
        return self.get_response(request)


class AppLockMiddleware:
    """Bank-app style lock for every signed-in session.

    After APP_LOCK_SERVER_GAP seconds without any request (app closed or phone
    put away), or when the page locks itself (left the app / untouched), every
    page asks again at /unlock/: Face ID where turned on, otherwise the password.
    """

    OPEN_PATHS = ("/static/", "/healthz/", "/unlock/", "/logout/", "/login/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from urllib.parse import quote

        from django.http import JsonResponse
        from django.shortcuts import redirect

        from . import services

        try:
            applies = services.app_lock_applies(request)
        except DatabaseError:
            applies = False
        if not applies:
            return self.get_response(request)
        now = services.now_seconds()
        _away, _idle, gap = services.lock_timing()
        seen = request.session.get("app_seen_at")
        locked = request.session.get("app_locked") is True
        if not locked and type(seen) is int and now - seen > gap:
            services.lock(request)
            locked = True
        if locked and not request.path.startswith(self.OPEN_PATHS):
            wants_json = (
                "application/json" in request.headers.get("Accept", "")
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or "/api/" in request.path
                or request.method not in ("GET", "HEAD")
            )
            if wants_json:
                # 423 Locked, not 401/403: page scripts (chat, assistant) treat it
                # as a temporary failure and resume after unlocking instead of
                # assuming the access was revoked.
                return JsonResponse(
                    {
                        "error": "Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục.",
                        "locked": True,
                        "unlock": "/unlock/",
                    },
                    status=423,
                )
            return redirect(
                "/unlock/?next=" + quote(request.get_full_path(), safe="/?=&")
            )
        if not locked and (type(seen) is not int or now - seen >= 30):
            request.session["app_seen_at"] = now
        return self.get_response(request)

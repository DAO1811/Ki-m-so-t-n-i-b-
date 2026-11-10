import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import PasskeyCredential


def api(*, authenticated=False):
    def decorate(fn):
        @wraps(fn)
        @require_POST
        @never_cache
        @sensitive_post_parameters("password")
        def inner(request):
            if authenticated and not request.user.is_authenticated:
                return JsonResponse(
                    {"error": "Đăng nhập lại bằng mật khẩu trước khi quản lý passkey."},
                    status=401,
                )
            if not authenticated and request.user.is_authenticated:
                return JsonResponse(
                    {
                        "error": "Bạn đã đăng nhập. Hãy đăng xuất trước khi đổi tài khoản."
                    },
                    status=409,
                )
            try:
                if (
                    request.content_type != "application/json"
                    or len(request.body) > 24576
                ):
                    raise services.PasskeyError("Yêu cầu không hợp lệ.")
                data = json.loads(request.body)
                if not isinstance(data, dict):
                    raise services.PasskeyError()
                return JsonResponse(fn(request, data))
            except services.PasskeyError as exc:
                response = JsonResponse({"error": str(exc)}, status=exc.status)
                if exc.status == 429:
                    response["Retry-After"] = "60"
                return response
            except IntegrityError:
                return JsonResponse(
                    {
                        "error": "Không thể lưu passkey này. Hãy thử lại hoặc dùng mật khẩu."
                    },
                    status=400,
                )
            except DatabaseError:
                return JsonResponse(
                    {"error": "Passkey tạm thời chưa sẵn sàng. Hãy dùng mật khẩu."},
                    status=503,
                )
            except (ValueError, TypeError, KeyError, UnicodeError):
                return JsonResponse(
                    {"error": "Yêu cầu xác thực không hợp lệ."}, status=400
                )

        return inner

    return decorate


@login_required
@require_GET
@never_cache
def manage(request):
    return render(
        request,
        "passkeys/manage.html",
        {
            "credentials": PasskeyCredential.objects.filter(
                user=request.user, revoked_at__isnull=True
            ).order_by("-created_at"),
            "max_credentials": services.MAX_CREDENTIALS,
            "page_name": "Face ID / Windows Hello",
        },
    )


@api(authenticated=True)
def register_options(request, data):
    password = data.get("password", "")
    label = data.get("label", "")
    if (
        not isinstance(password, str)
        or len(password) > 1024
        or not isinstance(label, str)
        or not 1 <= len(label.strip()) <= 80
    ):
        raise services.PasskeyError(
            "Điền tên passkey (tối đa 80 ký tự) và mật khẩu xác nhận."
        )
    return services.register_options(request, password, label.strip())


@api(authenticated=True)
def register_verify(request, data):
    services.register_finish(request, data.get("ceremony_id"), data.get("credential"))
    return {"ok": True}


@api()
def login_options(request, data):
    return services.login_options(request, data.get("next", "/"))


@api()
def login_verify(request, data):
    return {
        "redirect": services.login_finish(
            request, data.get("ceremony_id"), data.get("credential")
        )
    }


@login_required
@require_POST
@never_cache
@sensitive_post_parameters("password")
def remove(request, pk):
    password = request.POST.get("password", "")
    try:
        if len(password) > 1024:
            raise services.PasskeyError("Mật khẩu xác nhận không hợp lệ.")
        services.revoke(request, pk, password)
    except services.PasskeyError as exc:
        if exc.status == 404:
            from django.http import Http404

            raise Http404() from None
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Đã thu hồi passkey. Các phiên đăng nhập bằng passkey này sẽ phải đăng nhập lại.",
        )
    return redirect("passkeys_manage")

import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import FaceProfile


@require_GET
@never_cache
def readiness(request):
    from django.conf import settings

    from .engine import configuration_ready

    ready = False
    if settings.CAMERA_IDENTITY_ENABLED:
        try:
            services.cipher()
            ready = configuration_ready()
        except services.CameraError:
            pass
    return JsonResponse(
        {
            "enabled": settings.CAMERA_IDENTITY_ENABLED,
            "configured": ready,
            **services.evaluation(),
        },
        status=200 if ready else 503,
    )


def api(authenticated=False):
    def decorate(function):
        @wraps(function)
        @require_POST
        @never_cache
        @sensitive_post_parameters("password", "frames")
        def view(request):
            if authenticated and not request.user.is_authenticated:
                return JsonResponse(
                    {"error": "Cần đăng nhập trước khi quản lý camera."}, status=401
                )
            try:
                if (
                    request.content_type != "application/json"
                    or len(request.body) > services.MAX_BODY
                ):
                    raise services.CameraError()
                data = json.loads(request.body)
                if not isinstance(data, dict):
                    raise services.CameraError()
                return JsonResponse(function(request, data))
            except services.CameraError as error:
                return JsonResponse(
                    {"error": str(error), **services.evaluation()}, status=error.status
                )
            except DatabaseError:
                return JsonResponse(
                    {
                        "error": "Bản đánh giá camera tạm thời chưa sẵn sàng.",
                        **services.evaluation(),
                    },
                    status=503,
                )
            except (ValueError, TypeError, KeyError, UnicodeError):
                return JsonResponse(
                    {"error": "Yêu cầu camera chưa hợp lệ.", **services.evaluation()},
                    status=400,
                )

        return view

    return decorate


@login_required
@require_GET
@never_cache
def manage(request):
    try:
        services.cipher()
    except services.CameraError as error:
        return JsonResponse({"error": str(error)}, status=error.status)
    return render(
        request,
        "camera_identity/manage.html",
        {
            "profile": FaceProfile.objects.filter(user=request.user).first(),
            "page_name": "Đánh giá camera khuôn mặt",
            "consent_version": services.CONSENT_VERSION,
        },
    )


@require_GET
@never_cache
def verify_page(request):
    try:
        services.cipher()
    except services.CameraError as error:
        return JsonResponse({"error": str(error)}, status=error.status)
    return render(request, "camera_identity/verify.html")


@api(authenticated=True)
def enroll_options(request, data):
    return services.options(
        request, "ENROLL", password=data.get("password"), consent=data.get("consent")
    )


@api(authenticated=True)
def enroll_verify(request, data):
    return services.finish(
        request, data.get("challenge_id"), data.get("frames"), "ENROLL"
    )


@api()
def verify_options(request, data):
    return services.options(request, "VERIFY", username=data.get("username"))


@api()
def verify_finish(request, data):
    return services.finish(
        request, data.get("challenge_id"), data.get("frames"), "VERIFY"
    )

import json

from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from inventory.access import has_function, is_admin

from .cloud_config import (
    MODEL,
    ORG_REQUESTS_DAY,
    USER_REQUESTS_DAY,
    configuration,
    is_enabled,
)
from .cloud_jobs import ChatError, require_chat, result_for, start
from .cloud_private import session_scope
from .context import require_use
from .models import ChatJob


def response(data, status=200):
    result = JsonResponse(data, status=status)
    result["Cache-Control"] = "private, no-store"
    result["Vary"] = "Cookie"
    return result


def denied_or_none(request):
    if not request.user.is_authenticated:
        return response({"error": "Đăng nhập lại để dùng Trợ lý AI."}, 401)
    return None


@require_GET
def cloud_status(request):
    if (denied := denied_or_none(request)) is not None:
        return denied
    require_use(request.user)
    conf = configuration()
    permitted = has_function(request.user, "assistant_chat")
    return response(
        {
            "permitted": permitted,
            "configured": is_enabled() if permitted else False,
            "admin": is_admin(request.user),
            "model": MODEL,
            "provider": "Groq Free",
            "key_present": bool(conf.key) if is_admin(request.user) else None,
            "free_zdr_confirmed": conf.confirmed if is_admin(request.user) else None,
            "requests_per_day": USER_REQUESTS_DAY,
            "organization_requests_per_day": ORG_REQUESTS_DAY,
        }
    )


@require_POST
def cloud_start(request):
    if (denied := denied_or_none(request)) is not None:
        return denied
    try:
        require_chat(request.user)
        if len(request.body) > 24000:
            raise ValueError("Câu hỏi hoặc lịch sử quá dài.")
        data = json.loads(request.body)
        result = start(request.user, session_scope(request), data)
        return response(result, 202 if result["kind"] == "job" else 200)
    except PermissionDenied as exc:
        return response({"error": str(exc)}, 403)
    except ChatError as exc:
        return response({"error": str(exc), "code": exc.code}, exc.status)
    except (ValueError, AttributeError, TypeError) as exc:
        return response(
            {
                "error": str(exc)
                if isinstance(exc, ValueError)
                and not isinstance(exc, json.JSONDecodeError)
                else "Câu hỏi hoặc ngữ cảnh không hợp lệ."
            },
            400,
        )


def own_job(request, pk):
    require_chat(request.user)
    job = get_object_or_404(
        ChatJob,
        pk=pk,
        owner_id=request.user.pk,
        session_scope=session_scope(request),
        expires_at__gt=timezone.now(),
    )
    if job.expires_at <= timezone.now():
        raise Http404
    return job


@require_GET
def cloud_result(request, pk):
    if (denied := denied_or_none(request)) is not None:
        return denied
    job = own_job(request, pk)
    try:
        return response(result_for(job))
    except ValueError:
        return response(
            {"error": "Cuộc trò chuyện đã hết hạn. Hãy bắt đầu cuộc trao đổi mới."}, 410
        )


@require_POST
def cloud_cancel(request, pk):
    if (denied := denied_or_none(request)) is not None:
        return denied
    job = own_job(request, pk)
    ChatJob.objects.filter(pk=job.pk, state__in=["PENDING", "RUNNING"]).update(
        state="CANCELLED", error="cancelled"
    )
    return response({"cancelled": True})

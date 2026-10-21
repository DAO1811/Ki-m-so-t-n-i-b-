import json
from datetime import timedelta

import psycopg
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import caches
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from . import drive
from .drive_views import require_owner
from .models import DriveConnection
from .storage_audit import cache_key, measure_storage
from .storage_reports import export_month

cache = caches["storage"]


def private(response):
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
def storage_settings(request):
    require_owner(request.user)
    # Refresh on demand: simply visiting this page never contacts Google, scans
    # binary objects or writes any report on Drive.
    audit = cache.get(cache_key())
    return private(
        render(
            request,
            "storage_settings.html",
            {
                "audit": audit,
                "measured_at": parse_datetime(audit["measured_at"]) if audit else None,
                "connection": DriveConnection.objects.first(),
                "last_month": (
                    timezone.localdate().replace(day=1) - timedelta(days=1)
                ).strftime("%Y-%m"),
                "drive_usage": cache.get(cache_key() + ":drive"),
                "last_report": cache.get(cache_key() + ":report"),
            },
        )
    )


@login_required
@require_POST
def storage_measure(request):
    require_owner(request.user)
    try:
        measure_storage()
        messages.success(
            request, "Đã đo dung lượng thực tế. Chưa xóa hoặc di chuyển dữ liệu."
        )
    except DatabaseError:
        messages.error(
            request,
            "Chưa đo được dung lượng trong thời gian cho phép. Hoạt động kho giữ nguyên; có thể thử lại sau.",
        )
    return private(redirect("storage_settings"))


@login_required
@require_GET
def storage_download(request):
    require_owner(request.user)
    report = cache.get(cache_key())
    if report is None:
        messages.warning(request, "Bấm kiểm tra dung lượng trước khi tải báo cáo.")
        return private(redirect("storage_settings"))
    response = HttpResponse(
        json.dumps(report, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="bao-cao-dung-luong.json"'
    return private(response)


@login_required
@require_POST
def storage_drive_usage(request):
    require_owner(request.user)
    try:
        configured = DriveConnection.objects.first()
        if not configured:
            raise ValidationError("Kết nối Google Drive trước khi kiểm tra dung lượng.")
        result = drive.google_request(
            "https://www.googleapis.com/drive/v3/about?fields=storageQuota,user(emailAddress)",
            token=drive.access_token(configured),
        )
        if result.get("user", {}).get("emailAddress") != configured.account_email:
            raise ValidationError(
                "Tài khoản Google không khớp kết nối công ty. Cần kết nối lại."
            )
        quota = result.get("storageQuota", {})
        limit = int(quota["limit"]) if "limit" in quota else None
        used = int(quota["usage"]) if "usage" in quota else None
        cache.set(
            cache_key() + ":drive",
            {
                "limit": limit,
                "used": used,
                "remaining": max(limit - used, 0)
                if limit is not None and used is not None
                else None,
            },
            600,
        )
        messages.success(
            request, "Đã kiểm tra hạn mức tài khoản Google. Chưa tạo hoặc xóa tệp."
        )
    except (ValidationError, ValueError, TypeError):
        messages.error(
            request,
            "Chưa đọc được hạn mức Google. Kiểm tra kết nối; không ảnh hưởng việc quản lý kho.",
        )
    return private(redirect("storage_settings"))


@login_required
@require_POST
def storage_export(request):
    require_owner(request.user)
    try:
        report = export_month(request.POST.get("period", ""))
        cache.set(cache_key() + ":report", report, 3600)
        messages.success(
            request,
            "Đã tạo hoặc kiểm tra lại báo cáo Google Sheets; số liệu đọc lại khớp bản xuất. Dữ liệu gốc giữ nguyên.",
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    except (DatabaseError, psycopg.Error):
        messages.error(
            request,
            "Chưa hoàn tất báo cáo. Dữ liệu kho giữ nguyên; thử lại sẽ kiểm tra bản đã tạo để tránh nhân đôi.",
        )
    return private(redirect("storage_settings"))

import secrets
import time
import urllib.parse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import DriveConnection, StoredFile
from . import drive


def require_owner(user):
    if not user.is_active or not user.is_superuser:
        raise PermissionDenied("Chỉ quản trị viên được kết nối kho lưu trữ công ty.")


def callback_url(request):
    return request.build_absolute_uri(reverse("drive_callback"))


@login_required
def drive_settings(request):
    require_owner(request.user)
    missing = [
        name
        for name in [
            "GOOGLE_DRIVE_CLIENT_ID",
            "GOOGLE_DRIVE_CLIENT_SECRET",
            "GOOGLE_PICKER_API_KEY",
            "GOOGLE_CLOUD_PROJECT_NUMBER",
        ]
        if not getattr(settings, name)
    ]
    return render(
        request,
        "drive_settings.html",
        {
            "connection": DriveConnection.objects.first(),
            "missing": missing,
            "callback_url": callback_url(request),
            "picker_config": {
                "key": settings.GOOGLE_PICKER_API_KEY,
                "appId": settings.GOOGLE_CLOUD_PROJECT_NUMBER,
            },
            "root_folder": settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID,
            "provider": settings.PRIVATE_MEDIA_PROVIDER,
        },
    )


@login_required
@require_POST
def drive_connect(request):
    require_owner(request.user)
    if not settings.GOOGLE_DRIVE_CLIENT_ID or not settings.GOOGLE_DRIVE_CLIENT_SECRET:
        messages.error(
            request,
            "Cần cấu hình ứng dụng Google trước. Không gửi bí mật vào trò chuyện.",
        )
        return redirect("drive_settings")
    state = secrets.token_urlsafe(32)
    request.session["drive_oauth"] = {
        "state": state,
        "created": time.time(),
        "user": request.user.pk,
    }
    params = {
        "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
        "redirect_uri": callback_url(request),
        "response_type": "code",
        "scope": drive.SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return redirect(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    )


@login_required
def drive_callback(request):
    require_owner(request.user)
    pending = request.session.pop("drive_oauth", None)
    if (
        not pending
        or not secrets.compare_digest(
            pending.get("state", ""), request.GET.get("state", "")
        )
        or pending["user"] != request.user.pk
        or time.time() - pending["created"] > 600
    ):
        messages.error(
            request, "Phiên kết nối Google không hợp lệ hoặc hết hạn. Hãy kết nối lại."
        )
        return redirect("drive_settings")
    if request.GET.get("error") or not request.GET.get("code"):
        messages.error(request, "Google chưa cấp quyền; kết nối cũ không thay đổi.")
        return redirect("drive_settings")
    try:
        data = drive.exchange_token(
            {
                "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
                "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
                "code": request.GET["code"],
                "redirect_uri": callback_url(request),
                "grant_type": "authorization_code",
            }
        )
        token = data.get("access_token")
        if not token or drive.SCOPE not in data.get("scope", "").split():
            raise ValidationError(
                "Google chưa cấp quyền tệp cần thiết. Hãy kết nối lại."
            )
        about = drive.google_request(
            "https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)",
            token=token,
        )
        email = about.get("user", {}).get("emailAddress", "")
        if not email:
            raise ValidationError("Không xác định được tài khoản lưu trữ.")
        with transaction.atomic():
            old = DriveConnection.objects.select_for_update().first()
            if (
                old
                and old.account_email != email
                and StoredFile.objects.filter(provider="drive").exists()
            ):
                raise ValidationError(
                    "Đã có hồ sơ. Không đổi tài khoản Drive khi chưa có kế hoạch chuyển dữ liệu."
                )
            refresh = data.get("refresh_token")
            if not refresh and (not old or old.account_email != email):
                raise ValidationError(
                    "Chưa có quyền truy cập dài hạn. Hãy kết nối lại và đồng ý lưu trữ."
                )
            encrypted = (
                drive.token_cipher().encrypt(refresh.encode()).decode()
                if refresh
                else old.encrypted_refresh_token
            )
            DriveConnection.objects.update_or_create(
                pk=1,
                defaults={
                    "account_email": email,
                    "encrypted_refresh_token": encrypted,
                    "connected_by": request.user,
                },
            )
        messages.success(
            request,
            "Đã kết nối Google. Tiếp theo chọn đúng thư mục đã chỉ định qua bộ chọn Google.",
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("drive_settings")


@login_required
@require_POST
def drive_picker_token(request):
    require_owner(request.user)
    try:
        response = JsonResponse({"access_token": drive.access_token()})
    except ValidationError as exc:
        response = JsonResponse({"error": " ".join(exc.messages)}, status=400)
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
def drive_folder(request):
    require_owner(request.user)
    try:
        drive.choose_folder(request.POST.get("folder_id", ""))
        messages.success(
            request,
            "Đã chọn thư mục. Phần mềm sẽ tự tạo thư mục con khi bạn tải hồ sơ đầu tiên.",
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("drive_settings")

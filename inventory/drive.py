"""Owner OAuth with drive.file scope and Google Picker, restricted to selected folder."""

import base64
import hashlib
import json
import urllib.request
import urllib.parse
import urllib.error
from uuid import uuid4
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import DriveConnection

SCOPE = "https://www.googleapis.com/auth/drive.file"
API = "https://www.googleapis.com/drive/v3/files"


def token_cipher():
    key = hashlib.sha256(("dhd-drive-v1:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def google_request(
    url,
    *,
    method="GET",
    payload=None,
    token=None,
    content_type="application/json",
    binary=False,
):
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = (
        payload
        if isinstance(payload, bytes)
        else json.dumps(payload).encode()
        if payload is not None
        else None
    )
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=headers, method=method),
            timeout=30,
        ) as response:
            raw = response.read((8 * 1024 * 1024 + 1) if binary else (1024 * 1024 + 1))
            if len(raw) > (8 * 1024 * 1024 if binary else 1024 * 1024):
                raise ValueError("Response too large")
            return raw if binary else json.loads(raw or "{}")
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        ValueError,
    ) as exc:
        # Never echo Google's request/token/error body into user messages or logs.
        raise ValidationError(
            "Google Drive chưa phản hồi hoặc từ chối quyền / dung lượng. Tệp chưa được xác nhận lưu; kiểm tra kết nối rồi thử lại."
        ) from exc


def exchange_token(fields):
    return google_request(
        "https://oauth2.googleapis.com/token",
        method="POST",
        payload=urllib.parse.urlencode(fields).encode(),
        content_type="application/x-www-form-urlencoded",
    )


def access_token(connection=None):
    connection = connection or DriveConnection.objects.first()
    if (
        not connection
        or not settings.GOOGLE_DRIVE_CLIENT_ID
        or not settings.GOOGLE_DRIVE_CLIENT_SECRET
    ):
        raise ValidationError(
            "Quản trị viên cần kết nối Google Drive trước khi lưu tệp."
        )
    cache_key = (
        "drive-token:"
        + hashlib.sha256(connection.encrypted_refresh_token.encode()).hexdigest()
    )
    cached = cache.get(cache_key)
    if cached:
        return cached
    try:
        refresh = (
            token_cipher().decrypt(connection.encrypted_refresh_token.encode()).decode()
        )
    except InvalidToken as exc:
        raise ValidationError(
            "Không giải mã được kết nối Drive. Quản trị viên cần kết nối lại; không đổi SECRET_KEY khi chưa chuyển khóa."
        ) from exc
    data = exchange_token(
        {
            "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
            "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        }
    )
    token = data.get("access_token")
    if not token:
        raise ValidationError(
            "Kết nối Google hết hiệu lực; quản trị viên cần kết nối lại."
        )
    cache.set(cache_key, token, max(1, int(data.get("expires_in", 3600)) - 90))
    return token


@transaction.atomic
def choose_folder(folder_id):
    if folder_id != settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID:
        raise ValidationError("Chỉ chọn đúng thư mục gốc mà chủ dự án đã chỉ định.")
    if (
        not folder_id
        or len(folder_id) > 150
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in folder_id
        )
    ):
        raise ValidationError("Mã thư mục Drive không hợp lệ.")
    from .models import MediaQuota

    MediaQuota.objects.get_or_create(pk=1)
    MediaQuota.objects.select_for_update().get(pk=1)
    connection = DriveConnection.objects.select_for_update().first()
    token = access_token(connection)
    meta = google_request(
        API
        + "/"
        + folder_id
        + "?fields=id,name,mimeType,trashed,ownedByMe,capabilities(canAddChildren)",
        token=token,
    )
    if (
        meta.get("mimeType") != "application/vnd.google-apps.folder"
        or meta.get("trashed")
        or not meta.get("ownedByMe")
        or not meta.get("capabilities", {}).get("canAddChildren")
    ):
        raise ValidationError(
            "Chọn thư mục do tài khoản Google của bạn sở hữu và có quyền thêm tệp."
        )
    from .models import StoredFile

    if (
        connection.folder_id
        and connection.folder_id != folder_id
        and StoredFile.objects.filter(provider="drive").exists()
    ):
        raise ValidationError(
            "Đã có hồ sơ trong thư mục hiện tại. Cần kế hoạch chuyển dữ liệu trước khi đổi thư mục gốc."
        )
    connection.folder_id, connection.folder_name = folder_id, meta["name"][:200]
    connection.save(update_fields=["folder_id", "folder_name"])


def folder(token, parent, name, key):
    query = f"'{parent}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and appProperties has {{ key='dhd_key' and value='{key}' }}"
    result = google_request(
        API
        + "?"
        + urllib.parse.urlencode({"q": query, "fields": "files(id)", "pageSize": 1}),
        token=token,
    )
    if result.get("files"):
        return result["files"][0]["id"]
    return google_request(
        API,
        token=token,
        method="POST",
        payload={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent],
            "appProperties": {"dhd_key": key},
        },
    )["id"]


@transaction.atomic
def upload(content, content_type, sha, context, filename):
    connection = DriveConnection.objects.select_for_update().first()
    if not connection or not connection.folder_id:
        raise ValidationError(
            "Chưa chọn thư mục Drive. Quản trị viên cần kết nối và chọn thư mục trước."
        )
    token = access_token(connection)
    if context["kind"] == "product":
        parent = folder(token, connection.folder_id, "Hàng hóa", "products")
        parent = folder(token, parent, context["name"], "product-" + context["key"])
    else:
        parent = folder(token, connection.folder_id, "Hóa đơn", "receipts")
        parent = folder(token, parent, context["year"], "year-" + context["year"])
        parent = folder(token, parent, context["name"], "receipt-" + context["key"])
    query = f"'{parent}' in parents and trashed=false and appProperties has {{ key='dhd_sha256' and value='{sha}' }}"
    found = google_request(
        API
        + "?"
        + urllib.parse.urlencode(
            {"q": query, "fields": "files(id,size)", "pageSize": 1}
        ),
        token=token,
    )
    if found.get("files"):
        candidate = found["files"][0]
        if int(candidate.get("size", 0)) != len(content):
            raise ValidationError(
                "Tệp cùng mã đối chiếu trên Drive có kích thước khác. Cần kiểm tra hồ sơ gốc."
            )
        return candidate["id"]
    boundary = "dhd-" + uuid4().hex
    metadata = {
        "name": filename,
        "parents": [parent],
        "appProperties": {"dhd_sha256": sha},
    }
    body = (
        (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            + json.dumps(metadata, ensure_ascii=False)
            + f"\r\n--{boundary}\r\nContent-Type: {content_type}\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    result = google_request(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,size",
        method="POST",
        token=token,
        payload=body,
        content_type="multipart/related; boundary=" + boundary,
    )
    if not result.get("id") or int(result.get("size", -1)) != len(content):
        raise ValidationError(
            "Drive chưa xác nhận đủ kích thước tệp. Hãy thử lại; phần mềm sẽ tìm tệp cùng mã đối chiếu để tránh nhân đôi."
        )
    return result["id"]


def download(file):
    content = google_request(
        API + "/" + file.drive_id + "?alt=media", token=access_token(), binary=True
    )
    if len(content) != file.size or hashlib.sha256(content).hexdigest() != file.sha256:
        raise ValidationError(
            "Tệp trên Drive đã thay đổi so với bản lưu ban đầu. Cần đối chiếu / khôi phục bản gốc."
        )
    return content

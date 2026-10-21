"""Bounded monthly management reports. No ledger rows are moved or deleted.

Google Drive converts a text-typed XLSX to a native Sheet under drive.file.
The Sheet must round-trip with exactly the same cells before it is verified.
This is a reporting copy, never a backup or the source of inventory balances.
"""

import hashlib
import json
import re
import threading
import urllib.parse
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from . import drive
from .models import (
    Balance,
    Document,
    DriveConnection,
    LoanHolding,
    Movement,
    StocktakeItem,
)
from .release_backup import direct_connection

SHEET_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_ROWS = 25000
MAX_BYTES = 5 * 1024 * 1024
LOCAL_LOCK = threading.Lock()


def period_dates(period):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", period or ""):
        raise ValidationError("Chọn tháng báo cáo theo dạng YYYY-MM.")
    try:
        start = date.fromisoformat(period + "-01")
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    except ValueError:
        raise ValidationError("Tháng báo cáo không hợp lệ.") from None
    if end > timezone.localdate().replace(day=1):
        raise ValidationError(
            "Chỉ xuất tháng đã kết thúc; số tồn hiện tại vẫn được xem trong phần mềm."
        )
    zone = timezone.get_current_timezone()
    return tuple(
        timezone.make_aware(datetime.combine(d, time.min), zone) for d in (start, end)
    )


def text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return timezone.localtime(value).isoformat()
    return str(value)


def digest_rows(sheets):
    return hashlib.sha256(
        json.dumps(sheets, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def workbook_bytes(sheets):
    book = Workbook()
    book.remove(book.active)
    for name, rows in sheets:
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append([text(value) for value in row])
        # Explicit string cells prevent formulas and preserve leading-zero codes
        # and exact decimals during Sheets conversion (no double rounding).
        for row in sheet:
            for cell in row:
                cell.data_type = "s"
                cell.number_format = "@"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="795715")
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                48, max(18, max(len(text(c.value)) for c in column[:60]) + 2)
            )
    buffer = BytesIO()
    book.save(buffer)
    payload = buffer.getvalue()
    if len(payload) > MAX_BYTES:
        raise ValidationError(
            "Báo cáo vượt 5 MB. Chưa xuất dữ liệu; cần chia kỳ báo cáo trước khi thực hiện."
        )
    return payload


def build_report(period):
    start, end = period_dates(period)
    sheets = []
    remaining = MAX_ROWS

    def add(name, headers, rows):
        nonlocal remaining
        result = [[text(value) for value in headers]]
        for row in rows:
            remaining -= 1
            if remaining < 0:
                raise ValidationError(
                    "Báo cáo vượt 25.000 dòng. Chưa xuất dữ liệu; cần chia kỳ báo cáo trước khi thực hiện."
                )
            values = [text(value) for value in row]
            if any(len(value) > 32000 for value in values):
                raise ValidationError(
                    "Có nội dung quá dài để lưu nguyên vẹn trên báo cáo. Chưa xuất dữ liệu."
                )
            result.append(values)
        sheets.append([name, result])

    # Read all source tables at one consistent point. Google I/O happens AFTER
    # this transaction; no warehouse locks are held while talking to Drive.
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                cursor.execute("SET LOCAL statement_timeout = '8s'")
        generated = timezone.now()
        add(
            "Thong tin",
            ["Mục", "Nội dung"],
            [
                [
                    "Loại báo cáo",
                    "Bản tra cứu quản trị; không phải bản sao lưu để phục hồi hệ thống",
                ],
                ["Kỳ giao dịch", period],
                ["Thời điểm xuất", generated],
                ["Múi giờ", str(timezone.get_current_timezone())],
                [
                    "Giao dịch",
                    "Theo thời điểm ghi nhận từng biến động thực tế; có cả chặng chuyển kho đã xuất nhưng chưa nhận",
                ],
                [
                    "Tồn, mượn và trạng thái kiểm kê",
                    "Tại thời điểm xuất; không phải số dư cuối tháng",
                ],
                [
                    "Mã và số tiền",
                    "Lưu dạng văn bản để giữ số 0 đầu mã và độ chính xác số tiền",
                ],
                [
                    "Phạm vi",
                    "Toàn bộ kho; không xuất tài khoản, bí mật kết nối, tin nhắn hoặc tệp riêng tư",
                ],
            ],
        )
        journal = []
        totals = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
        doc_ids = set()
        for item in (
            Movement.objects.filter(created_at__gte=start, created_at__lt=end)
            .select_related("warehouse", "product", "document")
            .order_by("id")
            .iterator(chunk_size=500)
        ):
            if len(journal) >= MAX_ROWS:
                raise ValidationError(
                    "Kỳ giao dịch vượt giới hạn báo cáo. Chưa xuất dữ liệu."
                )
            doc_ids.add(item.document_id)
            # Movement is authoritative for executed transfer legs and quantities.
            key = (item.warehouse.code, item.warehouse.name)
            row = totals[key]
            row[0] += max(item.delta, 0)
            row[1] += max(-item.delta, 0)
            row[2] += item.delta
            row[3] += item.value_delta
            journal.append(
                [
                    item.pk,
                    item.created_at,
                    item.document_id,
                    item.document.get_kind_display(),
                    item.warehouse.code,
                    item.product.sku,
                    item.product.name,
                    item.product.unit,
                    item.delta,
                    item.value_delta,
                    item.balance_after,
                    item.value_after,
                ]
            )
        add(
            "Tong hop giao dich",
            [
                "Mã kho",
                "Tên kho",
                "SL tăng",
                "SL giảm",
                "SL ròng",
                "Giá trị biến động ròng",
            ],
            ([*key, *values] for key, values in sorted(totals.items())),
        )
        add(
            "Nhat ky kho",
            [
                "ID biến động",
                "Thời điểm ghi nhận",
                "ID phiếu",
                "Loại phiếu",
                "Mã kho",
                "Mã hàng hiện tại",
                "Tên hiện tại",
                "ĐVT hiện tại",
                "SL biến động",
                "Giá trị biến động",
                "Tồn sau biến động",
                "Giá trị sau biến động",
            ],
            journal,
        )
        add(
            "Phieu lien quan",
            [
                "ID phiếu",
                "Loại",
                "Ngày nghiệp vụ",
                "Trạng thái khi xuất báo cáo",
                "Kho xuất",
                "Kho nhập",
                "Số chứng từ",
                "Nhà cung cấp / đối tác",
                "Lý do",
            ],
            (
                [
                    doc.pk,
                    doc.get_kind_display(),
                    doc.business_date,
                    doc.get_status_display(),
                    doc.source.code if doc.source_id else "",
                    doc.destination.code if doc.destination_id else "",
                    doc.reference_number,
                    doc.counterparty,
                    doc.note,
                ]
                for doc in Document.objects.filter(pk__in=doc_ids)
                .select_related("source", "destination")
                .order_by("id")
                .iterator(chunk_size=500)
            ),
        )
        add(
            "Ton tai thoi diem xuat",
            ["Mã kho", "Mã hàng", "Tên hàng", "ĐVT", "SL khả dụng", "Giá trị khả dụng"],
            (
                [
                    item.warehouse.code,
                    item.product.sku,
                    item.product.name,
                    item.product.unit,
                    item.quantity,
                    item.value,
                ]
                for item in Balance.objects.select_related("warehouse", "product")
                .order_by("warehouse__code", "product__sku")
                .iterator(chunk_size=500)
            ),
        )
        add(
            "Muon tai thoi diem xuat",
            [
                "ID phiếu mượn",
                "Kho cho mượn",
                "Kho nhận",
                "Mã hàng",
                "Tên hàng",
                "SL còn giữ",
                "Giá trị còn giữ",
            ],
            (
                [
                    item.loan_line.document_id,
                    item.loan_line.document.source.code
                    if item.loan_line.document.source_id
                    else "",
                    item.loan_line.document.destination.code
                    if item.loan_line.document.destination_id
                    else "",
                    item.loan_line.product.sku,
                    item.loan_line.product.name,
                    item.quantity,
                    item.value,
                ]
                for item in LoanHolding.objects.filter(quantity__gt=0)
                .select_related(
                    "loan_line__document__source",
                    "loan_line__document__destination",
                    "loan_line__product",
                )
                .order_by("id")
                .iterator(chunk_size=500)
            ),
        )
        add(
            "Kiem ke trong ky",
            [
                "ID kiểm kê",
                "Ngày chốt",
                "Kho",
                "Trạng thái khi xuất báo cáo",
                "ID điều chỉnh",
                "Mã hàng lúc chốt",
                "Tên lúc chốt",
                "ĐVT lúc chốt",
                "SL sổ sách",
                "SL đã đếm",
                "Chênh lệch đếm",
                "Lý do",
            ],
            (
                [
                    item.session_id,
                    item.session.business_date,
                    item.session.warehouse.code,
                    item.session.workflow_status,
                    item.session.document_id,
                    item.sku_snapshot,
                    item.name_snapshot,
                    item.unit_snapshot,
                    item.book_quantity,
                    item.counted_quantity,
                    item.difference,
                    item.note,
                ]
                for item in StocktakeItem.objects.filter(
                    session__business_date__gte=start.date(),
                    session__business_date__lt=end.date(),
                )
                .select_related("session__warehouse", "session__document")
                .order_by("session_id", "id")
                .iterator(chunk_size=500)
            ),
        )
    payload = workbook_bytes(sheets)
    return payload, {
        "sha256": digest_rows(sheets),
        "rows": str(MAX_ROWS - remaining),
        "period": period,
    }


@contextmanager
def export_lock(period):
    """Serialize retries across gunicorn processes, including lost HTTP responses."""
    key = int.from_bytes(
        hashlib.sha256(("dhd-report-v1:" + period).encode()).digest()[:8],
        "big",
        signed=True,
    )
    if connection.vendor == "postgresql":
        with direct_connection() as db:
            locked = db.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()[0]
            if not locked:
                raise ValidationError(
                    "Đang xuất báo cáo tháng này. Chờ hoàn tất rồi tải lại danh sách."
                )
            try:
                yield
            finally:
                db.execute("SELECT pg_advisory_unlock(%s)", (key,))
    else:
        if not LOCAL_LOCK.acquire(blocking=False):
            raise ValidationError("Đang xuất báo cáo. Vui lòng chờ.")
        try:
            yield
        finally:
            LOCAL_LOCK.release()


def report_connection():
    configured = DriveConnection.objects.first()
    if not configured or not configured.folder_id:
        raise ValidationError(
            "Kết nối và chọn thư mục Google Drive trước khi xuất báo cáo."
        )
    if configured.folder_id != settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID:
        raise ValidationError(
            "Thư mục Drive khác thư mục công ty đã chỉ định. Cần kiểm tra lại kết nối."
        )
    return configured, drive.access_token(configured)


def metadata_url(file_id):
    # IDs come only from Google API, never from user-entered links.
    return drive.API + "/" + urllib.parse.quote(file_id, safe="")


def verify_sheet(file, token):
    properties = file.get("appProperties", {})
    expected = properties.get("dhd_sha256", "")
    if (
        not re.fullmatch("[0-9a-f]{64}", expected)
        or file.get("mimeType") != SHEET_MIME
        or file.get("trashed")
    ):
        raise ValidationError(
            "Báo cáo thiếu thông tin đối soát hoặc không còn hợp lệ. Không thay đổi dữ liệu gốc."
        )
    payload = drive.google_request(
        metadata_url(file["id"])
        + "/export?"
        + urllib.parse.urlencode({"mimeType": XLSX_MIME}),
        token=token,
        binary=True,
    )
    if len(payload) > MAX_BYTES:
        raise ValidationError(
            "Bản báo cáo đọc lại vượt giới hạn kiểm tra. Chưa xác nhận thành công."
        )
    try:
        with ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > 100
                or sum(item.file_size for item in entries) > 32 * 1024 * 1024
            ):
                raise ValueError("Uncompressed report exceeds verification budget")
        book = load_workbook(BytesIO(payload), read_only=True, data_only=False)
        sheets = []
        row_count = 0
        for sheet in book:
            rows = []
            # Ignore formatting-only trailing cells without discarding data.
            if sheet.max_column > 20 or sheet.max_row > MAX_ROWS + 30:
                raise ValueError("Unexpected shape")
            for row in sheet.iter_rows():
                if any(cell.data_type == "f" for cell in row):
                    raise ValueError("Formula in verified reporting copy")
                rows.append([text(cell.value) for cell in row])
                row_count += 1
                if row_count > MAX_ROWS + 50:
                    raise ValueError("Too many rows")
            sheets.append([sheet.title, rows])
        book.close()
        if digest_rows(sheets) != expected:
            raise ValueError("Mismatched cells")
    except Exception as exc:
        # Do not leak workbook contents, business notes, or Google responses.
        raise ValidationError(
            "Số liệu đọc lại từ Google Sheets không khớp bản xuất. Báo cáo chưa được xác nhận; dữ liệu trong phần mềm giữ nguyên."
        ) from exc
    updated = drive.google_request(
        metadata_url(file["id"]) + "?fields=id,mimeType,appProperties,modifiedTime",
        method="PATCH",
        token=token,
        payload={"appProperties": {**properties, "dhd_state": "verified"}},
    )
    return {
        "id": updated["id"],
        "period": properties["dhd_period"],
        "rows": properties["dhd_rows"],
        "state": "verified",
        "url": "https://docs.google.com/spreadsheets/d/"
        + urllib.parse.quote(updated["id"], safe="")
        + "/edit",
    }


def export_month(period):
    period_dates(period)
    with export_lock(period):
        configured, token = report_connection()
        # This refresh validates the account/root; it does not change permissions.
        drive.check_connection()
        token = drive.access_token(configured)
        parent = drive.folder(
            token, configured.folder_id, "Báo cáo quản trị", "management-reports"
        )
        parent = drive.folder(token, parent, period[:4], "reports-year-" + period[:4])
        key = "monthly-v1-" + period
        query = f"'{parent}' in parents and trashed=false and appProperties has {{ key='dhd_report' and value='{key}' }}"
        found = drive.google_request(
            drive.API
            + "?"
            + urllib.parse.urlencode(
                {
                    "q": query,
                    "fields": "files(id,mimeType,appProperties)",
                    "pageSize": 2,
                }
            ),
            token=token,
        ).get("files", [])
        if len(found) > 1:
            raise ValidationError(
                "Có nhiều bản báo cáo cùng tháng. Cần đối soát trước khi xuất tiếp."
            )
        if found:
            # Verify again even if a previous request succeeded: manual changes
            # in Sheets must never silently become the original report.
            return verify_sheet(found[0], token)
        payload, summary = build_report(period)
        boundary = "dhd-report-" + uuid4().hex
        properties = {
            "dhd_report": key,
            "dhd_period": period,
            "dhd_rows": summary["rows"],
            "dhd_sha256": summary["sha256"],
            "dhd_state": "pending",
        }
        metadata = {
            "name": "Báo cáo kho " + period,
            "parents": [parent],
            "mimeType": SHEET_MIME,
            "appProperties": properties,
        }
        body = (
            (
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                + json.dumps(metadata, ensure_ascii=False)
                + f"\r\n--{boundary}\r\nContent-Type: {XLSX_MIME}\r\n\r\n"
            ).encode()
            + payload
            + f"\r\n--{boundary}--\r\n".encode()
        )
        result = drive.google_request(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,mimeType,appProperties",
            method="POST",
            token=token,
            payload=body,
            content_type="multipart/related; boundary=" + boundary,
        )
        if not result.get("id"):
            raise ValidationError(
                "Google chưa xác nhận tạo báo cáo. Thử lại để tìm bản đã tạo, tránh nhân đôi."
            )
        return verify_sheet(result, token)

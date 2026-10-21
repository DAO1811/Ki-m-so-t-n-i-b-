"""Receive existing goods from one Excel file, separated into warehouse drafts."""

import time
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .access import require_function
from .excel import normalized_receipt_download, parse_receipt
from .forms import ReceiptImportForm
from .models import Document, Line, Product, Warehouse
from .services import audit_document, capture_lines, validate_document, warehouses_for


def document_details(preview):
    return {
        key: date.fromisoformat(value)
        if key in {"business_date", "reference_date", "due_date"} and value
        else value
        for key, value in preview["details"].items()
    }


def resolve_rows(rows, user, default_warehouse=None):
    allowed = {warehouse.code: warehouse for warehouse in warehouses_for(user)}
    allowed_ids = {warehouse.pk for warehouse in allowed.values()}
    groups = {}
    seen = set()
    for row in rows:
        code = row.get("warehouse_code", "")
        warehouse = allowed.get(code) if code else default_warehouse
        if warehouse is None or warehouse.pk not in allowed_ids:
            raise ValidationError(
                f"Dòng {row['row_number']}: điền ma_kho hợp lệ trong phạm vi được cấp, hoặc chọn Kho nhận chung."
            )
        identity = warehouse.pk, row["product_id"]
        if identity in seen:
            raise ValidationError(
                f"Dòng {row['row_number']}: mã {row['sku']} lặp tại cùng kho {warehouse.code}; gộp số lượng vào một dòng."
            )
        seen.add(identity)
        row.update(warehouse_id=warehouse.pk, warehouse_name=str(warehouse))
        group = groups.setdefault(
            warehouse.pk,
            {
                "warehouse_id": warehouse.pk,
                "warehouse_name": str(warehouse),
                "rows": 0,
                "amount": Decimal(0),
            },
        )
        group["rows"] += 1
        group["amount"] += Decimal(row["amount"])
    return [
        dict(group, amount=str(group["amount"]), documents=(group["rows"] + 49) // 50)
        for group in groups.values()
    ]


def current_preview(request):
    preview = request.session.get("receipt_import")
    if (
        not preview
        or preview.get("owner") != request.user.pk
        or not 0 <= time.time() - preview.get("created_at", 0) <= 1800
    ):
        return None
    return preview


def batch_redirect(result):
    ids = result["document_ids"]
    if len(ids) == 1:
        return redirect("document_detail", pk=ids[0])
    return redirect(reverse("documents") + "?kind=IN&import_batch=" + result["key"])


@transaction.atomic
def confirm_receipts(user, preview):
    actor = get_user_model().objects.select_for_update().get(pk=user.pk)
    require_function(actor, "receipts_create")
    if preview["details"].get("business_date") != str(timezone.localdate()):
        raise ValidationError(
            "Bản xem trước đã sang ngày khác. Hãy tải lại để tạo phiếu ngày hôm nay."
        )
    rows = preview["rows"]
    warehouse_ids = {row["warehouse_id"] for row in rows}
    authorized_ids = set(
        warehouses_for(actor).filter(pk__in=warehouse_ids).values_list("pk", flat=True)
    )
    if warehouse_ids != authorized_ids:
        raise ValidationError(
            "Quyền tại kho đã thay đổi. Chưa tạo phiếu nào; hãy kiểm tra lại."
        )
    warehouses = {
        w.pk: w
        for w in Warehouse.objects.select_for_update()
        .filter(pk__in=warehouse_ids)
        .order_by("pk")
    }
    products = {
        p.pk: p
        for p in Product.objects.select_for_update()
        .filter(pk__in={row["product_id"] for row in rows})
        .order_by("pk")
    }
    groups = defaultdict(list)
    for row in rows:
        warehouse = warehouses[row["warehouse_id"]]
        product = products.get(row["product_id"])
        if row.get("warehouse_code") and warehouse.code != row["warehouse_code"]:
            raise ValidationError("Mã kho đã thay đổi sau xem trước. Hãy tải lại file.")
        if product is None or product.sku != row["sku"] or product.unit != row["unit"]:
            raise ValidationError(
                "Danh mục hoặc đơn vị tính đã thay đổi. Hãy tải lại file."
            )
        groups[warehouse.pk].append(row)
    expected_keys = []
    documents = []
    details = document_details(preview)
    for warehouse_id, group in groups.items():
        for offset in range(0, len(group), 50):
            key = (
                preview["key"]
                if not expected_keys
                else str(
                    uuid5(
                        NAMESPACE_URL,
                        f"receipt-import:{actor.pk}:{preview['key']}:{warehouse_id}:{offset}",
                    )
                )
            )
            expected_keys.append(key)
            doc = Document(
                kind="IN",
                destination=warehouses[warehouse_id],
                created_by=actor,
                note=preview["note"],
                import_key=key,
                **details,
            )
            validate_document(doc)
            existing = Document.objects.filter(import_key=key).first()
            if existing is not None:
                if (
                    existing.created_by_id != actor.pk
                    or existing.kind != "IN"
                    or existing.destination_id != warehouse_id
                ):
                    raise ValidationError(
                        "Lượt nhập đã được sử dụng. Hãy tải lại file."
                    )
                documents.append(existing)
                continue
            doc.save()
            Line.objects.bulk_create(
                capture_lines(
                    doc,
                    [
                        Line(
                            document=doc,
                            product=products[row["product_id"]],
                            quantity=Decimal(row["quantity"]),
                            unit_price=Decimal(row["unit_price"]),
                            expected_quantity=Decimal(row["expected_quantity"])
                            if row.get("expected_quantity") is not None
                            else None,
                            rejected_quantity=Decimal(
                                row.get("rejected_quantity", "0")
                            ),
                            note=row.get("note", ""),
                        )
                        for row in group[offset : offset + 50]
                    ],
                )
            )
            audit_document(doc, actor, "CREATE")
            documents.append(doc)
    return documents


@login_required
@require_http_methods(["GET", "POST"])
def receipt_import(request):
    require_function(request.user, "receipts_create")
    form = ReceiptImportForm(
        request.POST or None, request.FILES or None, user=request.user
    )
    preview = None
    if request.method == "POST" and request.POST.get("confirm"):
        key = request.POST.get("import_key", "")
        completed = request.session.get("receipt_import_result", {})
        if (
            completed.get("owner") == request.user.pk
            and key
            and completed.get("key") == key
        ):
            messages.info(
                request, "Lượt nhập này đã hoàn tất; không tạo thêm phiếu trùng."
            )
            return batch_redirect(completed)
        preview = current_preview(request)
        if not preview or key != preview.get("key"):
            request.session.pop("receipt_import", None)
            messages.error(
                request,
                "Bản xem trước đã hết hạn hoặc đã được xử lý. Hãy tải lại file.",
            )
            return redirect("receipt_import")
        try:
            docs = confirm_receipts(request.user, preview)
        except ValidationError as exc:
            request.session.pop("receipt_import", None)
            messages.error(request, " ".join(exc.messages))
            return redirect("receipt_import")
        result = {
            "owner": request.user.pk,
            "key": key,
            "filename": preview["filename"],
            "document_ids": [doc.pk for doc in docs],
        }
        request.session["receipt_import_result"] = result
        request.session.pop("receipt_import", None)
        messages.success(
            request, f"Đã tạo {len(docs)} phiếu nhập theo kho chờ duyệt. Chưa cộng tồn."
        )
        return batch_redirect(result)
    if request.method == "POST":
        request.session.pop("receipt_import", None)
        if form.is_valid():
            try:
                if request.POST.get("normalize") == "1":
                    book = normalized_receipt_download(
                        form.cleaned_data["file"], user=request.user
                    )
                    response = HttpResponse(
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    response["Content-Disposition"] = (
                        'attachment; filename="nhap-kho-da-chuan-hoa.xlsx"'
                    )
                    response["Cache-Control"] = "private, no-store"
                    try:
                        book.save(response)
                    finally:
                        book.close()
                    return response
                rows = parse_receipt(form.cleaned_data["file"])
                groups = resolve_rows(
                    rows, request.user, form.cleaned_data["warehouse"]
                )
                details = {
                    key: str(form.cleaned_data[key])
                    if isinstance(form.cleaned_data[key], date)
                    else form.cleaned_data[key]
                    for key in form.Meta.fields
                    if key != "note"
                }
                for group in groups:
                    validate_document(
                        Document(
                            kind="IN",
                            destination_id=group["warehouse_id"],
                            **document_details({"details": details}),
                            note=form.cleaned_data["note"],
                        )
                    )
                preview = {
                    "key": str(uuid4()),
                    "owner": request.user.pk,
                    "created_at": time.time(),
                    "filename": str(form.cleaned_data["file"].name),
                    "warehouse_id": groups[0]["warehouse_id"]
                    if len(groups) == 1
                    else None,
                    "warehouse_name": groups[0]["warehouse_name"]
                    if len(groups) == 1
                    else f"{len(groups)} kho",
                    "note": form.cleaned_data["note"],
                    "details": details,
                    "rows": rows,
                    "groups": groups,
                    "document_count": sum(group["documents"] for group in groups),
                }
                request.session["receipt_import"] = preview
            except ValidationError as exc:
                form.add_error("file", exc)
    return render(request, "receipt_import.html", {"form": form, "preview": preview})

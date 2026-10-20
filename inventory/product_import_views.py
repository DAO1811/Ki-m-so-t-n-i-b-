"""Preview Excel catalogue additions before committing the complete batch."""

import time
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from .access import require_function
from .product_import import (
    build_product_template,
    confirm_product_import,
    parse_product_workbook,
)

PREVIEW_SECONDS = 30 * 60


class ProductImportUploadForm(forms.Form):
    file = forms.FileField(
        label="File Excel hàng hóa",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
        help_text="File .xlsx, tối đa 5 MB và 500 hàng hóa mỗi lần nhập.",
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".xlsx"):
            raise ValidationError(
                "Chọn file .xlsx. File .xls hoặc CSV cần lưu lại dạng .xlsx."
            )
        if upload.size > 5 * 1024 * 1024:
            raise ValidationError("File quá lớn. Mỗi lần nhập tối đa 5 MB.")
        return upload


def current_preview(request):
    preview = request.session.get("product_import")
    if (
        not isinstance(preview, dict)
        or preview.get("owner") != request.user.pk
        or not isinstance(preview.get("created_at"), (int, float))
        or not 0 <= time.time() - preview["created_at"] <= PREVIEW_SECONDS
    ):
        request.session.pop("product_import", None)
        return None
    return preview


def preview_context(preview):
    if preview is None:
        return None
    extra_columns = [
        column for column in preview["columns"] if column["key"].startswith("extra_")
    ]
    rows = []
    for original in preview["rows"]:
        data = original["data"]
        rows.append(
            {
                **data,
                "number": original["row_number"],
                "checked": preview.get("rows_checked", True),
                "extra": {
                    column["label"]: data.get(column["key"], "")
                    for column in extra_columns
                    if data.get(column["key"], "")
                },
                "errors": [
                    f"{error['label']}: {error['message']}"
                    for error in original["errors"]
                ],
            }
        )
    return {
        "key": preview.get("key", ""),
        "filename": preview["filename"],
        "total_rows": preview["count"],
        "valid_count": preview["valid_count"],
        "error_count": sum(bool(row["errors"]) for row in rows)
        + len(preview["errors"]),
        "errors": preview["errors"],
        "rows": rows,
        "valid": preview["valid"],
    }


@login_required
@require_GET
def product_import_template(request):
    require_function(request.user, "products_create")
    try:
        template = build_product_template()
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("product_import")
    response = HttpResponse(
        template.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="mau-them-hang-hoa.xlsx"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def product_import(request):
    require_function(request.user, "products_create")
    form = ProductImportUploadForm()
    confirmation_errors = []
    preview = current_preview(request)
    if request.method == "POST":
        action = request.POST.get("action", "preview")
        if action not in {"preview", "confirm", "cancel"}:
            return HttpResponseBadRequest("Thao tác nhập hàng hóa không hợp lệ.")
        if action == "cancel":
            if preview and request.POST.get("import_key") == preview.get("key"):
                request.session.pop("product_import", None)
            return redirect("product_import")
        if action == "confirm":
            key = request.POST.get("import_key", "")
            completed = request.session.get("product_import_result", {})
            if (
                key
                and completed.get("key") == key
                and completed.get("owner") == request.user.pk
            ):
                messages.info(
                    request, "Lượt nhập này đã hoàn tất; không tạo thêm hàng trùng."
                )
                return redirect(reverse("products") + "?batch=" + key)
            if not preview or not preview["valid"] or key != preview.get("key"):
                messages.error(
                    request,
                    "Bản xem trước đã hết hạn hoặc không thuộc lượt nhập này. Hãy chọn file và kiểm tra lại.",
                )
                return redirect("product_import")
            try:
                products = confirm_product_import(
                    request.user,
                    preview["rows"],
                    preview["schema"],
                    filename=preview["filename"],
                )
            except ValidationError as exc:
                request.session.pop("product_import", None)
                confirmation_errors = exc.messages
                preview = None
            else:
                request.session.pop("product_import", None)
                request.session["product_import_result"] = {
                    "owner": request.user.pk,
                    "key": key,
                    "filename": preview["filename"],
                    "ids": [product.pk for product in products],
                }
                messages.success(
                    request,
                    f"Đã thêm {len(products)} hàng hóa từ Excel và tạo mã QR cho từng mã.",
                )
                return redirect(reverse("products") + "?batch=" + key)
        else:
            request.session.pop("product_import", None)
            preview = None
            form = ProductImportUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    preview = parse_product_workbook(form.cleaned_data["file"])
                    preview.update(
                        key=str(uuid4()), owner=request.user.pk, created_at=time.time()
                    )
                    if preview["valid"]:
                        request.session["product_import"] = preview
                except ValidationError as exc:
                    form.add_error("file", exc)
    response = render(
        request,
        "product_import.html",
        {
            "form": form,
            "preview": preview_context(preview),
            "confirmation_errors": confirmation_errors,
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response

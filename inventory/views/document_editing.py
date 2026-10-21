from decimal import Decimal
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import DocumentForm, LineFormSet
from ..models import (
    Balance,
    Document,
    Line,
    LoanHolding,
    Product,
)
from ..services import (
    audit_document,
    capture_lines,
    documents_for,
    warehouses_for,
)
from ..workspace import selected_warehouse


def document_form_response(request, form, formset, operation, editing=False):
    instructions = {
        "IN": "Chọn kho nhận → thêm hàng và đơn giá → gửi quản lý kho duyệt.",
        "OUT": "Chọn kho xuất → thêm hàng đang có tồn → gửi người có quyền duyệt xuất.",
        "TRANSFER": "Chọn hai kho → duyệt chuyển đi → kho nhận xác nhận hàng đến.",
        "LOAN": "Chọn kho cho mượn và kho mượn. Hàng mượn được khóa ở sổ trung gian, không được xuất dùng.",
        "RETURN": "Chọn lệnh mượn gốc → kiểm tra hàng còn mượn → nhập số lượng trả.",
        "COUNT": "Nhập số thực đếm của tồn thường, không cộng hàng mượn tạm. Ghi lý do chênh lệch.",
        "ADJUST": "Nhập số tăng hoặc giảm, ghi rõ lý do. Hệ thống không cho phép âm tồn.",
    }
    return render(
        request,
        "document_form.html",
        {
            "form": form,
            "formset": formset,
            "form_kind": operation,
            "operation_name": dict(Document.TYPES).get(operation, "Lập phiếu"),
            "operation_help": instructions.get(operation, ""),
            "editing": editing,
            "loans_data": list(
                form.fields["loan"].queryset.values("id", "source_id", "destination_id")
            ),
            "has_products": Product.objects.exists(),
            "has_warehouses": warehouses_for(request.user).exists(),
        },
    )


def validate_available_lines(form, formset):
    """Catch an obvious shortage before sending a draft; posting rechecks under locks."""
    kind = form.cleaned_data["kind"]
    if kind not in ["OUT", "TRANSFER", "LOAN", "RETURN"]:
        return True
    if kind == "RETURN":
        available = {
            h.loan_line.product_id: h.quantity
            for h in LoanHolding.objects.filter(
                loan_line__document=form.cleaned_data["loan"]
            ).select_related("loan_line")
        }
    else:
        available = {
            b.product_id: b.quantity
            for b in Balance.objects.filter(warehouse=form.cleaned_data["source"])
        }
    valid = True
    for row in formset:
        data = row.cleaned_data
        if not data or data.get("DELETE"):
            continue
        current = available.get(data["product"].pk, Decimal(0))
        if data["quantity"] > current:
            row.add_error(
                "quantity",
                f"Chỉ còn {current:f} {data['product'].unit} có thể {'trả' if kind == 'RETURN' else 'xuất / cho mượn'}.",
            )
            valid = False
    return valid


@login_required
def document_new(request, kind=None):
    fixed = kind.upper() if kind else None
    if fixed and fixed not in dict(Document.TYPES):
        raise Http404
    operation = fixed or request.POST.get("kind") or request.GET.get("kind", "IN")
    if operation not in dict(Document.TYPES):
        operation = "IN"
    if operation == "COUNT":
        if request.method == "POST":
            messages.info(
                request,
                "Kiểm kê mới cần chốt tồn kho trước, sau đó chọn kiểm bằng giấy hoặc QR.",
            )
        return redirect("stocktakes")
    if operation == "RETURN" and request.method == "GET":
        loan_id = request.GET.get("loan", "")
        if loan_id.isdigit() and len(loan_id) <= 18:
            return redirect("loan_return", pk=int(loan_id))
        if loan_id:
            raise Http404("Lệnh mượn không hợp lệ.")
        return redirect("loans")
    accessible = warehouses_for(request.user)
    warehouse = selected_warehouse(request) or (
        accessible.first() if accessible.count() == 1 else None
    )
    initial = {"kind": operation, "submission_key": uuid4()}
    if warehouse:
        initial[
            "source"
            if operation in ["OUT", "TRANSFER", "LOAN", "RETURN"]
            else "destination"
        ] = warehouse
    line_initial = []
    loan_id = request.GET.get("loan")
    if operation == "RETURN" and loan_id:
        loan = get_object_or_404(
            documents_for(request.user),
            pk=loan_id if str(loan_id).isdigit() and len(str(loan_id)) <= 18 else 0,
            kind="LOAN",
            status="POSTED",
        )
        initial.update(loan=loan, source=loan.destination, destination=loan.source)
        line_initial = [
            {"product": h.loan_line.product_id, "quantity": h.quantity}
            for h in LoanHolding.objects.filter(
                loan_line__document=loan, quantity__gt=0
            ).select_related("loan_line")
        ]
    form = DocumentForm(
        request.POST or None, user=request.user, fixed_kind=fixed, initial=initial
    )
    formset = LineFormSet(request.POST or None, initial=line_initial, kind=operation)
    if (
        request.method == "POST"
        and form.is_valid()
        and formset.is_valid()
        and validate_available_lines(form, formset)
    ):
        if operation == "RETURN":
            from ..loan_returns import save_return

            try:
                doc = save_return(
                    form.cleaned_data["loan"].pk,
                    request.user,
                    {
                        row.cleaned_data["product"].pk: row.cleaned_data["quantity"]
                        for row in formset
                        if row.cleaned_data and not row.cleaned_data.get("DELETE")
                    },
                    note=form.cleaned_data.get("note", ""),
                    submission_key=form.cleaned_data.get("submission_key") or uuid4(),
                )
                return redirect("document_detail", pk=doc.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
                return document_form_response(request, form, formset, operation)
        with transaction.atomic():
            key = form.cleaned_data.get("submission_key") or uuid4()
            values = {k: form.cleaned_data.get(k) for k in DocumentForm.Meta.fields}
            doc, created = Document.objects.get_or_create(
                import_key=key, defaults={**values, "created_by": request.user}
            )
            if not created and doc.created_by_id != request.user.pk:
                raise PermissionDenied(
                    "Không được sử dụng mã phiên tạo phiếu của người khác."
                )
            if created:
                Line.objects.bulk_create(
                    capture_lines(
                        doc,
                        [
                            Line(
                                document=doc,
                                **{
                                    k: v
                                    for k, v in f.cleaned_data.items()
                                    if k != "DELETE"
                                },
                            )
                            for f in formset
                            if f.cleaned_data and not f.cleaned_data.get("DELETE")
                        ],
                    )
                )
                audit_document(doc, request.user, "CREATE")
        messages.success(
            request,
            "Đã lưu phiếu chờ duyệt. Người đủ cấp và quyền kiểm tra, duyệt để cập nhật tồn.",
        )
        return redirect("document_detail", pk=doc.pk)
    return document_form_response(request, form, formset, operation)


@login_required
def document_edit(request, pk):
    doc = get_object_or_404(
        Document, pk=pk, created_by=request.user, status__in=["DRAFT", "REJECTED"]
    )
    if doc.kind == "RETURN" and request.method == "GET":
        return redirect("loan_return_edit", pk=doc.pk)
    if hasattr(doc, "stocktake_session"):
        raise PermissionDenied(
            "Phiếu điều chỉnh kiểm kê khóa theo biên bản gốc. Nếu cần sửa, hủy phiếu rồi mở phiên kiểm kê mới."
        )
    form = DocumentForm(
        request.POST or None, user=request.user, instance=doc, fixed_kind=doc.kind
    )
    formset = LineFormSet(
        request.POST or None,
        initial=list(
            doc.lines.values(
                "product",
                "quantity",
                "unit_price",
                "expected_quantity",
                "rejected_quantity",
                "note",
            )
        ),
        kind=doc.kind,
    )
    if (
        request.method == "POST"
        and form.is_valid()
        and formset.is_valid()
        and validate_available_lines(form, formset)
    ):
        if doc.kind == "RETURN":
            from ..loan_returns import save_return

            try:
                saved = save_return(
                    form.cleaned_data["loan"].pk,
                    request.user,
                    {
                        row.cleaned_data["product"].pk: row.cleaned_data["quantity"]
                        for row in formset
                        if row.cleaned_data and not row.cleaned_data.get("DELETE")
                    },
                    note=form.cleaned_data.get("note", ""),
                    editing_id=doc.pk,
                    revision=form.cleaned_data["revision"],
                )
                return redirect("document_detail", pk=saved.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
                return document_form_response(
                    request, form, formset, doc.kind, editing=True
                )
        with transaction.atomic():
            locked = Document.objects.select_for_update().get(pk=pk)
            if locked.status not in ["DRAFT", "REJECTED"]:
                messages.error(request, "Phiếu đã được xử lý, không thể sửa.")
                return redirect("document_detail", pk=pk)
            if locked.revision != form.cleaned_data["revision"]:
                messages.error(
                    request,
                    "Phiếu đã được sửa ở phiên khác. Hãy mở lại phiếu mới nhất để tránh ghi đè.",
                )
                return redirect("document_edit", pk=pk)
            form.instance.status = "DRAFT"
            form.instance.closure_reason = ""
            form.instance.revision = locked.revision + 1
            form.save()
            doc.lines.all().delete()
            Line.objects.bulk_create(
                capture_lines(
                    doc,
                    [
                        Line(
                            document=doc,
                            **{
                                k: v for k, v in f.cleaned_data.items() if k != "DELETE"
                            },
                        )
                        for f in formset
                        if f.cleaned_data and not f.cleaned_data.get("DELETE")
                    ],
                )
            )
            audit_document(doc, request.user, "EDIT")
        messages.success(request, "Đã cập nhật phiếu nháp.")
        return redirect("document_detail", pk=pk)
    return document_form_response(request, form, formset, doc.kind, editing=True)

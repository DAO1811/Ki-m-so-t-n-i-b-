import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, F, Sum, Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Document, Line, Product, Balance, Movement, LoanHolding
from .forms import DocumentForm, LineFormSet, ProductForm, WarehouseForm, EmployeeForm
from .services import (
    warehouses_for,
    documents_for,
    post_document,
    can_approve,
    approval_documents_for,
    capture_lines,
    audit_document,
    close_document,
)
from .workspace import selected_warehouse, scoped_documents
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import date
from decimal import Decimal
from uuid import uuid4
from django.core.exceptions import PermissionDenied
from .models import CustomField


def balances(user):
    return Balance.objects.filter(warehouse__in=warehouses_for(user)).select_related(
        "warehouse", "product"
    )


def export_csv(name, headers, rows):
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(
            [
                ("'" + v)
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                else format(v, "f")
                if isinstance(v, Decimal)
                else v
                for v in row
            ]
        )
    # Encode once. Encoding each response.write with utf-8-sig adds a BOM to every row.
    response = HttpResponse(
        buffer.getvalue().encode("utf-8-sig"),
        content_type="text/csv; charset=utf-8-sig",
    )
    response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
    return response


def request_balances(request):
    qs = balances(request.user)
    warehouse = selected_warehouse(request)
    return qs.filter(warehouse=warehouse) if warehouse else qs


def date_range(request):
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get("from", str(today.replace(day=1))))
        end = date.fromisoformat(request.GET.get("to", str(today)))
        if start > end or (end - start).days > 366:
            raise ValueError
    except (ValueError, TypeError):
        start, end = today.replace(day=1), today
        messages.error(
            request,
            "Khoảng ngày không hợp lệ. Đang hiển thị tháng hiện tại; tối đa 366 ngày mỗi lần.",
        )
    return start, end


@login_required
def dashboard(request):
    b = request_balances(request)
    docs = scoped_documents(request)
    start, end = date_range(request)
    movement = Movement.objects.filter(
        warehouse__in=warehouses_for(request.user),
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    warehouse = selected_warehouse(request)
    if warehouse:
        movement = movement.filter(warehouse=warehouse)
    inbound = (
        movement.filter(document__kind="IN").aggregate(n=Sum("value_delta"))["n"] or 0
    )
    outbound = -(
        movement.filter(document__kind="OUT").aggregate(n=Sum("value_delta"))["n"] or 0
    )
    # Quantities with different units are deliberately not added together.
    groups = {}
    activity_rows = (
        movement.filter(document__kind__in=["IN", "OUT"])
        .annotate(day=TruncDate("created_at"))
        .values("day", "document__kind")
        .annotate(amount=Sum("value_delta"))
        .order_by("day")
    )
    for row in activity_rows:
        day = row["day"]
        key = (
            day.strftime("%d/%m") if (end - start).days <= 31 else day.strftime("%m/%Y")
        )
        groups.setdefault(key, {"label": key, "inbound": 0, "outbound": 0})
        groups[key]["inbound" if row["document__kind"] == "IN" else "outbound"] += (
            float(abs(row["amount"]))
        )
    warehouse_values = list(
        b.values("warehouse__name", "warehouse__code")
        .annotate(total=Sum("value"))
        .order_by("-total")
    )
    approval = approval_documents_for(request.user)
    if warehouse:
        approval = approval.filter(Q(source=warehouse) | Q(destination=warehouse))
    owned_holdings = LoanHolding.objects.filter(
        loan_line__document__source__in=warehouses_for(request.user)
    )
    if warehouse:
        owned_holdings = owned_holdings.filter(loan_line__document__source=warehouse)
    context = {
        "warehouse_count": 1 if warehouse else warehouses_for(request.user).count(),
        "product_count": Product.objects.count(),
        "pending": docs.filter(status="DRAFT").count(),
        "approval_count": approval.count(),
        "total_value": b.aggregate(n=Sum("value"))["n"] or 0,
        "inbound_value": inbound,
        "outbound_value": outbound,
        "stock_rows": b.filter(quantity__gt=0).count(),
        "transit_count": docs.filter(status="TRANSIT").count(),
        "low_count": b.filter(quantity__lt=F("product__minimum")).count(),
        "today_count": docs.filter(
            Q(posted_at__date=timezone.localdate())
            | Q(dispatched_at__date=timezone.localdate())
        ).count(),
        "loan_value": owned_holdings.aggregate(n=Sum("value"))["n"] or 0,
        "recent": docs.select_related("source", "destination", "created_by")[:6],
        "low": b.filter(quantity__lt=F("product__minimum"))[:5],
        "chart_activity": list(groups.values()),
        "chart_warehouses": [
            {
                "label": v["warehouse__code"],
                "name": v["warehouse__name"],
                "value": float(v["total"]),
            }
            for v in warehouse_values
        ],
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "has_warehouses": warehouses_for(request.user).exists(),
        "has_products": Product.objects.exists(),
    }
    return render(request, "dashboard.html", context)


@login_required
def documents(request):
    qs = scoped_documents(request).select_related("source", "destination", "created_by")
    kind = request.GET.get("kind", "")
    status = request.GET.get("status", "")
    if kind:
        qs = qs.filter(kind=kind)
    if status:
        qs = qs.filter(status=status)
    if request.GET.get("mine"):
        qs = qs.filter(created_by=request.user)
    if request.GET.get("q"):
        q = request.GET["q"].strip()
        number = q.upper().removeprefix("PK-")
        search = (
            Q(note__icontains=q)
            | Q(created_by__username__icontains=q)
            | Q(reference_number__icontains=q)
            | Q(counterparty__icontains=q)
            | Q(department__icontains=q)
        )
        if number.isdigit() and len(number) <= 18:
            search |= Q(pk=int(number))
        qs = qs.filter(search)
    if request.GET.get("from") or request.GET.get("to"):
        start, end = date_range(request)
        qs = qs.filter(business_date__range=[start, end])
    if request.GET.get("export"):
        return export_csv(
            "chung-tu-kho",
            [
                "Mã phiếu",
                "Loại phiếu",
                "Ngày thực tế",
                "Thời điểm lập",
                "Thời điểm chuyển đi",
                "Thời điểm ghi sổ",
                "Kho xuất",
                "Kho nhận",
                "Trạng thái",
                "Chứng từ nguồn",
                "Ngày chứng từ nguồn",
                "Đối tác",
                "Bộ phận",
                "Người giao",
                "Người nhận",
                "Hạn trả",
                "Người lập",
                "Người duyệt chuyển",
                "Người ghi sổ",
                "Diễn giải",
                "Lý do yêu cầu sửa / hủy",
            ],
            (
                (
                    str(d),
                    d.get_kind_display(),
                    str(d.business_date),
                    d.created_at.isoformat(),
                    d.dispatched_at.isoformat() if d.dispatched_at else "",
                    d.posted_at.isoformat() if d.posted_at else "",
                    d.source.code if d.source else "",
                    d.destination.code if d.destination else "",
                    d.get_status_display(),
                    d.reference_number,
                    str(d.reference_date or ""),
                    d.counterparty,
                    d.department,
                    d.handed_over_by,
                    d.received_by,
                    str(d.due_date or ""),
                    d.created_by.username,
                    d.dispatched_by.username if d.dispatched_by else "",
                    d.posted_by.username if d.posted_by else "",
                    d.note,
                    d.closure_reason,
                )
                for d in qs.select_related("created_by", "posted_by", "dispatched_by")
            ),
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "documents.html",
        {"documents": page, "page_obj": page, "kinds": Document.TYPES},
    )


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
@permission_required("inventory.add_document", raise_exception=True)
def document_new(request, kind=None):
    fixed = kind.upper() if kind else None
    if fixed and fixed not in dict(Document.TYPES):
        raise Http404
    operation = fixed or request.POST.get("kind") or request.GET.get("kind", "IN")
    if operation not in dict(Document.TYPES):
        operation = "IN"
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
            documents_for(request.user), pk=loan_id, kind="LOAN", status="POSTED"
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
            request, "Đã lưu phiếu nháp. Kiểm tra rồi bấm Ghi sổ để cập nhật tồn."
        )
        return redirect("document_detail", pk=doc.pk)
    return document_form_response(request, form, formset, operation)


@login_required
@permission_required("inventory.add_document", raise_exception=True)
def document_edit(request, pk):
    doc = get_object_or_404(
        Document, pk=pk, created_by=request.user, status__in=["DRAFT", "REJECTED"]
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


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(documents_for(request.user), pk=pk)
    can_post = can_approve(doc, request.user)
    receiving = doc.status == "TRANSIT" or not doc.source_id
    approvers = (
        doc.destination.managers if receiving else doc.source.issue_approvers
    ).all()
    return render(
        request,
        "document_detail.html",
        {
            "doc": doc,
            "lines": doc.lines.select_related("product"),
            "can_post": can_post,
            "approvers": approvers,
            "events": doc.events.select_related("actor"),
            "can_cancel": doc.status in ["DRAFT", "REJECTED"]
            and (doc.created_by_id == request.user.pk or request.user.is_superuser),
            "duplicate_sources": documents_for(request.user)
            .filter(
                kind="IN",
                reference_number__iexact=doc.reference_number,
                counterparty__iexact=doc.counterparty,
            )
            .exclude(pk=doc.pk)
            .exclude(status="CANCELLED")[:5]
            if doc.kind == "IN" and doc.reference_number
            else [],
            "total_amount": sum(
                (
                    l.quantity * l.unit_price
                    for l in doc.lines.all()
                    if l.unit_price is not None
                ),
                Decimal(0),
            ),
        },
    )


@login_required
@require_POST
def document_post(request, pk):
    get_object_or_404(documents_for(request.user), pk=pk)
    try:
        result = post_document(pk, request.user)
        messages.success(
            request,
            "Đã xuất kho, đang chờ kho nhận xác nhận."
            if result.status == "TRANSIT"
            else "Đã ghi sổ và cập nhật tồn kho.",
        )
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("document_detail", pk=pk)


@login_required
@require_POST
def document_close(request, pk, action):
    get_object_or_404(documents_for(request.user), pk=pk)
    try:
        close_document(pk, request.user, action.upper(), request.POST.get("reason", ""))
        messages.success(request, "Đã lưu xử lý phiếu; tồn kho không thay đổi.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("document_detail", pk=pk)


@login_required
def stock(request):
    qs = request_balances(request).order_by("warehouse__code", "product__sku")
    warehouse = selected_warehouse(request)
    if warehouse:
        qs = qs.filter(warehouse=warehouse)
    if request.GET.get("q"):
        qs = qs.filter(
            Q(product__name__icontains=request.GET["q"])
            | Q(product__sku__icontains=request.GET["q"])
        )
    if request.GET.get("low"):
        qs = qs.filter(quantity__lt=F("product__minimum"))
    if request.GET.get("export"):
        return export_csv(
            "ton-kho",
            [
                "Kho",
                "Mã hàng",
                "Tên hàng",
                "ĐVT",
                "Tồn",
                "Tối thiểu",
                "Giá bình quân",
                "Giá trị VNĐ",
            ],
            (
                (
                    b.warehouse.code,
                    b.product.sku,
                    b.product.name,
                    b.product.unit,
                    b.quantity,
                    b.product.minimum,
                    b.average_cost,
                    b.value,
                )
                for b in qs
            ),
        )
    return render(
        request,
        "stock.html",
        {"balances": qs[:500], "warehouses": warehouses_for(request.user)},
    )


@login_required
def ledger(request):
    qs = Movement.objects.filter(
        warehouse__in=warehouses_for(request.user)
    ).select_related("document", "product", "warehouse")
    warehouse = selected_warehouse(request)
    if warehouse:
        qs = qs.filter(warehouse=warehouse)
    if request.GET.get("product"):
        raw = request.GET["product"]
        product = get_object_or_404(Product, pk=raw if raw.isdigit() else 0)
        qs = qs.filter(product=product)
    if request.GET.get("from") or request.GET.get("to"):
        start, end = date_range(request)
        qs = qs.filter(created_at__date__range=[start, end])
    # Balance after is persisted per movement, so filtered history retains true running balance.
    if request.GET.get("export"):
        return export_csv(
            "the-kho",
            [
                "Thời gian ghi sổ",
                "Ngày nghiệp vụ thực tế",
                "Phiếu",
                "Kho",
                "Hàng",
                "Biến động",
                "Tồn sau",
                "Giá trị biến động VNĐ",
                "Giá trị tồn VNĐ",
            ],
            (
                (
                    m.created_at.isoformat(),
                    m.business_date.isoformat(),
                    str(m.document),
                    m.warehouse.code,
                    m.product.sku,
                    m.delta,
                    m.balance_after,
                    m.value_delta,
                    m.value_after,
                )
                for m in qs
            ),
        )
    return render(
        request,
        "ledger.html",
        {
            "movements": qs[:500],
            "warehouses": warehouses_for(request.user),
            "products": Product.objects.all(),
        },
    )


@login_required
def loans(request):
    rows = []
    warehouse_ids = set(warehouses_for(request.user).values_list("id", flat=True))
    for doc in (
        scoped_documents(request)
        .filter(kind="LOAN", status="POSTED")
        .select_related("source", "destination")
        .prefetch_related("lines__product")
    ):
        for line in doc.lines.all():
            returned = (
                Movement.objects.filter(
                    document__loan=doc, warehouse=doc.source, product=line.product
                ).aggregate(n=Sum("delta"))["n"]
                or 0
            )
            holding = LoanHolding.objects.filter(loan_line=line).first()
            pending = (
                Line.objects.filter(
                    document__loan=doc, document__status="TRANSIT", product=line.product
                ).aggregate(n=Sum("quantity"))["n"]
                or 0
            )
            rows.append(
                {
                    "doc": doc,
                    "product": line.product,
                    "quantity": line.quantity,
                    "returned": returned,
                    "outstanding": line.quantity - returned,
                    "holding": holding.quantity if holding else 0,
                    "value": holding.value if holding else 0,
                    "pending": pending,
                    "can_return": doc.destination_id in warehouse_ids,
                    "overdue": bool(
                        doc.due_date
                        and doc.due_date < timezone.localdate()
                        and line.quantity > returned
                    ),
                }
            )
    return render(
        request,
        "loans.html",
        {
            "rows": rows,
            "transit_loans": scoped_documents(request)
            .filter(kind="LOAN", status="TRANSIT")
            .select_related("source", "destination"),
        },
    )


@login_required
def products(request):
    qs = Product.objects.all().order_by("sku")
    if request.GET.get("q"):
        qs = qs.filter(
            Q(name__icontains=request.GET["q"])
            | Q(sku__icontains=request.GET["q"])
            | Q(category__icontains=request.GET["q"])
            | Q(brand__icontains=request.GET["q"])
            | Q(model_number__icontains=request.GET["q"])
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "products.html", {"products": page, "page_obj": page})


@login_required
@permission_required("inventory.add_product", raise_exception=True)
def product_new(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã thêm hàng hóa.")
        return redirect("products")
    return render(request, "product_form.html", {"form": form})


@login_required
@permission_required("inventory.add_document", raise_exception=True)
def receipt_template(request):
    from .excel import receipt_template

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="mau-nhap-kho.xlsx"'
    receipt_template().save(response)
    return response


@login_required
@permission_required("inventory.add_document", raise_exception=True)
def receipt_import(request):
    from .forms import ReceiptImportForm
    from .excel import parse_receipt
    import uuid

    form = ReceiptImportForm(
        request.POST or None, request.FILES or None, user=request.user
    )
    preview = None
    if request.method == "POST" and request.POST.get("confirm"):
        preview = request.session.get("receipt_import")
        if not preview or request.POST.get("import_key") != preview["key"]:
            messages.error(
                request,
                "Lượt nhập không còn hợp lệ hoặc đã tạo phiếu. Hãy tải file lại.",
            )
            return redirect("receipt_import")
        warehouse = get_object_or_404(
            warehouses_for(request.user), pk=preview["warehouse_id"]
        )
        if preview.get("details", {}).get("business_date") != str(timezone.localdate()):
            request.session.pop("receipt_import", None)
            messages.error(
                request,
                "Bản xem trước đã sang ngày khác hoặc dùng phiên cũ. Hãy tải lại để tạo phiếu ngày hôm nay.",
            )
            return redirect("receipt_import")
        with transaction.atomic():
            doc, created = Document.objects.get_or_create(
                import_key=preview["key"],
                defaults={
                    "kind": "IN",
                    "destination": warehouse,
                    "created_by": request.user,
                    "note": preview["note"],
                    **{
                        k: date.fromisoformat(v)
                        if k in ["business_date", "reference_date", "due_date"] and v
                        else v
                        for k, v in preview.get("details", {}).items()
                    },
                },
            )
            if created:
                # Recheck product existence after preview; deleting products must not yield a partial import.
                if Product.objects.filter(
                    pk__in=[i["product_id"] for i in preview["rows"]]
                ).count() != len(preview["rows"]):
                    transaction.set_rollback(True)
                    messages.error(request, "Danh mục đã thay đổi. Hãy tải lại file.")
                    return redirect("receipt_import")
                Line.objects.bulk_create(
                    capture_lines(
                        doc,
                        [
                            Line(
                                document=doc,
                                product_id=i["product_id"],
                                quantity=Decimal(i["quantity"]),
                                unit_price=Decimal(i["unit_price"]),
                                expected_quantity=Decimal(i["expected_quantity"])
                                if i.get("expected_quantity") is not None
                                else None,
                                rejected_quantity=Decimal(
                                    i.get("rejected_quantity", "0")
                                ),
                                note=i.get("note", ""),
                            )
                            for i in preview["rows"]
                        ],
                    )
                )
                audit_document(doc, request.user, "CREATE")
        request.session.pop("receipt_import", None)
        messages.success(
            request,
            "Đã tạo phiếu nhập nháp từ Excel. Quản lý kho cần kiểm tra và xác nhận trước khi cộng tồn.",
        )
        return redirect("document_detail", pk=doc.pk)
    if request.method == "POST" and form.is_valid():
        try:
            rows = parse_receipt(form.cleaned_data["file"])
            preview = {
                "key": str(uuid.uuid4()),
                "warehouse_id": form.cleaned_data["warehouse"].pk,
                "warehouse_name": str(form.cleaned_data["warehouse"]),
                "note": form.cleaned_data["note"],
                "details": {
                    k: str(form.cleaned_data[k])
                    if isinstance(form.cleaned_data[k], date)
                    else form.cleaned_data[k]
                    for k in form.Meta.fields
                    if k != "note"
                },
                "rows": rows,
            }
            request.session["receipt_import"] = preview
        except ValidationError as exc:
            form.add_error("file", exc)
    return render(request, "receipt_import.html", {"form": form, "preview": preview})


@login_required
@require_POST
def warehouse_scope(request):
    raw = request.POST.get("warehouse", "")
    if raw:
        warehouse = get_object_or_404(
            warehouses_for(request.user), pk=raw if raw.isdigit() else 0
        )
        request.session["warehouse_scope"] = str(warehouse.pk)
    else:
        request.session.pop("warehouse_scope", None)
    target = request.POST.get("next", "/")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = "/"
    return redirect(target)


@login_required
def availability(request):
    raw = request.GET.get("warehouse", "")
    warehouse = get_object_or_404(
        warehouses_for(request.user), pk=raw if raw.isdigit() else 0
    )
    loan_id = request.GET.get("loan", "")
    if loan_id:
        loan = get_object_or_404(
            documents_for(request.user),
            pk=loan_id if loan_id.isdigit() else 0,
            kind="LOAN",
            status="POSTED",
            destination=warehouse,
        )
        rows = LoanHolding.objects.filter(loan_line__document=loan).values(
            "loan_line__product_id", "quantity"
        )
        data = {str(row["loan_line__product_id"]): str(row["quantity"]) for row in rows}
    else:
        data = {
            str(b.product_id): str(b.quantity)
            for b in Balance.objects.filter(warehouse=warehouse)
        }
    return JsonResponse({"quantities": data})


@login_required
def approvals(request):
    qs = approval_documents_for(request.user).select_related(
        "source", "destination", "created_by"
    )
    warehouse = selected_warehouse(request)
    if warehouse:
        qs = qs.filter(Q(source=warehouse) | Q(destination=warehouse))
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "approvals.html",
        {"documents": page, "page_obj": page, "approval_total": qs.count()},
    )


@login_required
@permission_required("inventory.change_product", raise_exception=True)
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật hàng hóa.")
        return redirect("products")
    return render(request, "product_form.html", {"form": form, "editing": True})


@login_required
def warehouse_list(request):
    return render(
        request,
        "warehouses.html",
        {
            "warehouses": warehouses_for(request.user)
            .prefetch_related("members", "managers", "issue_approvers")
            .order_by("code")
        },
    )


@login_required
@permission_required("inventory.add_warehouse", raise_exception=True)
def warehouse_new(request):
    return warehouse_form(request)


@login_required
@permission_required("inventory.change_warehouse", raise_exception=True)
def warehouse_edit(request, pk):
    return warehouse_form(
        request, get_object_or_404(warehouses_for(request.user), pk=pk)
    )


def warehouse_form(request, warehouse=None):
    form = WarehouseForm(request.POST or None, instance=warehouse)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã lưu kho và phân công người duyệt.")
        return redirect("warehouse_list")
    return render(
        request, "warehouse_form.html", {"form": form, "editing": bool(warehouse)}
    )


def require_admin(user):
    from django.core.exceptions import PermissionDenied

    if not user.is_superuser:
        raise PermissionDenied(
            "Chỉ quản trị viên được quản lý nhân viên và phân quyền."
        )


@login_required
def team(request):
    require_admin(request.user)
    qs = (
        get_user_model()
        .objects.all()
        .prefetch_related(
            "groups", "warehouses", "managed_warehouses", "issue_warehouses"
        )
        .order_by("username")
    )
    if request.GET.get("q"):
        qs = qs.filter(
            Q(username__icontains=request.GET["q"])
            | Q(first_name__icontains=request.GET["q"])
            | Q(last_name__icontains=request.GET["q"])
        )
    return render(request, "team.html", {"employees": qs})


@login_required
def employee_form(request, pk=None):
    require_admin(request.user)
    employee = get_object_or_404(get_user_model(), pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, instance=employee)
    if request.method == "POST" and form.is_valid():
        if (
            employee
            and employee.pk == request.user.pk
            and not form.cleaned_data["is_active"]
        ):
            form.add_error("is_active", "Bạn không thể khóa tài khoản đang sử dụng.")
        else:
            with transaction.atomic():
                saved = form.save()
            if saved.pk == request.user.pk:
                update_session_auth_hash(request, saved)
            messages.success(
                request,
                "Đã lưu nhân viên. Tên đăng nhập do quản trị viên quy định; người dùng tự đổi được mật khẩu.",
            )
            return redirect("team")
    return render(
        request, "employee_form.html", {"form": form, "editing": bool(employee)}
    )


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Đã đổi mật khẩu. Bạn vẫn đang đăng nhập.")
        return redirect("password_change")
    return render(request, "password_change.html", {"form": form})


@login_required
def reports(request):
    b = request_balances(request)
    warehouses = (
        b.values("warehouse__code", "warehouse__name")
        .annotate(total_value=Sum("value"), sku_count=Count("product", distinct=True))
        .order_by("warehouse__code")
    )
    return render(
        request,
        "reports.html",
        {
            "warehouse_totals": warehouses,
            "low": b.filter(quantity__lt=F("product__minimum")),
            "total_value": b.aggregate(n=Sum("value"))["n"] or 0,
            "receipt_exceptions": Line.objects.filter(
                document__in=scoped_documents(request)
                .filter(kind="IN")
                .exclude(status="CANCELLED")
            )
            .filter(
                Q(rejected_quantity__gt=0)
                | Q(expected_quantity__gt=F("quantity") + F("rejected_quantity"))
            )
            .select_related("document", "product")[:100],
            "overdue_loans": LoanHolding.objects.filter(
                loan_line__document__in=scoped_documents(request).filter(
                    kind="LOAN", due_date__lt=timezone.localdate()
                ),
                quantity__gt=0,
            ).select_related("loan_line__document", "loan_line__product")[:100],
            "pending_documents": scoped_documents(request)
            .filter(status__in=["DRAFT", "REJECTED", "TRANSIT"])
            .order_by("created_at")[:100],
        },
    )


@login_required
@permission_required("inventory.add_customfield", raise_exception=True)
def custom_fields(request):
    from django.forms import modelform_factory

    Form = modelform_factory(CustomField, fields=["key", "label"])
    form = Form(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, "Đã thêm trường. Trường mới sẽ hiện trên biểu mẫu hàng hóa."
        )
        return redirect("custom_fields")
    return render(
        request,
        "custom_fields.html",
        {"form": form, "fields": CustomField.objects.order_by("id")},
    )

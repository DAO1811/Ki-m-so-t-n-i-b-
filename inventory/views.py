import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, F, Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Document, Line, Product, Balance, Movement, LoanHolding
from .forms import DocumentForm, LineFormSet, ProductForm
from .services import warehouses_for, documents_for, post_document


def balances(user):
    return Balance.objects.filter(warehouse__in=warehouses_for(user)).select_related(
        "warehouse", "product"
    )


def export_csv(name, headers, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(
            [
                ("'" + str(v))
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                else v
                for v in row
            ]
        )
    return response


@login_required
def dashboard(request):
    b = balances(request.user)
    return render(
        request,
        "dashboard.html",
        {
            "warehouse_count": warehouses_for(request.user).count(),
            "product_count": Product.objects.count(),
            "pending": documents_for(request.user).filter(status="DRAFT").count(),
            "total_value": b.aggregate(n=Sum("value"))["n"] or 0,
            "transit_count": documents_for(request.user)
            .filter(status="TRANSIT")
            .count(),
            "low_count": b.filter(quantity__lt=F("product__minimum")).count(),
            "recent": documents_for(request.user).select_related(
                "source", "destination", "created_by"
            )[:6],
            "low": b.filter(quantity__lt=F("product__minimum"))[:6],
        },
    )


@login_required
def documents(request):
    qs = documents_for(request.user).select_related(
        "source", "destination", "created_by"
    )
    if request.GET.get("kind"):
        qs = qs.filter(kind=request.GET["kind"])
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    return render(
        request, "documents.html", {"documents": qs[:200], "kinds": Document.TYPES}
    )


@login_required
@permission_required("inventory.add_document", raise_exception=True)
def document_new(request):
    form = DocumentForm(request.POST or None, user=request.user)
    formset = LineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        items = [f.cleaned_data for f in formset if f.cleaned_data]
        if len({i["product"].pk for i in items}) != len(items):
            form.add_error(None, "Mỗi hàng hóa chỉ xuất hiện một lần trên phiếu.")
        elif (
            any(
                (
                    i["quantity"] < 0
                    if form.cleaned_data["kind"] == "COUNT"
                    else i["quantity"] <= 0
                )
                for i in items
            )
            and form.cleaned_data["kind"] != "ADJUST"
        ):
            form.add_error(None, "Số lượng phải dương; kiểm kê cho phép 0.")
        else:
            with transaction.atomic():
                doc = form.save(commit=False)
                doc.created_by = request.user
                doc.save()
                Line.objects.bulk_create([Line(document=doc, **i) for i in items])
            messages.success(
                request, "Đã lưu phiếu nháp. Kiểm tra rồi bấm Ghi sổ để cập nhật tồn."
            )
            return redirect("document_detail", pk=doc.pk)
    return render(
        request,
        "document_form.html",
        {
            "form": form,
            "formset": formset,
            "loans_data": list(
                form.fields["loan"].queryset.values("id", "source_id", "destination_id")
            ),
        },
    )


@login_required
@permission_required("inventory.add_document", raise_exception=True)
def document_edit(request, pk):
    doc = get_object_or_404(Document, pk=pk, created_by=request.user, status="DRAFT")
    form = DocumentForm(request.POST or None, user=request.user, instance=doc)
    initial = list(doc.lines.values("product", "quantity", "unit_price"))
    formset = LineFormSet(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        items = [f.cleaned_data for f in formset if f.cleaned_data]
        if len({i["product"].pk for i in items}) != len(items):
            form.add_error(None, "Mỗi hàng hóa chỉ xuất hiện một lần trên phiếu.")
        else:
            with transaction.atomic():
                locked = Document.objects.select_for_update().get(pk=pk)
                if locked.status != "DRAFT":
                    messages.error(request, "Phiếu đã được xử lý, không thể sửa.")
                    return redirect("document_detail", pk=pk)
                form.save()
                doc.lines.all().delete()
                Line.objects.bulk_create([Line(document=doc, **i) for i in items])
            messages.success(request, "Đã cập nhật phiếu nháp.")
            return redirect("document_detail", pk=pk)
    return render(
        request,
        "document_form.html",
        {
            "form": form,
            "formset": formset,
            "loans_data": list(
                form.fields["loan"].queryset.values("id", "source_id", "destination_id")
            ),
        },
    )


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(documents_for(request.user), pk=pk)
    receiving = doc.status == "TRANSIT" or not doc.source_id
    people = doc.destination.managers if receiving else doc.source.issue_approvers
    can_post = request.user.is_superuser or people.filter(pk=request.user.pk).exists()
    return render(
        request,
        "document_detail.html",
        {
            "doc": doc,
            "lines": doc.lines.select_related("product"),
            "can_post": can_post and doc.created_by_id != request.user.pk,
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
def stock(request):
    qs = balances(request.user).order_by("warehouse__code", "product__sku")
    if request.GET.get("warehouse"):
        qs = qs.filter(warehouse_id=request.GET["warehouse"])
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
    if request.GET.get("warehouse"):
        qs = qs.filter(warehouse_id=request.GET["warehouse"])
    if request.GET.get("product"):
        qs = qs.filter(product_id=request.GET["product"])
    # Balance after is persisted per movement, so filtered history retains true running balance.
    if request.GET.get("export"):
        return export_csv(
            "the-kho",
            [
                "Thời gian",
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
    for doc in (
        documents_for(request.user)
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
                }
            )
    return render(
        request,
        "loans.html",
        {
            "rows": rows,
            "transit_loans": documents_for(request.user)
            .filter(kind="LOAN", status="TRANSIT")
            .select_related("source", "destination"),
        },
    )


@login_required
def products(request):
    qs = Product.objects.all().order_by("sku")
    if request.GET.get("q"):
        qs = qs.filter(
            Q(name__icontains=request.GET["q"]) | Q(sku__icontains=request.GET["q"])
        )
    return render(request, "products.html", {"products": qs[:500]})


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
    from decimal import Decimal

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
        with transaction.atomic():
            doc, created = Document.objects.get_or_create(
                import_key=preview["key"],
                defaults={
                    "kind": "IN",
                    "destination": warehouse,
                    "created_by": request.user,
                    "note": preview["note"],
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
                    [
                        Line(
                            document=doc,
                            product_id=i["product_id"],
                            quantity=Decimal(i["quantity"]),
                            unit_price=Decimal(i["unit_price"]),
                        )
                        for i in preview["rows"]
                    ]
                )
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
                "rows": rows,
            }
            request.session["receipt_import"] = preview
        except ValidationError as exc:
            form.add_error("file", exc)
    return render(request, "receipt_import.html", {"form": form, "preview": preview})

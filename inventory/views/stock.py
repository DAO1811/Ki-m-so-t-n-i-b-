from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.exporting import export_csv
from inventory.views.common import date_range, request_balances

from ..models import (
    Balance,
    Line,
    LoanHolding,
    Movement,
    Product,
)
from ..services import (
    documents_for,
    warehouses_for,
)
from ..workspace import scoped_documents, selected_warehouse


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
        product = get_object_or_404(
            Product, pk=raw if raw.isdigit() and len(raw) <= 18 else 0
        )
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
def availability(request):
    raw = request.GET.get("warehouse", "")
    warehouse = get_object_or_404(
        warehouses_for(request.user), pk=raw if raw.isdigit() and len(raw) <= 18 else 0
    )
    loan_id = request.GET.get("loan", "")
    if loan_id:
        loan = get_object_or_404(
            documents_for(request.user),
            pk=loan_id if loan_id.isdigit() and len(loan_id) <= 18 else 0,
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

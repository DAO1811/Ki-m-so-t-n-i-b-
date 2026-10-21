from django.contrib.auth.decorators import login_required
from django.db.models import F, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from inventory.views.common import date_range, request_balances

from ..access import has_function
from ..models import (
    LoanHolding,
    Movement,
    Product,
)
from ..services import (
    approval_documents_for,
    warehouses_for,
)
from ..workspace import scoped_documents, selected_warehouse


@login_required
def dashboard(request):
    if not has_function(request.user, "dashboard_view"):
        return render(request, "access_home.html")
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

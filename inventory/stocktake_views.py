from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from .forms import StocktakeCountForm
from .access import has_function
from .models import StocktakeSession, LoanHolding
from .services import warehouses_for, can_approve_adjustments
from .stocktakes import (
    product_from_scan,
    save_count,
    start_session,
    submit_session,
    cancel_session,
)
from .workspace import selected_warehouse


def session_for(request, pk):
    from .models import Warehouse

    scope = (
        Warehouse.objects.all()
        if can_approve_adjustments(request.user)
        else warehouses_for(request.user)
    )
    return get_object_or_404(
        StocktakeSession.objects.select_related("warehouse", "created_by", "document"),
        pk=pk,
        warehouse__in=scope,
    )


@login_required
def stocktakes(request):
    warehouses = warehouses_for(request.user)
    if request.method == "POST":
        warehouse = get_object_or_404(
            warehouses,
            pk=request.POST.get("warehouse")
            if request.POST.get("warehouse", "").isdigit()
            and len(request.POST.get("warehouse", "")) <= 18
            else 0,
        )
        session = start_session(warehouse, request.user)
        request.session["warehouse_scope"] = str(warehouse.pk)
        return redirect("stocktake_detail", pk=session.pk)
    sessions = (
        StocktakeSession.objects.all()
        if can_approve_adjustments(request.user)
        else StocktakeSession.objects.filter(warehouse__in=warehouses)
    )
    sessions = sessions.select_related("warehouse", "created_by")
    current = selected_warehouse(request)
    if current:
        sessions = sessions.filter(warehouse=current)
    return render(
        request,
        "stocktakes.html",
        {"sessions": sessions[:100], "warehouses": warehouses},
    )


@login_required
def stocktake_detail(request, pk):
    session = session_for(request, pk)
    return render(
        request,
        "stocktake_detail.html",
        {
            "session": session,
            "items": session.items.select_related("product"),
            "events": session.events.select_related("item__product", "actor")[:100],
            "can_edit": session.created_by_id == request.user.pk
            and session.status == "OPEN"
            and has_function(request.user, "stocktakes_create")
            and session.business_date == timezone.localdate(),
            "can_cancel": session.status == "OPEN"
            and has_function(request.user, "stocktakes_create")
            and (session.created_by_id == request.user.pk or request.user.is_superuser),
            "counted": session.items.filter(counted_quantity__isnull=False).count(),
            "item_count": session.items.count(),
        },
    )


@login_required
def stocktake_lookup(request, pk):
    session = session_for(request, pk)
    try:
        product = product_from_scan(request.GET.get("code", "")[:500])
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    item = session.items.filter(product=product).first()
    held = (
        LoanHolding.objects.filter(
            loan_line__document__destination=session.warehouse,
            loan_line__product=product,
        ).aggregate(n=Sum("quantity"))["n"]
        or 0
    )
    photo = product.photos.first()
    from django.urls import reverse

    return JsonResponse(
        {
            "product": {
                "sku": product.sku,
                "name": product.name,
                "unit": product.unit,
                "image": reverse("private_file", args=[photo.file_id])
                if photo
                else None,
            },
            "counted": str(item.counted_quantity)
            if item and item.counted_quantity is not None
            else None,
            "book": str(item.book_quantity) if item else "0",
            "revision": item.revision if item else 1,
            "unit_price": str(item.unit_price)
            if item and item.unit_price is not None
            else "",
            "note": item.note if item else "",
            "borrowed": str(held),
        }
    )


@login_required
@require_POST
def stocktake_count(request, pk):
    session_for(request, pk)
    form = StocktakeCountForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "error": " ".join(
                    error for errors in form.errors.values() for error in errors
                )
            },
            status=400,
        )
    data = form.cleaned_data
    try:
        product = product_from_scan(data.pop("code"))
        item, replay = save_count(pk, request.user, product, **data)
        return JsonResponse(
            {
                "quantity": str(item.counted_quantity),
                "revision": item.revision,
                "replay": replay,
                "difference": str(item.difference),
                "counted_count": item.session.items.filter(
                    counted_quantity__isnull=False
                ).count(),
                "total_count": item.session.items.count(),
            }
        )
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)


@login_required
@require_POST
def stocktake_submit(request, pk):
    session_for(request, pk)
    try:
        doc = submit_session(pk, request.user, request.POST.get("note", "")[:4000])
        if doc is None:
            messages.success(
                request,
                "Đã chốt biên bản, không có chênh lệch nên không tạo phiếu điều chỉnh. Tồn không đổi.",
            )
            return redirect("stocktake_detail", pk=pk)
        messages.success(
            request,
            "Đã chốt biên bản và lập phiếu điều chỉnh chờ Tổng giám đốc duyệt. Tồn chưa thay đổi.",
        )
        return redirect("document_detail", pk=doc.pk)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("stocktake_detail", pk=pk)


@login_required
@require_POST
def stocktake_cancel(request, pk):
    session_for(request, pk)
    try:
        cancel_session(pk, request.user, request.POST.get("reason", "")[:1000])
        messages.success(request, "Đã hủy phiên, giữ lịch sử quét; tồn không thay đổi.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("stocktake_detail", pk=pk)


@login_required
def stocktake_report(request, pk):
    session = session_for(request, pk)
    items = list(session.items.select_related("product"))
    return render(
        request,
        "stocktake_report.html",
        {
            "session": session,
            "items": items,
            "counted": sum(item.counted_quantity is not None for item in items),
            "company_name": settings.INVENTORY_COMPANY_NAME,
        },
    )

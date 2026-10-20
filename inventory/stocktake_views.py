from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import has_function
from .forms import StocktakeCountForm
from .models import LoanHolding, StocktakeSession
from .services import can_approve_adjustments, warehouses_for
from .stocktakes import (
    begin_session,
    cancel_session,
    freeze_session,
    product_from_scan,
    require_open,
    save_count,
    submit_session,
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
        StocktakeSession.objects.select_related(
            "warehouse", "created_by", "counted_by", "document"
        ),
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
        try:
            session = freeze_session(warehouse, request.user)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("stocktakes")
        request.session["warehouse_scope"] = str(warehouse.pk)
        return redirect("stocktake_detail", pk=session.pk)
    sessions = (
        StocktakeSession.objects.all()
        if can_approve_adjustments(request.user)
        else StocktakeSession.objects.filter(warehouse__in=warehouses)
    )
    sessions = sessions.select_related(
        "warehouse", "created_by", "counted_by", "document"
    )
    ready = sessions.filter(status="READY")
    current = selected_warehouse(request)
    if current:
        sessions = sessions.filter(warehouse=current)
    return render(
        request,
        "stocktakes.html",
        {
            "sessions": sessions.exclude(status="READY")[:100],
            "ready_sessions": ready,
            "warehouses": warehouses,
        },
    )


@login_required
def stocktake_detail(request, pk):
    session = session_for(request, pk)
    return render(
        request,
        "stocktake_detail.html",
        {
            "session": session,
            "expired": session.business_date != timezone.localdate(),
            "items": session.items.select_related("product"),
            "events": session.events.select_related("item__product", "actor")[:100],
            "can_manage": has_function(request.user, "stocktakes_create")
            and warehouses_for(request.user).filter(pk=session.warehouse_id).exists(),
            "can_edit": (
                session.counter_id == request.user.pk or request.user.is_superuser
            )
            and session.status == "OPEN"
            and has_function(request.user, "stocktakes_create")
            and session.business_date == timezone.localdate(),
            "can_cancel": session.status in ["READY", "OPEN"]
            and has_function(request.user, "stocktakes_create")
            and (
                request.user.pk in {session.created_by_id, session.counter_id}
                or request.user.is_superuser
            ),
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
        "stocktake_worksheet.html"
        if request.GET.get("worksheet") == "1"
        else "stocktake_report.html",
        {
            "session": session,
            "items": items,
            "counted": sum(item.counted_quantity is not None for item in items),
            "company_name": settings.INVENTORY_COMPANY_NAME,
        },
    )


@login_required
@require_POST
def stocktake_begin(request, pk):
    session_for(request, pk)
    try:
        session = begin_session(pk, request.user, request.POST.get("method", ""))
        request.session["warehouse_scope"] = str(session.warehouse_id)
        return redirect(
            "stocktake_paper" if session.method == "PAPER" else "stocktake_detail",
            pk=pk,
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("stocktake_detail", pk=pk)


@login_required
def stocktake_paper(request, pk):
    from uuid import uuid4

    from django.urls import reverse

    from .stocktake_forms import PaperCountFormSet

    session = session_for(request, pk)
    try:
        require_open(session, request.user)
    except ValidationError as exc:
        messages.info(request, " ".join(exc.messages))
        return redirect("stocktake_detail", pk=pk)
    if session.method != "PAPER":
        messages.info(
            request, "Phiên này kiểm bằng QR. Ghi số tại màn hình kiểm kê của phiên."
        )
        return redirect("stocktake_detail", pk=pk)
    items = session.items.select_related("product").order_by("sku_snapshot", "pk")
    query = request.GET.get("q", "").strip()
    if query:
        items = items.filter(
            Q(sku_snapshot__icontains=query) | Q(name_snapshot__icontains=query)
        )
    if request.GET.get("remaining") == "1":
        items = items.filter(counted_quantity__isnull=True)
    page = Paginator(items, 25).get_page(request.GET.get("page"))
    visible_ids = [item.pk for item in page]
    visible = (
        session.items.filter(pk__in=visible_ids)
        .select_related("product")
        .order_by("sku_snapshot", "pk")
    )
    action = request.POST.get("action", "save")
    formset = PaperCountFormSet(
        request.POST if request.method == "POST" and action == "save" else None,
        queryset=visible,
    )
    for form in formset:
        form.fields["id"].queryset = visible
    extra_errors = []
    if request.method == "POST" and action == "extra":
        data = request.POST.copy()
        data.update(mode="SET", request_id=str(uuid4()), revision="1")
        extra = StocktakeCountForm(data)
        if extra.is_valid():
            try:
                cleaned = extra.cleaned_data
                product = product_from_scan(cleaned.pop("code"))
                if session.items.filter(product=product).exists():
                    raise ValidationError(
                        "Mã đã có trong bảng. Tìm mã đó và ghi số tại dòng tương ứng để tránh đếm hai lần."
                    )
                save_count(pk, request.user, product, **cleaned)
                return redirect(
                    reverse("stocktake_paper", args=[pk])
                    + "?"
                    + urlencode({"q": product.sku})
                )
            except ValidationError as exc:
                extra_errors = exc.messages
        else:
            extra_errors = [
                error for errors in extra.errors.values() for error in errors
            ]
    elif request.method == "POST" and action == "save" and formset.is_valid():
        try:
            with transaction.atomic():
                locked = StocktakeSession.objects.select_for_update().get(pk=pk)
                require_open(locked, request.user)
                saved = 0
                for form in formset:
                    data = form.cleaned_data
                    if form.has_changed() and data.get("counted_quantity") is not None:
                        item = data["id"]
                        save_count(
                            pk,
                            request.user,
                            item.product,
                            "SET",
                            data["counted_quantity"],
                            data.get("unit_price"),
                            data.get("note", ""),
                            uuid4(),
                            data["revision"],
                        )
                        saved += 1
            messages.success(
                request, f"Đã ghi số kiểm đếm cho {saved} mã. Tồn kho chưa thay đổi."
            )
            return redirect(request.get_full_path())
        except ValidationError as exc:
            extra_errors = exc.messages
    return render(
        request,
        "stocktake_paper.html",
        {
            "session": session,
            "formset": formset,
            "page_obj": page,
            "counted": session.items.filter(counted_quantity__isnull=False).count(),
            "total": session.items.count(),
            "extra_errors": extra_errors,
        },
    )

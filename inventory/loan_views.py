from uuid import UUID, uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .access import has_function
from .loan_forms import LoanReturnForm
from .loan_returns import (
    require_return_access,
    return_items,
    return_items_batch,
    save_return,
)
from .models import Document
from .services import approval_block_reason, can_approve, documents_for, warehouses_for
from .workspace import scoped_documents


def loan_dashboard(request):
    qs = (
        scoped_documents(request)
        .filter(kind="LOAN", status="POSTED")
        .select_related("source", "destination", "created_by")
    )
    query = request.GET.get("q", "").strip()
    if query:
        search = (
            Q(source__name__icontains=query)
            | Q(destination__name__icontains=query)
            | Q(lines__product__sku__icontains=query)
            | Q(lines__product__name__icontains=query)
        )
        number = query.upper().removeprefix("PK-")
        if number.isdigit() and len(number) <= 18:
            search |= Q(pk=int(number))
        qs = qs.filter(search).distinct()
    state = request.GET.get("state", "outstanding")
    warehouse_ids = set(warehouses_for(request.user).values_list("pk", flat=True))
    visible_returns = (
        scoped_documents(request)
        .filter(kind="RETURN")
        .select_related("source", "destination", "created_by")
    )
    groups = []
    loans = list(qs)
    quantities = return_items_batch(loans)
    linked_returns = {}
    for doc in visible_returns.filter(loan_id__in=[loan.pk for loan in loans]):
        linked_returns.setdefault(doc.loan_id, []).append(doc)
    # Each original loan appears once. Counts remain per product/unit.
    for loan in loans:
        items = quantities[loan.pk]
        outstanding = any(item["outstanding"] > 0 for item in items)
        returns = linked_returns.get(loan.pk, [])
        pending = any(
            item["pending_draft"] or item["in_transit"] for item in items
        ) or any(doc.status == "REJECTED" for doc in returns)
        if (
            (state == "outstanding" and not outstanding)
            or (state == "completed" and outstanding)
            or (state == "pending" and not pending)
        ):
            continue
        groups.append(
            dict(
                loan=loan,
                items=items,
                can_start_return=loan.destination_id in warehouse_ids
                and has_function(request.user, "returns_create"),
                has_available=any(item["available"] > 0 for item in items),
                has_pending=pending,
                overdue=outstanding
                and bool(loan.due_date and loan.due_date < timezone.localdate()),
                returns=[
                    dict(
                        document=doc,
                        can_approve=can_approve(doc, request.user),
                        reason=approval_block_reason(doc, request.user),
                        can_edit=doc.created_by_id == request.user.pk
                        and doc.status in ["DRAFT", "REJECTED"]
                        and has_function(request.user, "returns_create"),
                    )
                    for doc in returns
                ],
            )
        )
    page = Paginator(groups, 15).get_page(request.GET.get("page"))
    standalone_returns = visible_returns.filter(
        status__in=["DRAFT", "TRANSIT", "REJECTED"]
    ).exclude(loan_id__in=[group["loan"].pk for group in page])
    if query:
        search = (
            Q(source__name__icontains=query)
            | Q(destination__name__icontains=query)
            | Q(lines__product__sku__icontains=query)
            | Q(lines__product__name__icontains=query)
        )
        number = query.upper().removeprefix("PK-")
        if number.isdigit() and len(number) <= 18:
            search |= Q(pk=int(number)) | Q(loan_id=int(number))
        standalone_returns = standalone_returns.filter(search).distinct()
    return render(
        request,
        "loans.html",
        dict(
            loan_groups=page,
            page_obj=page,
            transit_loans=scoped_documents(request)
            .filter(kind="LOAN", status__in=["DRAFT", "TRANSIT"])
            .select_related("source", "destination", "created_by"),
            return_documents=standalone_returns[:25],
        ),
    )


def return_response(request, loan, editing=None):
    require_return_access(loan, request.user)
    if request.method == "POST" and not editing:
        try:
            key = UUID(request.POST.get("submission_key", ""))
        except (ValueError, AttributeError):
            key = None
        if key:
            previous = Document.objects.filter(
                import_key=key, kind="RETURN", loan=loan, created_by=request.user
            ).first()
            if previous:
                return redirect("document_detail", pk=previous.pk)
    items = return_items(loan, exclude_document=editing.pk if editing else None)
    form = LoanReturnForm(request.POST or None, items=items, editing=editing)
    if request.method == "POST" and form.is_valid():
        try:
            doc = save_return(
                loan.pk,
                request.user,
                form.quantities,
                note=form.cleaned_data["note"],
                submission_key=form.cleaned_data.get("submission_key") or uuid4(),
                editing_id=editing.pk if editing else None,
                revision=form.cleaned_data.get("revision"),
            )
            messages.success(
                request,
                "Đã lưu phiếu trả chờ duyệt. Sau khi duyệt chuyển trả, kho cho mượn xác nhận nhận lại hàng để hoàn tất.",
            )
            return redirect("document_detail", pk=doc.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "loan_return.html",
        dict(
            loan=loan,
            form=form,
            editing=editing,
            return_rows=[
                dict(item=item, field=form[f"quantity_{item['product'].pk}"])
                for item in items
            ],
            today=timezone.localdate(),
        ),
    )


@login_required
def loan_return(request, pk):
    loan = get_object_or_404(
        documents_for(request.user).select_related("source", "destination"),
        pk=pk,
        kind="LOAN",
        status="POSTED",
    )
    return return_response(request, loan)


@login_required
def loan_return_edit(request, pk):
    doc = get_object_or_404(
        documents_for(request.user),
        pk=pk,
        kind="RETURN",
        created_by=request.user,
        status__in=["DRAFT", "REJECTED"],
    )
    loan = get_object_or_404(
        documents_for(request.user).select_related("source", "destination"),
        pk=doc.loan_id,
        kind="LOAN",
        status="POSTED",
    )
    return return_response(request, loan, editing=doc)

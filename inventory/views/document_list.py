from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from core.exporting import export_csv
from inventory.views.common import date_range

from ..access import (
    can_view_kind,
    is_admin,
)
from ..models import Document
from ..services import (
    approval_documents_for,
    documents_for,
)
from ..workspace import scoped_documents, selected_warehouse


@login_required
def documents(request):
    import_batch = None
    if request.GET.get("import_batch"):
        result = next(
            (
                request.session.get(name, {})
                for name in ("product_import_result", "receipt_import_result")
                if request.session.get(name, {}).get("owner") == request.user.pk
                and request.session.get(name, {}).get("key")
                == request.GET["import_batch"]
            ),
            {},
        )
        if result:
            import_batch = result
            qs = documents_for(request.user).filter(
                pk__in=result.get("document_ids", [])
            )
        else:
            qs = Document.objects.none()
    else:
        qs = scoped_documents(request)
    qs = qs.select_related("source", "destination", "created_by")
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
        {
            "documents": page,
            "import_batch": import_batch,
            "page_obj": page,
            "kinds": [
                (key, label)
                for key, label in Document.TYPES
                if can_view_kind(request.user, key)
            ],
        },
    )


@login_required
def approvals(request):
    actionable = approval_documents_for(request.user)
    monitoring = is_admin(request.user) and request.GET.get("scope") != "actionable"
    qs = (documents_for(request.user) if monitoring else actionable).select_related(
        "source", "destination", "created_by"
    )
    status = request.GET.get("status", "")
    if status in dict(Document._meta.get_field("status").choices):
        qs = qs.filter(status=status)
    elif monitoring:
        qs = qs.filter(status__in=["DRAFT", "TRANSIT", "REJECTED"])
    kind = request.GET.get("kind", "")
    if kind in dict(Document.TYPES):
        qs = qs.filter(kind=kind)
    if request.GET.get("q"):
        query = request.GET["q"].strip()
        search = Q(created_by__username__icontains=query) | Q(
            reference_number__icontains=query
        )
        number = query.upper().removeprefix("PK-")
        if number.isdigit() and len(number) <= 18:
            search |= Q(pk=int(number))
        qs = qs.filter(search)
    warehouse = selected_warehouse(request)
    if warehouse:
        qs = qs.filter(Q(source=warehouse) | Q(destination=warehouse))
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    from ..services import approval_block_reason

    for doc in page:
        doc.review_reason = approval_block_reason(doc, request.user)
    return render(
        request,
        "approvals.html",
        {
            "documents": page,
            "page_obj": page,
            "approval_total": qs.count(),
            "monitoring": monitoring,
            "show_review_reason": True,
            "kinds": Document.TYPES,
            "statuses": Document._meta.get_field("status").choices,
        },
    )

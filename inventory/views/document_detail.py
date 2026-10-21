from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..access import (
    can_create_kind,
    has_function,
    is_admin,
)
from ..services import (
    can_approve,
    close_document,
    documents_for,
    post_document,
    warehouses_for,
)


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(documents_for(request.user), pk=pk)
    from ..access import may_attach
    from ..forms import ReceiptAttachmentForm

    can_post = can_approve(doc, request.user)
    receiving = doc.status == "TRANSIT" or not doc.source_id
    candidates = (
        doc.destination.managers if receiving else doc.source.issue_approvers
    ).all()
    from ..hierarchy import LEVEL_LABELS, maker_level
    from ..services import approval_block_reason

    approvers = [person for person in candidates if can_approve(doc, person)]
    can_return_loan = False
    if (
        doc.kind == "LOAN"
        and doc.status == "POSTED"
        and has_function(request.user, "returns_create")
    ):
        from ..loan_returns import return_items

        can_return_loan = warehouses_for(request.user).filter(
            pk=doc.destination_id
        ).exists() and any(item["available"] > 0 for item in return_items(doc))
    return render(
        request,
        "document_detail.html",
        {
            "doc": doc,
            "can_return_loan": can_return_loan,
            "related_returns": documents_for(request.user).filter(
                kind="RETURN", loan=doc
            )
            if doc.kind == "LOAN"
            else [],
            "can_view_return_loan": doc.kind == "RETURN"
            and documents_for(request.user).filter(pk=doc.loan_id).exists(),
            "lines": doc.lines.select_related("product"),
            "can_post": can_post,
            "self_approval": can_post
            and is_admin(request.user)
            and doc.created_by_id == request.user.pk,
            "approval_block_reason": approval_block_reason(doc, request.user),
            "maker_level_label": LEVEL_LABELS.get(maker_level(doc), "Nhân viên"),
            "approvers": approvers,
            "events": doc.events.select_related("actor"),
            "attachment_form": ReceiptAttachmentForm(
                initial={"invoice_number": doc.reference_number}
            ),
            "attachments": doc.attachments.select_related("uploaded_by", "voided_by")
            if has_function(request.user, "files_view")
            else doc.attachments.none(),
            "can_attach": may_attach(doc, request.user),
            "can_void_attachment": may_attach(doc, request.user, void=True),
            "can_edit_doc": can_create_kind(request.user, doc.kind),
            "qr_session": getattr(doc, "stocktake_session", None),
            "can_cancel": doc.status in ["DRAFT", "REJECTED"]
            and can_create_kind(request.user, doc.kind)
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
                    line.quantity * line.unit_price
                    for line in doc.lines.all()
                    if line.unit_price is not None
                ),
                Decimal(0),
            ),
        },
    )


@login_required
@require_POST
def document_post(request, pk):
    doc = get_object_or_404(documents_for(request.user), pk=pk)
    if doc.status in ["DRAFT", "TRANSIT"] and not can_approve(doc, request.user):
        raise PermissionDenied(
            "Bạn chưa đủ cấp, quyền hoặc phân công kho để duyệt phiếu này."
        )
    try:
        expected_status = request.POST.get("expected_status", "")
        raw_revision = request.POST.get("expected_revision", "")
        if (
            expected_status not in ["DRAFT", "TRANSIT"]
            or not raw_revision.isascii()
            or not raw_revision.isdigit()
            or len(raw_revision) > 10
            or not 1 <= int(raw_revision) <= 2147483647
        ):
            raise ValidationError(
                "Thông tin xác nhận phiếu chưa hợp lệ. Hãy tải lại phiếu và thực hiện lại thao tác."
            )
        result = post_document(
            pk,
            request.user,
            confirm_self_approval=request.POST.get("confirm_self_approval") == "yes",
            expected_status=expected_status,
            expected_revision=int(raw_revision),
        )
        messages.success(
            request,
            (
                "Đã duyệt chuyển trả. Chờ kho cho mượn xác nhận nhận lại hàng."
                if result.kind == "RETURN"
                else "Đã xuất kho, đang chờ kho nhận xác nhận."
            )
            if result.status == "TRANSIT"
            else (
                "Đã xác nhận nhận lại hàng và cộng tồn về kho cho mượn."
                if result.kind == "RETURN"
                else "Đã ghi sổ và cập nhật tồn kho."
            ),
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

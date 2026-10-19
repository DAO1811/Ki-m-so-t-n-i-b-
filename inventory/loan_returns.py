"""Return quantities tied to one original loan, with draft reservations."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .access import has_function
from .models import Document, Line, LoanHolding
from .services import (
    audit_document,
    capture_lines,
    documents_for,
    validate_document,
    warehouses_for,
)


def return_items_batch(loans, *, exclude_document=None):
    from django.db.models import prefetch_related_objects

    loans = list(loans)
    if not loans:
        return {}
    prefetch_related_objects(loans, "lines__product")
    ids = [loan.pk for loan in loans]
    totals = {}
    returns = Line.objects.filter(
        document__kind="RETURN",
        document__loan_id__in=ids,
        document__status__in=["DRAFT", "TRANSIT", "POSTED"],
    )
    if exclude_document:
        returns = returns.exclude(document_id=exclude_document)
    for row in returns.values(
        "document__loan_id", "product_id", "document__status"
    ).annotate(quantity=Sum("quantity")):
        totals[
            (row["document__loan_id"], row["product_id"], row["document__status"])
        ] = row["quantity"]
    holdings = dict(
        LoanHolding.objects.filter(loan_line__document_id__in=ids).values_list(
            "loan_line_id", "quantity"
        )
    )
    result = {}
    for loan in loans:
        items = []
        for line in sorted(loan.lines.all(), key=lambda line: line.pk):
            returned = totals.get((loan.pk, line.product_id, "POSTED"), Decimal(0))
            draft = totals.get((loan.pk, line.product_id, "DRAFT"), Decimal(0))
            transit = totals.get((loan.pk, line.product_id, "TRANSIT"), Decimal(0))
            holding = holdings.get(line.pk, Decimal(0))
            items.append(
                dict(
                    product=line.product,
                    borrowed=line.quantity,
                    returned=returned,
                    pending_draft=draft,
                    in_transit=transit,
                    available=max(Decimal(0), holding - draft),
                    outstanding=max(Decimal(0), line.quantity - returned),
                )
            )
        result[loan.pk] = items
    return result


def return_items(loan, *, exclude_document=None):
    return return_items_batch([loan], exclude_document=exclude_document)[loan.pk]


def require_return_access(loan, user):
    if (
        not has_function(user, "returns_create")
        or not has_function(user, "loans_view")
        or not documents_for(user).filter(pk=loan.pk).exists()
        or not warehouses_for(user).filter(pk=loan.destination_id).exists()
    ):
        raise PermissionDenied(
            "Bạn cần quyền lập phiếu trả và quyền tại kho đang mượn hàng."
        )
    if loan.kind != "LOAN" or loan.status != "POSTED":
        raise ValidationError(
            "Lệnh mượn phải hoàn tất bước nhận hàng trước khi lập trả."
        )


@transaction.atomic
def save_return(
    loan_id,
    user,
    quantities,
    *,
    note="",
    submission_key=None,
    editing_id=None,
    revision=None,
):
    """Serialize new/edit drafts on the original loan; no inventory changes here."""
    editing = None
    if editing_id:
        editing = Document.objects.select_for_update().get(pk=editing_id)
        if editing.created_by_id != user.pk or editing.kind != "RETURN":
            raise PermissionDenied("Chỉ người lập được sửa phiếu trả của mình.")
        if editing.status not in ["DRAFT", "REJECTED"]:
            raise ValidationError("Phiếu đã được duyệt chuyển trả, không thể sửa.")
        if editing.revision != revision:
            raise ValidationError(
                "Phiếu đã thay đổi ở cửa sổ khác. Mở lại phiếu mới nhất trước khi sửa."
            )
        if editing.loan_id != loan_id:
            raise ValidationError(
                "Không đổi lệnh mượn gốc của phiếu trả. Hủy phiếu chờ nếu cần lập lại."
            )
    loan = Document.objects.select_for_update().get(pk=loan_id)
    require_return_access(loan, user)
    if not editing and submission_key:
        previous = Document.objects.filter(import_key=submission_key).first()
        if previous:
            if (
                previous.created_by_id != user.pk
                or previous.kind != "RETURN"
                or previous.loan_id != loan.pk
            ):
                raise PermissionDenied(
                    "Mã phiên lập phiếu không thuộc lần trả hàng này."
                )
            return previous
    items = {
        row["product"].pk: row
        for row in return_items(loan, exclude_document=editing_id)
    }
    cleaned = {}
    for product_id, quantity in quantities.items():
        if product_id not in items:
            raise ValidationError("Có mã hàng không thuộc lệnh mượn gốc.")
        try:
            quantity = Decimal(str(quantity))
            if (
                not quantity.is_finite()
                or quantity < 0
                or quantity.as_tuple().exponent < -3
            ):
                raise ValueError
        except (ValueError, ArithmeticError):
            raise ValidationError(
                "Số trả phải từ 0 trở lên, tối đa 3 chữ số thập phân."
            )
        if quantity > items[product_id]["available"]:
            raise ValidationError(
                f"{items[product_id]['product']}: chỉ còn {items[product_id]['available']:f} có thể lập trả. Kiểm tra phiếu đang chờ duyệt hoặc đang chuyển trả."
            )
        if quantity:
            cleaned[product_id] = quantity
    if not cleaned:
        raise ValidationError("Nhập số thực trả lớn hơn 0 cho ít nhất một mặt hàng.")
    doc = editing or Document(
        kind="RETURN",
        created_by=user,
        loan=loan,
        source=loan.destination,
        destination=loan.source,
        import_key=submission_key,
    )
    doc.business_date = timezone.localdate()
    doc.note = note.strip()
    doc.status = "DRAFT"
    doc.closure_reason = ""
    if editing:
        doc.revision += 1
    validate_document(doc)
    doc.save()
    if editing:
        doc.lines.all().delete()
    Line.objects.bulk_create(
        capture_lines(
            doc,
            [
                Line(document=doc, product=items[pid]["product"], quantity=qty)
                for pid, qty in cleaned.items()
            ],
        )
    )
    audit_document(doc, user, "EDIT" if editing else "CREATE")
    return doc

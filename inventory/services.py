from decimal import Decimal, ROUND_HALF_UP, localcontext
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Warehouse, Document, Balance, Movement, LoanHolding


def warehouses_for(user):
    return (
        Warehouse.objects.all()
        if user.is_superuser
        else Warehouse.objects.filter(
            Q(members=user) | Q(managers=user) | Q(issue_approvers=user)
        ).distinct()
    )


def documents_for(user):
    if user.is_superuser:
        return Document.objects.all()
    ids = warehouses_for(user).values_list("id", flat=True)
    return Document.objects.filter(
        Q(source_id__in=ids) | Q(destination_id__in=ids) | Q(created_by=user)
    ).distinct()


def validate_document(doc):
    transfer = doc.kind in ["TRANSFER", "LOAN", "RETURN"]
    if doc.kind not in dict(Document.TYPES):
        raise ValidationError("Loại phiếu không hợp lệ.")
    needs_source = doc.kind == "OUT" or transfer
    needs_dest = doc.kind in ["IN", "COUNT", "ADJUST"] or transfer
    if bool(doc.source_id) != needs_source or bool(doc.destination_id) != needs_dest:
        raise ValidationError(
            "Chọn đúng kho xuất / kho nhập theo loại phiếu. Nhập, kiểm kê, điều chỉnh chỉ dùng kho nhập; xuất chỉ dùng kho xuất."
        )
    if transfer and doc.source_id == doc.destination_id:
        raise ValidationError("Hai kho phải khác nhau.")
    if doc.kind in ["COUNT", "ADJUST"] and not doc.note.strip():
        raise ValidationError("Kiểm kê và điều chỉnh phải ghi lý do.")
    if doc.kind == "RETURN":
        if not doc.loan_id:
            raise ValidationError("Phải chọn phiếu mượn gốc.")
        loan = doc.loan
        if (
            loan.kind != "LOAN"
            or loan.status != "POSTED"
            or doc.source_id != loan.destination_id
            or doc.destination_id != loan.source_id
        ):
            raise ValidationError(
                "Phiếu trả phải đảo chiều kho của phiếu mượn đã ghi sổ."
            )
    elif doc.loan_id:
        raise ValidationError("Chỉ phiếu trả mới được chọn phiếu mượn gốc.")


def approval_documents_for(user):
    qs = documents_for(user).exclude(created_by=user)
    if user.is_superuser:
        return qs.filter(status__in=["DRAFT", "TRANSIT"])
    source_ids = user.issue_warehouses.values_list("id", flat=True)
    dest_ids = user.managed_warehouses.values_list("id", flat=True)
    return qs.filter(
        Q(status="TRANSIT", destination_id__in=dest_ids)
        | Q(status="DRAFT", source_id__in=source_ids)
        | Q(status="DRAFT", source__isnull=True, destination_id__in=dest_ids)
    ).distinct()


def can_approve(doc, user):
    if doc.status not in ["DRAFT", "TRANSIT"] or doc.created_by_id == user.pk:
        return False
    if user.is_superuser:
        return True
    receiving = doc.status == "TRANSIT" or not doc.source_id
    warehouse = doc.destination if receiving else doc.source
    return bool(
        warehouse
        and (warehouse.managers if receiving else warehouse.issue_approvers)
        .filter(pk=user.pk)
        .exists()
    )


def require_approver(doc, user, receiving):
    if doc.created_by_id == user.pk:
        raise PermissionDenied(
            "Người lập phiếu không được tự xác nhận. Hãy nhờ người được chỉ định duyệt."
        )
    if not can_approve(doc, user):
        raise PermissionDenied("Bạn chưa được chỉ định duyệt tại kho này.")


def record(doc, line, wid, delta, value_delta):
    balance, _ = Balance.objects.get_or_create(warehouse_id=wid, product=line.product)
    balance = Balance.objects.select_for_update().get(pk=balance.pk)
    if balance.quantity + delta < 0:
        raise ValidationError(
            f"{line.product}: không đủ tồn kho (còn {balance.quantity})."
        )
    if balance.quantity + delta >= Decimal("1e13"):
        raise ValidationError(f"{line.product}: số tồn vượt giới hạn lưu trữ.")
    if abs(balance.value + value_delta) >= Decimal("1e20"):
        raise ValidationError(f"{line.product}: giá trị tồn vượt giới hạn lưu trữ.")
    balance.quantity += delta
    balance.value += value_delta
    balance.save(update_fields=["quantity", "value"])
    Movement.objects.create(
        document=doc,
        warehouse_id=wid,
        product=line.product,
        delta=delta,
        balance_after=balance.quantity,
        value_delta=value_delta,
        value_after=balance.value,
    )


@transaction.atomic
def post_document(pk, user):
    doc = Document.objects.select_for_update().get(pk=pk)
    if doc.status == "POSTED":
        raise ValidationError("Phiếu đã ghi sổ trước đó.")
    transfer = doc.kind in ["TRANSFER", "LOAN", "RETURN"]
    receiving = doc.status == "TRANSIT" or not doc.source_id
    require_approver(doc, user, receiving)
    validate_document(doc)
    lines = list(doc.lines.select_related("product").order_by("product_id"))
    if not lines:
        raise ValidationError("Phiếu cần ít nhất một dòng hàng.")
    # Reserve return quantities at dispatch; pending returns count toward the loan limit.
    if doc.kind == "RETURN" and doc.status == "DRAFT":
        loan = Document.objects.select_for_update().get(pk=doc.loan_id)
        borrowed = {l.product_id: l.quantity for l in loan.lines.all()}
        for line in lines:
            from .models import Line

            returned = Line.objects.filter(
                document__loan=loan,
                document__status__in=["TRANSIT", "POSTED"],
                product_id=line.product_id,
            ).aggregate(n=Sum("quantity"))["n"] or Decimal(0)
            if line.quantity > borrowed.get(line.product_id, Decimal(0)) - returned:
                raise ValidationError(
                    f"{line.product}: số trả vượt số còn mượn (bao gồm hàng đang trả)."
                )
    list(
        Warehouse.objects.select_for_update()
        .filter(pk__in=sorted(filter(None, [doc.source_id, doc.destination_id])))
        .order_by("pk")
    )

    def money(v):
        with localcontext() as context:
            context.prec = 50
            if abs(v) >= Decimal("1e20"):
                raise ValidationError(
                    "Giá trị phiếu vượt giới hạn lưu trữ. Hãy kiểm tra số lượng và đơn giá."
                )
            return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    for line in lines:
        q = line.quantity
        if (doc.kind not in ["COUNT", "ADJUST"] and q <= 0) or (
            doc.kind == "COUNT" and q < 0
        ):
            raise ValidationError(
                "Số lượng không hợp lệ; kiểm kê được nhập 0, điều chỉnh được nhập số âm."
            )
        if line.unit_price is not None and line.unit_price < 0:
            raise ValidationError("Đơn giá không được âm.")
        if doc.status == "TRANSIT":
            if doc.kind == "LOAN":
                LoanHolding.objects.create(
                    loan_line=line, quantity=q, value=line.book_value
                )
            else:
                record(doc, line, doc.destination_id, q, line.book_value)
        elif doc.kind == "RETURN":
            holding = LoanHolding.objects.select_for_update().get(
                loan_line__document=doc.loan, loan_line__product=line.product
            )
            if q > holding.quantity:
                raise ValidationError(f"{line.product}: không đủ tồn mượn tạm để trả.")
            cost = (
                holding.value
                if q == holding.quantity
                else money(q * holding.value / holding.quantity)
            )
            holding.quantity -= q
            holding.value -= cost
            holding.save(update_fields=["quantity", "value"])
            line.book_value = cost
            line.save(update_fields=["book_value"])
        elif doc.source_id:
            source, _ = Balance.objects.get_or_create(
                warehouse_id=doc.source_id, product=line.product
            )
            if q > source.quantity:
                raise ValidationError(
                    f"{line.product}: không đủ tồn kho (còn {source.quantity})."
                )
            cost = (
                source.value
                if q == source.quantity
                else money(q * source.value / source.quantity)
            )
            record(doc, line, doc.source_id, -q, -cost)
            line.book_value = cost
            line.save(update_fields=["book_value"])
        else:
            dest, _ = Balance.objects.get_or_create(
                warehouse_id=doc.destination_id, product=line.product
            )
            delta = q - dest.quantity if doc.kind == "COUNT" else q
            if delta < 0:
                if -delta > dest.quantity:
                    raise ValidationError(f"{line.product}: điều chỉnh làm âm tồn.")
                value_delta = (
                    -dest.value
                    if -delta == dest.quantity
                    else money(delta * dest.value / dest.quantity)
                )
            elif delta == 0:
                value_delta = Decimal(0)
            else:
                if doc.kind == "IN" and line.unit_price is None:
                    raise ValidationError(
                        f"{line.product}: phiếu nhập phải có đơn giá (được nhập 0 cho hàng miễn phí)."
                    )
                price = line.unit_price
                if price is None:
                    if not dest.quantity:
                        raise ValidationError(
                            f"{line.product}: cần đơn giá cho hàng chưa có tồn."
                        )
                    price = dest.value / dest.quantity
                value_delta = money(delta * price)
            record(doc, line, doc.destination_id, delta, value_delta)
    if transfer and doc.status == "DRAFT":
        doc.status = "TRANSIT"
        doc.dispatched_by = user
        doc.dispatched_at = timezone.now()
        doc.save(update_fields=["status", "dispatched_by", "dispatched_at"])
    else:
        doc.status = "POSTED"
        doc.posted_by = user
        doc.posted_at = timezone.now()
        doc.save(update_fields=["status", "posted_by", "posted_at"])
    return doc

from decimal import ROUND_HALF_UP, Decimal, localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from .models import Balance, Document, DocumentEvent, LoanHolding, Movement, Warehouse


@transaction.atomic
def capture_lines(doc, rows):
    """Keep item identity and the stocktake cutoff at the time the draft is saved."""
    if doc.kind == "COUNT":
        Warehouse.objects.select_for_update().get(pk=doc.destination_id)
    for line in rows:
        line.sku_snapshot = line.product.sku
        line.name_snapshot = line.product.name
        line.unit_snapshot = line.product.unit
        if doc.kind == "COUNT":
            balance = Balance.objects.filter(
                warehouse=doc.destination, product=line.product
            ).first()
            line.stocktake_quantity = balance.quantity if balance else Decimal(0)
            line.stocktake_version = (
                Movement.objects.filter(
                    warehouse=doc.destination, product=line.product
                ).aggregate(n=Max("id"))["n"]
                or 0
            )
    return rows


def audit_document(doc, actor, action, extra=None):
    from .hierarchy import approval_level

    fields = [
        "kind",
        "source_id",
        "destination_id",
        "loan_id",
        "status",
        "revision",
        "business_date",
        "reference_number",
        "reference_date",
        "counterparty",
        "counterparty_address",
        "department",
        "handed_over_by",
        "received_by",
        "due_date",
        "note",
        "closure_reason",
    ]
    snapshot = {
        k: str(getattr(doc, k)) if getattr(doc, k) is not None else None for k in fields
    }
    snapshot.update(
        creator_level=doc.creator_level,
        actor_level=approval_level(actor),
        admin_self_approved=bool(
            action in ["POST", "DISPATCH"]
            and actor.is_superuser
            and doc.created_by_id == actor.pk
        ),
    )
    snapshot["lines"] = [
        {
            k: str(getattr(line, k)) if getattr(line, k) is not None else None
            for k in [
                "product_id",
                "quantity",
                "unit_price",
                "expected_quantity",
                "rejected_quantity",
                "note",
                "sku_snapshot",
                "name_snapshot",
                "unit_snapshot",
                "stocktake_quantity",
                "stocktake_version",
            ]
        }
        for line in doc.lines.all().order_by("product_id")
    ]
    if extra:
        snapshot.update(extra)
    DocumentEvent.objects.create(
        document=doc, actor=actor, action=action, snapshot=snapshot
    )


def validate_line_details(doc, line):
    if doc.kind != "IN":
        if line.expected_quantity is not None or line.rejected_quantity:
            raise ValidationError(
                "Số theo chứng từ và số không nhận chỉ dùng cho nhập kho."
            )
        return
    expected, rejected = line.expected_quantity, line.rejected_quantity
    if rejected < 0 or (
        expected is not None and (expected < 0 or line.quantity + rejected > expected)
    ):
        raise ValidationError(
            f"{line.product}: số thực nhận cộng số không nhận không được vượt số theo chứng từ."
        )
    if (
        rejected or (expected is not None and line.quantity + rejected < expected)
    ) and not line.note.strip():
        raise ValidationError(f"{line.product}: ghi rõ lý do thiếu / không nhận hàng.")


def warehouses_for(user):
    if not user.is_authenticated or not user.is_active:
        return Warehouse.objects.none()
    return (
        Warehouse.objects.all()
        if user.is_superuser
        else Warehouse.objects.filter(
            Q(members=user) | Q(managers=user) | Q(issue_approvers=user)
        ).distinct()
    )


def documents_for(user):
    from .access import KIND_MODULES, function_codes

    codes = function_codes(user)
    if user.is_superuser:
        return Document.objects.all() if user.is_active else Document.objects.none()
    kinds = [kind for kind, module in KIND_MODULES.items() if module + "_view" in codes]
    ids = warehouses_for(user).values_list("id", flat=True)
    return (
        Document.objects.filter(
            Q(source_id__in=ids)
            | Q(destination_id__in=ids)
            | (
                Q(kind__in=["COUNT", "ADJUST"])
                if can_approve_adjustments(user)
                else Q(pk__in=[])
            )
        )
        .filter(kind__in=kinds)
        .distinct()
    )


def can_approve_adjustments(user):
    from .access import has_function

    return has_function(user, "adjustments_approve")


def validate_document(doc):
    if doc.status == "DRAFT" and doc.business_date != timezone.localdate():
        raise ValidationError(
            "Phiếu chỉ được lập và duyệt cho ngày hôm nay. Người lập cần mở sửa phiếu để cập nhật lại ngày và kiểm tra hàng."
        )
    if doc.business_date > timezone.localdate():
        raise ValidationError(
            "Ngày nghiệp vụ không được ở tương lai. Phiếu chỉ ghi hàng thực tế đã phát sinh."
        )
    if doc.reference_date and (
        not doc.reference_number.strip() or doc.reference_date > timezone.localdate()
    ):
        raise ValidationError(
            "Ngày chứng từ nguồn cần có số chứng từ và không được ở tương lai."
        )
    if doc.due_date and (doc.kind != "LOAN" or doc.due_date < doc.business_date):
        raise ValidationError(
            "Hạn trả chỉ dùng cho lệnh mượn và không trước ngày mượn."
        )
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
        if doc.business_date < loan.business_date:
            raise ValidationError("Ngày trả không được trước ngày mượn gốc.")
    elif doc.loan_id:
        raise ValidationError("Chỉ phiếu trả mới được chọn phiếu mượn gốc.")


def approval_documents_for(user):
    from .access import KIND_MODULES, function_codes, is_admin

    qs = documents_for(user)
    if is_admin(user):
        return qs.filter(status__in=["DRAFT", "TRANSIT"])
    from django.db.models import Case, IntegerField, Value, When
    from django.db.models.functions import Coalesce

    from .hierarchy import approval_level

    level = approval_level(user)
    qs = (
        qs.exclude(created_by=user)
        .annotate(
            _maker_level=Case(
                When(created_by__is_superuser=True, then=Value(40)),
                default=Coalesce(
                    "created_by__function_access__approval_level", Value(10)
                ),
                output_field=IntegerField(),
            )
        )
        .filter(creator_level__lt=level, _maker_level__lt=level)
    )
    codes = function_codes(user)
    source_ids = user.issue_warehouses.values_list("id", flat=True)
    dest_ids = user.managed_warehouses.values_list("id", flat=True)
    allowed = Q(pk__in=[])
    for kind, module in KIND_MODULES.items():
        if kind in ["COUNT", "ADJUST"]:
            if "adjustments_approve" in codes:
                allowed |= Q(kind=kind, status="DRAFT")
            continue
        if module + "_approve" in codes:
            allowed |= (
                Q(kind=kind, status="DRAFT", destination_id__in=dest_ids)
                if kind == "IN"
                else Q(kind=kind, status="DRAFT", source_id__in=source_ids)
            )
        if module + "_receive" in codes:
            allowed |= Q(kind=kind, status="TRANSIT", destination_id__in=dest_ids)
    return qs.filter(allowed).distinct()


def approval_block_reason(doc, user):
    from .access import approval_key, can_view_kind, has_function, is_admin
    from .hierarchy import approval_level, maker_level

    if not user.is_authenticated or not user.is_active:
        return "Tài khoản không hoạt động."
    if doc.status not in ["DRAFT", "TRANSIT"]:
        return "Phiếu không ở trạng thái chờ duyệt hoặc chờ nhận."
    if is_admin(user):
        return ""
    if doc.created_by_id == user.pk:
        return "Người lập phiếu không được tự duyệt. Chỉ Admin tổng có ngoại lệ tự duyệt kèm xác nhận."
    if approval_level(user) <= maker_level(doc):
        return "Người duyệt phải có cấp cao hơn người lập; không duyệt ngang cấp hoặc ngược cấp."
    if not can_view_kind(user, doc.kind) or not has_function(user, approval_key(doc)):
        return "Bạn chưa được cấp quyền duyệt chức năng này."
    if doc.kind in ["COUNT", "ADJUST"]:
        return ""
    receiving = doc.status == "TRANSIT" or not doc.source_id
    warehouse = doc.destination if receiving else doc.source
    assigned = bool(
        warehouse
        and (warehouse.managers if receiving else warehouse.issue_approvers)
        .filter(pk=user.pk)
        .exists()
    )
    return "" if assigned else "Bạn chưa được phân công duyệt tại kho này."


def can_approve(doc, user):
    return not approval_block_reason(doc, user)


def require_approver(doc, user, receiving):
    reason = approval_block_reason(doc, user)
    if reason:
        raise PermissionDenied(reason)


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
def post_document(
    pk,
    user,
    *,
    confirm_self_approval=False,
    expected_status=None,
    expected_revision=None,
):
    doc = Document.objects.select_for_update().get(pk=pk)
    from .hierarchy import lock_approval_accounts

    user = lock_approval_accounts(doc, user)
    if doc.status == "POSTED":
        raise ValidationError("Phiếu đã ghi sổ trước đó.")
    if doc.status not in ["DRAFT", "TRANSIT"]:
        raise ValidationError("Phiếu đã hủy hoặc đang yêu cầu sửa không thể ghi sổ.")
    transfer = doc.kind in ["TRANSFER", "LOAN", "RETURN"]
    receiving = doc.status == "TRANSIT" or not doc.source_id
    require_approver(doc, user, receiving)
    if expected_status is not None and (
        expected_status not in ["DRAFT", "TRANSIT"] or doc.status != expected_status
    ):
        raise ValidationError(
            "Phiếu đã được xử lý hoặc chuyển sang bước khác. Hãy tải lại phiếu và kiểm tra trước khi tiếp tục."
        )
    if expected_revision is not None and (
        type(expected_revision) is not int
        or expected_revision < 1
        or doc.revision != expected_revision
    ):
        raise ValidationError(
            "Nội dung phiếu đã thay đổi. Hãy tải lại phiếu và kiểm tra bản mới trước khi duyệt."
        )
    if user.is_superuser and doc.created_by_id == user.pk and not confirm_self_approval:
        raise ValidationError(
            "Bạn đang tự duyệt phiếu do chính mình lập. Hãy đánh dấu xác nhận tự duyệt trước khi tiếp tục."
        )
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
    if doc.kind in ["COUNT", "ADJUST"]:
        from .models import StocktakeSession

        session = StocktakeSession.objects.filter(document=doc).first()
        if (
            session
            and (
                Movement.objects.filter(warehouse=doc.destination).aggregate(
                    v=Max("id")
                )["v"]
                or 0
            )
            > session.cutoff_id
        ):
            raise ValidationError(
                "Kho đã biến động sau khi mở phiên kiểm kê QR. Biên bản không còn hợp lệ để điều chỉnh; cần kiểm đếm lại."
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
        validate_line_details(doc, line)
        if doc.kind == "COUNT" or (
            doc.kind == "ADJUST" and getattr(doc, "stocktake_session", None)
        ):
            if line.stocktake_version is None:
                raise ValidationError(
                    "Phiếu kiểm kê cần người lập mở sửa, kiểm đếm lại và lưu mốc tồn trước khi duyệt."
                )
            current_version = (
                Movement.objects.filter(
                    warehouse=doc.destination, product=line.product
                ).aggregate(n=Max("id"))["n"]
                or 0
            )
            if current_version != line.stocktake_version:
                raise ValidationError(
                    f"{line.product}: tồn đã biến động sau khi lập phiếu kiểm kê. Người lập cần kiểm đếm lại và lưu sửa phiếu trước khi duyệt."
                )
        q = line.quantity
        zero_receipt = (
            doc.kind == "IN"
            and q == 0
            and (line.expected_quantity or line.rejected_quantity)
        )
        if (doc.kind not in ["COUNT", "ADJUST"] and q <= 0 and not zero_receipt) or (
            doc.kind == "COUNT" and q < 0
        ):
            raise ValidationError(
                "Số lượng không hợp lệ; kiểm kê được nhập 0, điều chỉnh được nhập số âm."
            )
        if line.unit_price is not None and line.unit_price < 0:
            raise ValidationError("Đơn giá không được âm.")
        if zero_receipt:
            # Record the discrepancy on the document, without creating usable stock or a zero movement.
            continue
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
        audit_document(doc, user, "DISPATCH")
    else:
        doc.status = "POSTED"
        doc.posted_by = user
        doc.posted_at = timezone.now()
        doc.save(update_fields=["status", "posted_by", "posted_at"])
        audit_document(doc, user, "POST")
    return doc


@transaction.atomic
def close_document(pk, user, action, reason):
    doc = Document.objects.select_for_update().get(pk=pk)
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ValidationError("Ghi lý do từ 1 đến 1000 ký tự.")
    if action == "REJECT":
        from .hierarchy import lock_approval_accounts

        user = lock_approval_accounts(doc, user)
        if doc.status != "DRAFT" or not can_approve(doc, user):
            raise PermissionDenied(
                "Chỉ người được duyệt mới được yêu cầu sửa phiếu đang chờ."
            )
        doc.status = "REJECTED"
    elif action == "CANCEL":
        from .access import can_create_kind

        if (
            not can_create_kind(user, doc.kind)
            or not documents_for(user).filter(pk=doc.pk).exists()
        ):
            raise PermissionDenied("Bạn không còn quyền xử lý phiếu này.")
        if doc.status not in ["DRAFT", "REJECTED"] or not (
            doc.created_by_id == user.pk or user.is_superuser
        ):
            raise PermissionDenied(
                "Chỉ người lập hoặc quản trị viên được hủy phiếu chưa ghi sổ / chưa chuyển đi."
            )
        doc.status = "CANCELLED"
    else:
        raise ValidationError("Thao tác không hợp lệ.")
    doc.closure_reason = reason
    doc.revision += 1
    doc.save(update_fields=["status", "closure_reason", "revision"])
    audit_document(doc, user, action)
    return doc

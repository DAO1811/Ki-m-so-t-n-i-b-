import hashlib
import json
import re
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .access import has_function
from .models import (
    Balance,
    Document,
    Line,
    Movement,
    Product,
    StocktakeEvent,
    StocktakeItem,
    StocktakeSession,
    Warehouse,
)
from .services import audit_document, warehouses_for


def product_from_scan(raw):
    text = str(raw).strip()
    product = Product.objects.filter(qr_code=text).first()
    if product:
        return product
    match = re.search(r"(?:/q/items/|DHD:ITEM:)([a-fA-F0-9-]{36})(?:/|$)", text)
    if match:
        try:
            return Product.objects.get(qr_token=UUID(match[1]))
        except (ValueError, Product.DoesNotExist):
            pass
    else:
        product = Product.objects.filter(sku=text).first()
        if product:
            return product
    raise ValidationError(
        "Không tìm thấy mã QR / mã hàng trong danh mục. Không mở liên kết bên ngoài từ mã quét."
    )


def require_open(session, user):
    if session.counter_id != user.pk and not user.is_superuser:
        raise PermissionDenied(
            "Chỉ người nhận kiểm hoặc Admin tổng được ghi số đếm và gửi duyệt."
        )
    if not warehouses_for(user).filter(
        pk=session.warehouse_id
    ).exists() or not has_function(user, "stocktakes_create"):
        raise PermissionDenied("Bạn không còn quyền lập phiếu tại kho này.")
    if session.status != "OPEN":
        raise ValidationError("Phiên đã khóa; không thể ghi thêm.")
    if session.business_date != timezone.localdate():
        raise ValidationError(
            "Phiên đã sang ngày khác. Hãy hủy và mở phiên mới để kiểm đếm lại hôm nay."
        )


def active_sessions():
    return StocktakeSession.objects.filter(
        Q(status__in=["READY", "OPEN"])
        | Q(status="SUBMITTED", document__status="DRAFT")
    )


@transaction.atomic
def freeze_session(warehouse, user):
    if (
        not has_function(user, "stocktakes_create")
        or not warehouses_for(user).filter(pk=warehouse.pk).exists()
    ):
        raise PermissionDenied
    Warehouse.objects.select_for_update().get(pk=warehouse.pk)
    if active_sessions().filter(warehouse=warehouse).exists():
        raise ValidationError(
            "Kho đã có biên bản đang xử lý. Hoàn tất hoặc hủy phiên cũ có lý do trước khi chốt tồn mới."
        )
    versions = dict(
        Movement.objects.filter(warehouse=warehouse)
        .values("product_id")
        .annotate(v=Max("id"))
        .values_list("product_id", "v")
    )
    session = StocktakeSession.objects.create(
        warehouse=warehouse,
        created_by=user,
        cutoff_id=max(versions.values(), default=0),
        status="READY",
        locks_inventory=True,
    )
    StocktakeItem.objects.bulk_create(
        [
            StocktakeItem(
                session=session,
                product=b.product,
                sku_snapshot=b.product.sku,
                name_snapshot=b.product.name,
                unit_snapshot=b.product.unit,
                book_quantity=b.quantity,
                book_value=b.value,
                movement_version=versions.get(b.product_id, 0),
            )
            for b in Balance.objects.filter(
                warehouse=warehouse, quantity__gt=0
            ).select_related("product")
        ]
    )
    StocktakeEvent.objects.create(session=session, actor=user, action="FREEZE")
    return session


@transaction.atomic
def begin_session(pk, user, method):
    session = StocktakeSession.objects.select_for_update().get(pk=pk)
    if (
        not has_function(user, "stocktakes_create")
        or not warehouses_for(user).filter(pk=session.warehouse_id).exists()
    ):
        raise PermissionDenied
    if method not in {"QR", "PAPER"}:
        raise ValidationError("Chọn kiểm kê bằng giấy hoặc quét QR.")
    if session.status == "OPEN":
        if session.counter_id != user.pk and not user.is_superuser:
            raise PermissionDenied(
                "Phiên đã có người nhận kiểm. Admin tổng có thể hỗ trợ xử lý."
            )
        if session.method == method:
            return session
        raise ValidationError(
            "Phiên đã bắt đầu; không đổi cách kiểm để tránh đếm trùng."
        )
    if session.status != "READY" or session.business_date != timezone.localdate():
        raise ValidationError(
            "Chỉ bắt đầu từ mốc tồn đã chốt hôm nay. Phiên cũ cần hủy và chốt lại."
        )
    Warehouse.objects.select_for_update().get(pk=session.warehouse_id)
    latest = (
        Movement.objects.filter(warehouse_id=session.warehouse_id).aggregate(
            v=Max("id")
        )["v"]
        or 0
    )
    if latest > session.cutoff_id:
        raise ValidationError(
            "Mốc tồn đã biến động; hủy và chốt tồn mới trước khi kiểm."
        )
    session.status, session.method, session.started_at = "OPEN", method, timezone.now()
    from .hierarchy import approval_level

    session.counted_by = user
    session.creator_level = approval_level(user)
    session.save(
        update_fields=["status", "method", "started_at", "counted_by", "creator_level"]
    )
    StocktakeEvent.objects.create(session=session, actor=user, action="BEGIN")
    return session


@transaction.atomic
def start_session(warehouse, user):
    """Internal convenience; the web workflow freezes then explicitly starts."""
    session = freeze_session(warehouse, user)
    return begin_session(session.pk, user, "QR")


@transaction.atomic
def save_count(
    pk, user, product, mode, quantity, unit_price, note, request_id, revision
):
    session = StocktakeSession.objects.select_for_update().get(pk=pk)
    require_open(session, user)
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                product.pk,
                mode,
                str(quantity) if mode == "SET" else None,
                str(unit_price),
                note,
            ],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    replay = session.events.filter(request_id=request_id).first()
    if replay:
        if (
            replay.item
            and replay.item.product_id == product.pk
            and replay.action == mode
            and replay.payload_hash == fingerprint
        ):
            return replay.item, True
        raise ValidationError(
            "Mã lượt quét đã được dùng cho nội dung khác. Hãy quét lại."
        )
    Warehouse.objects.select_for_update().get(pk=session.warehouse_id)
    item = session.items.filter(product=product).first()
    if item is None:
        current = (
            Movement.objects.filter(
                warehouse=session.warehouse, product=product
            ).aggregate(v=Max("id"))["v"]
            or 0
        )
        if current > session.cutoff_id:
            raise ValidationError(
                "Hàng đã biến động sau khi mở phiên. Hãy mở phiên kiểm kê mới."
            )
        item = StocktakeItem.objects.create(
            session=session,
            product=product,
            movement_version=current,
            sku_snapshot=product.sku,
            name_snapshot=product.name,
            unit_snapshot=product.unit,
        )
    if item.revision != revision:
        raise ValidationError(
            "Số đếm đã thay đổi ở phiên khác. Chọn lại mã hàng để lấy số mới nhất."
        )
    before = item.counted_quantity
    if mode == "ADD":
        if session.method != "QR":
            raise ValidationError(
                "Phiên kiểm bằng giấy: ghi tổng số thực đếm, không quét cộng thêm."
            )
        quantity = (before or Decimal(0)) + 1
    elif mode != "SET":
        raise ValidationError("Chế độ đếm không hợp lệ.")
    if quantity is None or quantity < 0 or quantity >= Decimal("1e13"):
        raise ValidationError("Số đếm phải không âm và trong giới hạn lưu trữ.")
    item.counted_quantity = quantity
    item.unit_price = unit_price
    item.note = note
    if item.value_difference is not None and abs(item.value_difference) >= Decimal(
        "1e20"
    ):
        raise ValidationError(
            "Giá trị chênh lệch vượt giới hạn lưu trữ. Kiểm tra lại số đếm và đơn giá."
        )
    item.revision += 1
    item.save(update_fields=["counted_quantity", "unit_price", "note", "revision"])
    StocktakeEvent.objects.create(
        session=session,
        item=item,
        actor=user,
        request_id=request_id,
        payload_hash=fingerprint,
        action=mode,
        before=before,
        after=quantity,
    )
    return item, False


@transaction.atomic
def submit_session(pk, user, note):
    session = StocktakeSession.objects.select_for_update().get(pk=pk)
    if session.status == "COMPLETED" and (
        session.counter_id == user.pk or user.is_superuser
    ):
        return None
    if session.status == "SUBMITTED" and (
        session.counter_id == user.pk or user.is_superuser
    ):
        return session.document
    require_open(session, user)
    Warehouse.objects.select_for_update().get(pk=session.warehouse_id)
    if not note.strip():
        raise ValidationError(
            "Ghi kết luận kiểm kê / lý do chênh lệch trước khi gửi duyệt."
        )
    items = list(session.items.select_related("product"))
    if not items or any(item.counted_quantity is None for item in items):
        raise ValidationError(
            "Còn mã chưa đếm. Hàng không tìm thấy phải xác nhận số thực đếm 0; không tự coi chưa quét là 0."
        )
    versions = dict(
        Movement.objects.filter(warehouse=session.warehouse)
        .values("product_id")
        .annotate(v=Max("id"))
        .values_list("product_id", "v")
    )
    # Newly received codes must also be counted, even if absent from the initial list.
    if any(v > session.cutoff_id for v in versions.values()):
        raise ValidationError(
            "Kho có biến động sau khi mở phiên. Hãy mở phiên mới và kiểm đếm lại; không làm mới mốc tồn ngầm."
        )
    for item in items:
        if versions.get(item.product_id, 0) != item.movement_version:
            raise ValidationError(f"{item.product}: mốc tồn đã thay đổi.")
        if (
            item.counted_quantity > 0
            and item.book_quantity == 0
            and item.unit_price is None
        ):
            raise ValidationError(
                f"{item.product}: hàng ngoài sổ cần đơn giá để định giá phần tăng (có thể bằng 0)."
            )
    changes = [i for i in items if i.difference != 0]
    if not changes:
        session.status, session.note = "COMPLETED", note.strip()
        session.save(update_fields=["status", "note"])
        StocktakeEvent.objects.create(session=session, actor=user, action="SUBMIT")
        return None
    doc = Document.objects.create(
        creator_level=session.creator_level,
        kind="ADJUST",
        destination=session.warehouse,
        created_by_id=session.counter_id,
        note=f"Căn cứ biên bản KK-{session.pk:06d}: " + note.strip(),
    )
    Line.objects.bulk_create(
        [
            Line(
                document=doc,
                product=i.product,
                quantity=i.difference,
                unit_price=i.unit_price,
                note=i.note,
                stocktake_quantity=i.book_quantity,
                stocktake_version=i.movement_version,
                sku_snapshot=i.sku_snapshot,
                name_snapshot=i.name_snapshot,
                unit_snapshot=i.unit_snapshot,
            )
            for i in changes
        ]
    )
    audit_document(doc, user, "CREATE")
    session.document = doc
    session.note = note.strip()
    session.status = "SUBMITTED"
    session.save(update_fields=["document", "note", "status"])
    StocktakeEvent.objects.create(session=session, actor=user, action="SUBMIT")
    return doc


@transaction.atomic
def cancel_session(pk, user, reason):
    session = StocktakeSession.objects.select_for_update().get(pk=pk)
    if not user.is_active or (
        user.pk not in {session.created_by_id, session.counter_id}
        and not user.is_superuser
    ):
        raise PermissionDenied
    if not has_function(user, "stocktakes_create"):
        raise PermissionDenied
    if session.status not in ["READY", "OPEN"] or not reason.strip():
        raise ValidationError("Chỉ hủy phiên đang mở và phải ghi lý do.")
    session.status = "CANCELLED"
    session.note = reason.strip()
    session.save(update_fields=["status", "note"])
    StocktakeEvent.objects.create(session=session, actor=user, action="CANCEL")

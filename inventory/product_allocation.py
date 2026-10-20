"""Validate optional warehouse allocations and create ordinary receipt drafts."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.core.exceptions import ValidationError
from django.utils import timezone

from .access import has_function, require_function
from .models import Document, Line, Warehouse
from .services import audit_document, capture_lines, validate_document, warehouses_for

ALLOCATION_COLUMNS = (
    (
        "warehouse_code",
        "Mã kho nhập",
        ("ma kho", "ma kho nhap", "kho nhap", "warehouse_code"),
    ),
    (
        "receipt_quantity",
        "Số lượng nhập",
        ("so luong nhap", "receipt_quantity", "quantity"),
    ),
    ("receipt_price", "Đơn giá nhập", ("don gia nhap", "receipt_price", "unit_price")),
)
ALLOCATION_KEYS = {column[0] for column in ALLOCATION_COLUMNS}


def has_allocation(row):
    return any(row["data"].get(key, "").strip() for key in ALLOCATION_KEYS)


def validate_allocations(rows, user, *, lock=False):
    active = [row for row in rows if has_allocation(row)]
    if not active:
        return
    labels = {key: label for key, label, _ in ALLOCATION_COLUMNS}

    def error(row, key, message):
        row["errors"].append({"field": key, "label": labels[key], "message": message})

    allowed = user is not None and has_function(user, "receipts_create")
    codes = {row["data"].get("warehouse_code", "") for row in active}
    warehouses = {
        warehouse.code: warehouse
        for warehouse in (
            warehouses_for(user).filter(code__in=codes) if allowed else []
        )
    }
    if lock and warehouses:
        # DISTINCT permission query cannot be used with PostgreSQL FOR UPDATE.
        list(
            Warehouse.objects.select_for_update()
            .filter(pk__in=[warehouse.pk for warehouse in warehouses.values()])
            .order_by("pk")
        )
        warehouses = {
            warehouse.code: warehouse
            for warehouse in warehouses_for(user).filter(code__in=codes)
        }
    for row in active:
        data = row["data"]
        if not allowed:
            error(
                row,
                "warehouse_code",
                "Cần được cấp quyền Tạo phiếu nhập kho để nhập kèm phân bổ kho.",
            )
        warehouse = warehouses.get(data.get("warehouse_code", ""))
        if not data.get("warehouse_code"):
            error(
                row, "warehouse_code", "Điền mã kho khi có số lượng hoặc đơn giá nhập."
            )
        elif allowed and warehouse is None:
            error(
                row,
                "warehouse_code",
                "Mã kho không tồn tại hoặc bạn không được cấp quyền tại kho này.",
            )
        if warehouse:
            row["warehouse_id"] = warehouse.pk
            row["warehouse_name"] = str(warehouse)
        values = {}
        for key, places, upper in [
            ("receipt_quantity", 3, Decimal("1e13")),
            ("receipt_price", 4, Decimal("1e14")),
        ]:
            raw = data.get(key, "")
            try:
                if not raw or len(raw) > 64:
                    raise ValueError
                value = Decimal(raw)
                if (
                    not value.is_finite()
                    or value < 0
                    or value >= upper
                    or (key == "receipt_quantity" and value == 0)
                    or value != value.quantize(Decimal(1).scaleb(-places))
                ):
                    raise ValueError
                data[key] = str(value)
                values[key] = value
            except (ValueError, InvalidOperation):
                error(
                    row,
                    key,
                    "Nhập số lượng dương, tối đa 3 số lẻ."
                    if key == "receipt_quantity"
                    else "Điền đơn giá không âm, tối đa 4 số lẻ; miễn phí ghi 0.",
                )
        if len(values) == 2:
            amount = values["receipt_quantity"] * values["receipt_price"]
            if amount >= Decimal("1e20"):
                error(row, "receipt_price", "Thành tiền vượt giới hạn lưu trữ.")
            else:
                row["receipt_amount"] = str(
                    amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                )


def allocation_summary(rows):
    groups = {}
    for row in rows:
        if not has_allocation(row) or row.get("errors") or not row.get("warehouse_id"):
            continue
        warehouse_id = row["warehouse_id"]
        group = groups.setdefault(
            warehouse_id,
            {
                "warehouse_id": warehouse_id,
                "warehouse_name": row["warehouse_name"],
                "rows": 0,
                "amount": Decimal(0),
            },
        )
        group["rows"] += 1
        group["amount"] += Decimal(row["receipt_amount"])
    return [
        dict(group, amount=str(group["amount"]), documents=(group["rows"] + 49) // 50)
        for group in groups.values()
    ]


def create_allocated_receipts(
    user, rows, products, *, business_date, filename="", batch_key=None
):
    active = [row for row in rows if has_allocation(row)]
    if not active:
        return []
    require_function(user, "receipts_create")
    if str(business_date) != str(timezone.localdate()):
        raise ValidationError(
            "Bản xem trước phân bổ kho đã sang ngày khác. Hãy tải lại file để lập phiếu ngày hôm nay."
        )
    products_by_sku = {product.sku: product for product in products}
    groups = defaultdict(list)
    for row in active:
        groups[row["warehouse_id"]].append(row)
    batch_key = str(batch_key or uuid4())
    documents = []
    for warehouse_id, group in groups.items():
        for offset in range(0, len(group), 50):
            doc = Document(
                kind="IN",
                destination_id=warehouse_id,
                created_by=user,
                business_date=date.fromisoformat(str(business_date)),
                import_key=uuid5(
                    NAMESPACE_URL,
                    f"product-allocation:{user.pk}:{batch_key}:{warehouse_id}:{offset}",
                ),
                note=f"Nhập hàng hóa từ Excel: {filename}. Phân bổ theo kho, phần {offset // 50 + 1}.",
            )
            validate_document(doc)
            doc.save()
            Line.objects.bulk_create(
                capture_lines(
                    doc,
                    [
                        Line(
                            document=doc,
                            product=products_by_sku[row["data"]["sku"]],
                            quantity=Decimal(row["data"]["receipt_quantity"]),
                            expected_quantity=Decimal(row["data"]["receipt_quantity"]),
                            unit_price=Decimal(row["data"]["receipt_price"]),
                            note=f"Dòng Excel {row['row_number']}",
                        )
                        for row in group[offset : offset + 50]
                    ],
                )
            )
            audit_document(doc, user, "CREATE")
            documents.append(doc)
    return documents

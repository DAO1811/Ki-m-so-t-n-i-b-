"""One QR identity per product; older UUID labels remain valid."""

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q


def new_qr_code():
    return "DHD-" + uuid4().hex.upper()


def validate_manual_qr(value):
    if not value or len(value) > 120:
        raise ValidationError("Nhập mã QR từ 1 đến 120 ký tự khi bỏ chọn tự động.")
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ValidationError(
            "Mã QR không được chứa khoảng trắng hoặc ký tự điều khiển."
        )
    if "DHD:ITEM:" in value.upper() or "/q/items/" in value.lower():
        raise ValidationError(
            "Nội dung này dành cho tem QR cũ của phần mềm. Hãy dùng mã riêng, ví dụ LEMON-TS-0001."
        )


def lock_product_codes():
    # Shared by individual and Excel creation. Prevents concurrent cross-use of
    # a product's SKU as another product's QR identity.
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [1811000030])


def validate_identity(sku, code, *, exclude_pk=None):
    from .models import Product

    others = Product.objects.exclude(pk=exclude_pk)
    if not code:
        raise ValidationError(
            {"qr_code": "Mã QR là bắt buộc. Chọn tự động hoặc nhập mã riêng."}
        )
    if others.filter(Q(qr_code=code) | Q(sku=code)).exists():
        raise ValidationError(
            {"qr_code": "Mã QR đã được dùng cho hàng hóa khác; chọn mã duy nhất."}
        )
    if others.filter(qr_code=sku).exists():
        raise ValidationError(
            {"sku": "Mã hàng đang được dùng làm QR của hàng hóa khác."}
        )

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator
from django.utils import timezone
from uuid import uuid4
from decimal import Decimal, ROUND_HALF_UP, localcontext


class FunctionAccess(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="function_access",
    )
    permissions = models.JSONField(default=list, blank=True)
    revision = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="function_access_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()


class Warehouse(models.Model):
    code = models.CharField("Mã kho", max_length=30, unique=True)
    name = models.CharField("Tên kho", max_length=150)
    address = models.CharField("Địa chỉ", max_length=250, blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="warehouses",
        verbose_name="Nhân viên được truy cập",
    )
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="managed_warehouses",
        verbose_name="Quản lý được duyệt nhập kho",
    )
    issue_approvers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="issue_warehouses",
        verbose_name="Người được admin chỉ định duyệt xuất",
    )

    class Meta:
        verbose_name = "Kho"
        verbose_name_plural = "Kho"

    def __str__(self):
        return f"{self.code} · {self.name}"


class CustomField(models.Model):
    key = models.SlugField("Mã trường", unique=True)
    label = models.CharField("Tên hiển thị", max_length=100)

    class Meta:
        verbose_name = "Trường bổ sung hàng hóa"
        verbose_name_plural = "Trường bổ sung hàng hóa"

    def __str__(self):
        return self.label


class Product(models.Model):
    qr_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    sku = models.CharField("Mã hàng", max_length=50, unique=True)
    name = models.CharField("Tên hàng", max_length=200)
    unit = models.CharField("Đơn vị tính", max_length=30, default="Cái")
    category = models.CharField("Nhóm hàng", max_length=100, blank=True)
    brand = models.CharField("Nhãn hiệu / nhà sản xuất", max_length=100, blank=True)
    model_number = models.CharField(
        "Model / mã nhà sản xuất", max_length=100, blank=True
    )
    specifications = models.TextField("Quy cách / thông số kỹ thuật", blank=True)
    storage_instructions = models.TextField("Điều kiện bảo quản", blank=True)
    minimum = models.DecimalField(
        "Mức tồn tối thiểu mỗi kho",
        max_digits=16,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)],
    )
    extra = models.JSONField("Thông tin bổ sung", default=dict, blank=True)

    class Meta:
        verbose_name = "Hàng hóa"
        verbose_name_plural = "Hàng hóa"

    def __str__(self):
        return f"{self.sku} · {self.name}"


class StoredFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    sha256 = models.CharField(max_length=64)
    context_key = models.CharField(max_length=100)
    provider = models.CharField(max_length=12, default="database")
    drive_id = models.CharField(max_length=150, blank=True)
    content_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField()
    data = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sha256", "context_key"], name="unique_file_in_context"
            )
        ]


class DriveConnection(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    encrypted_refresh_token = models.TextField()
    account_email = models.EmailField()
    folder_id = models.CharField(max_length=150, blank=True)
    folder_name = models.CharField(max_length=200, blank=True)
    connected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    connected_at = models.DateTimeField(auto_now=True)


class MediaQuota(models.Model):
    """Singleton row serializes file creation and development quota checks."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)


class ProductPhoto(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="photos"
    )
    file = models.ForeignKey(StoredFile, on_delete=models.PROTECT)
    caption = models.CharField(max_length=150, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "file"], name="unique_product_photo"
            )
        ]


class Balance(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    value = models.DecimalField(max_digits=22, decimal_places=2, default=0)

    @property
    def average_cost(self):
        return self.value / self.quantity if self.quantity else 0

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "product"], name="unique_balance"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0), name="nonnegative_stock"
            ),
            models.CheckConstraint(
                condition=Q(value__gte=0), name="nonnegative_stock_value"
            ),
        ]


class Document(models.Model):
    TYPES = [
        ("IN", "Nhập kho"),
        ("OUT", "Xuất kho"),
        ("TRANSFER", "Luân chuyển"),
        ("LOAN", "Cho kho mượn"),
        ("RETURN", "Trả hàng mượn"),
        ("COUNT", "Kiểm kê"),
        ("ADJUST", "Điều chỉnh tồn"),
    ]
    import_key = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    revision = models.PositiveIntegerField(default=1, editable=False)
    kind = models.CharField("Loại phiếu", max_length=10, choices=TYPES)
    source = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="outgoing",
        verbose_name="Kho xuất",
        null=True,
        blank=True,
    )
    destination = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="incoming",
        verbose_name="Kho nhập / kiểm kê",
        null=True,
        blank=True,
    )
    loan = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Phiếu mượn gốc",
    )
    note = models.TextField("Diễn giải / lý do", blank=True)
    business_date = models.DateField(
        "Ngày nghiệp vụ thực tế", default=timezone.localdate
    )
    reference_number = models.CharField(
        "Số hóa đơn / chứng từ nguồn", max_length=100, blank=True
    )
    reference_date = models.DateField("Ngày chứng từ nguồn", null=True, blank=True)
    counterparty = models.CharField(
        "Nhà cung cấp / đối tác", max_length=200, blank=True
    )
    counterparty_address = models.CharField(
        "Địa chỉ đối tác", max_length=250, blank=True
    )
    department = models.CharField(
        "Bộ phận / công trình sử dụng", max_length=150, blank=True
    )
    handed_over_by = models.CharField(
        "Người giao hàng / bàn giao", max_length=150, blank=True
    )
    received_by = models.CharField(
        "Người nhận hàng / kiểm đếm", max_length=150, blank=True
    )
    due_date = models.DateField("Hạn trả hàng mượn", null=True, blank=True)
    status = models.CharField(
        max_length=10,
        default="DRAFT",
        choices=[
            ("DRAFT", "Nháp"),
            ("TRANSIT", "Đang chuyển / chờ nhận"),
            ("POSTED", "Đã ghi sổ"),
            ("REJECTED", "Yêu cầu sửa"),
            ("CANCELLED", "Đã hủy"),
        ],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_documents",
    )
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dispatched_documents",
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="posted_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closure_reason = models.TextField("Lý do yêu cầu sửa / hủy", blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [
            ("post_document", "Được ghi sổ chứng từ"),
            (
                "approve_inventory_adjustment",
                "Tổng giám đốc: duyệt biên bản kiểm kê và điều chỉnh tồn",
            ),
        ]
        verbose_name = "Chứng từ"
        verbose_name_plural = "Chứng từ"
        ordering = ["-id"]

    @property
    def action_label(self):
        if self.status == "TRANSIT":
            return "Xác nhận nhận hàng"
        return {
            "IN": "Duyệt nhập kho",
            "OUT": "Duyệt xuất kho",
            "TRANSFER": "Duyệt chuyển đi",
            "LOAN": "Duyệt cho mượn",
            "RETURN": "Duyệt trả hàng",
            "COUNT": "Duyệt kiểm kê",
            "ADJUST": "Duyệt điều chỉnh",
        }.get(self.kind, "Duyệt phiếu")

    def __str__(self):
        return f"PK-{self.pk:06d} · {self.get_kind_display()}"


class Line(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    expected_quantity = models.DecimalField(
        "Số lượng theo chứng từ nguồn",
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
    )
    rejected_quantity = models.DecimalField(
        "Số lượng không nhận (hỏng / sai quy cách)",
        max_digits=16,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)],
    )
    note = models.CharField("Tình trạng / lý do chênh lệch", max_length=250, blank=True)
    stocktake_quantity = models.DecimalField(
        max_digits=16, decimal_places=3, null=True, blank=True, editable=False
    )
    stocktake_version = models.BigIntegerField(null=True, blank=True, editable=False)
    sku_snapshot = models.CharField(max_length=50, blank=True, editable=False)
    name_snapshot = models.CharField(max_length=200, blank=True, editable=False)
    unit_snapshot = models.CharField(max_length=30, blank=True, editable=False)

    @property
    def shortage(self):
        return (
            max(self.expected_quantity - self.quantity - self.rejected_quantity, 0)
            if self.expected_quantity is not None
            else None
        )

    @property
    def count_difference(self):
        if self.stocktake_quantity is not None and self.document.kind == "ADJUST":
            return self.quantity
        return (
            self.quantity - self.stocktake_quantity
            if self.stocktake_quantity is not None
            else None
        )

    book_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "product"], name="unique_document_product"
            ),
            models.CheckConstraint(
                condition=Q(rejected_quantity__gte=0),
                name="nonnegative_rejected_quantity",
            ),
            models.CheckConstraint(
                condition=Q(expected_quantity__isnull=True)
                | Q(
                    expected_quantity__gte=models.F("quantity")
                    + models.F("rejected_quantity")
                ),
                name="receipt_quantities_reconcile",
            ),
        ]


class Movement(models.Model):
    document = models.ForeignKey(Document, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    delta = models.DecimalField(max_digits=16, decimal_places=3)
    balance_after = models.DecimalField(max_digits=16, decimal_places=3)
    value_delta = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    value_after = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def business_date(self):
        # Each transfer leg has its own actual date under the today's-only policy.
        return timezone.localdate(self.created_at)

    class Meta:
        ordering = ["-id"]


class DocumentEvent(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="events"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(
        max_length=20,
        choices=[
            ("CREATE", "Lập phiếu"),
            ("EDIT", "Sửa phiếu / gửi duyệt lại"),
            ("DISPATCH", "Duyệt chuyển đi"),
            ("POST", "Duyệt ghi sổ"),
            ("REJECT", "Yêu cầu sửa"),
            ("CANCEL", "Hủy phiếu chưa ghi sổ"),
            ("FILE_ADD", "Bổ sung hồ sơ đợt nhập"),
            ("FILE_VOID", "Đánh dấu hồ sơ không sử dụng"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ["id"]


class ReceiptAttachment(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="attachments"
    )
    file = models.ForeignKey(StoredFile, on_delete=models.PROTECT)
    filename = models.CharField(max_length=150)
    invoice_number = models.CharField("Số hóa đơn / tên hồ sơ", max_length=100)
    invoice_date = models.DateField("Ngày hóa đơn", null=True, blank=True)
    category = models.CharField(
        "Loại hồ sơ",
        max_length=15,
        default="INVOICE",
        choices=[
            ("INVOICE", "Hóa đơn"),
            ("DELIVERY", "Giao nhận"),
            ("QUALITY", "Chất lượng / bảo hành"),
        ],
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    void_reason = models.CharField(max_length=250, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_receipt_attachments",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "file"],
                name="unique_receipt_attachment",
                condition=Q(voided_at__isnull=True),
            )
        ]


class StocktakeSession(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    business_date = models.DateField(default=timezone.localdate)
    cutoff_id = models.BigIntegerField(default=0)
    status = models.CharField(
        max_length=12,
        default="OPEN",
        choices=[
            ("OPEN", "Đang đếm"),
            ("SUBMITTED", "Đã lập phiếu điều chỉnh"),
            ("COMPLETED", "Hoàn tất, không chênh lệch"),
            ("CANCELLED", "Đã hủy phiên"),
        ],
    )
    note = models.TextField(blank=True)
    document = models.OneToOneField(
        Document,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stocktake_session",
    )

    class Meta:
        ordering = ["-id"]

    @property
    def workflow_status(self):
        if self.document_id:
            return {
                "DRAFT": "Chờ Tổng giám đốc duyệt điều chỉnh",
                "POSTED": "Hoàn tất, đã điều chỉnh tồn",
                "REJECTED": "Yêu cầu kiểm đếm lại bằng phiên mới",
                "CANCELLED": "Phiếu điều chỉnh đã hủy",
            }.get(self.document.status, self.get_status_display())
        return self.get_status_display()


class StocktakeItem(models.Model):
    session = models.ForeignKey(
        StocktakeSession, on_delete=models.PROTECT, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    sku_snapshot = models.CharField(max_length=50, blank=True)
    name_snapshot = models.CharField(max_length=200, blank=True)
    unit_snapshot = models.CharField(max_length=30, blank=True)
    book_quantity = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    book_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    movement_version = models.BigIntegerField(default=0)
    counted_quantity = models.DecimalField(
        max_digits=16, decimal_places=3, null=True, blank=True
    )
    unit_price = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    note = models.CharField(max_length=250, blank=True)
    revision = models.PositiveIntegerField(default=1)

    @property
    def difference(self):
        return (
            self.counted_quantity - self.book_quantity
            if self.counted_quantity is not None
            else None
        )

    @property
    def value_difference(self):
        if self.difference is None:
            return None
        if self.difference == 0:
            return Decimal(0)
        price = (
            self.book_value / self.book_quantity
            if self.book_quantity
            else self.unit_price
        )
        if self.difference > 0 and self.unit_price is not None:
            price = self.unit_price
        with localcontext() as context:
            context.prec = 50
            return (
                (self.difference * price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if price is not None
                else None
            )

    class Meta:
        ordering = ["product__sku"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "product"], name="unique_stocktake_item"
            ),
            models.CheckConstraint(
                condition=Q(counted_quantity__gte=0) | Q(counted_quantity__isnull=True),
                name="nonnegative_counted_quantity",
            ),
        ]


class StocktakeEvent(models.Model):
    session = models.ForeignKey(
        StocktakeSession, on_delete=models.PROTECT, related_name="events"
    )
    item = models.ForeignKey(
        StocktakeItem, on_delete=models.PROTECT, null=True, blank=True
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_id = models.UUIDField(null=True, blank=True)
    payload_hash = models.CharField(max_length=64, blank=True)
    action = models.CharField(
        max_length=12,
        choices=[
            ("START", "Mở phiên"),
            ("SET", "Ghi số đếm"),
            ("ADD", "Quét cộng 1"),
            ("SUBMIT", "Gửi duyệt"),
            ("CANCEL", "Hủy phiên"),
        ],
    )
    before = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)
    after = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "request_id"], name="unique_stocktake_request"
            )
        ]


class LoanHolding(models.Model):
    """Restricted loan stock: not part of the borrower's usable inventory."""

    loan_line = models.OneToOneField(
        Line, on_delete=models.PROTECT, related_name="holding"
    )
    quantity = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    value = models.DecimalField(max_digits=22, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=0), name="nonnegative_loan_holding"
            ),
            models.CheckConstraint(
                condition=Q(value__gte=0), name="nonnegative_loan_value"
            ),
        ]

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator


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
    sku = models.CharField("Mã hàng", max_length=50, unique=True)
    name = models.CharField("Tên hàng", max_length=200)
    unit = models.CharField("Đơn vị tính", max_length=30, default="Cái")
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
    status = models.CharField(
        max_length=10,
        default="DRAFT",
        choices=[
            ("DRAFT", "Nháp"),
            ("TRANSIT", "Đang chuyển / chờ nhận"),
            ("POSTED", "Đã ghi sổ"),
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
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [("post_document", "Được ghi sổ chứng từ")]
        verbose_name = "Chứng từ"
        verbose_name_plural = "Chứng từ"
        ordering = ["-id"]

    def __str__(self):
        return f"PK-{self.pk:06d} · {self.get_kind_display()}"


class Line(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
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
            )
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

    class Meta:
        ordering = ["-id"]


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

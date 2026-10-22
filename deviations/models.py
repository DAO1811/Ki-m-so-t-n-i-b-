from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .constants import SEVERITIES, TERMINAL, ActionKind, ActionStatus, CaseStatus


class Category(models.Model):
    name = models.CharField("Tên nhóm sai lệch", max_length=100, unique=True)
    active = models.BooleanField("Đang sử dụng", default=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class WorkflowPolicy(models.Model):
    enabled = models.BooleanField("Mở quy trình xử lý", default=False)
    minimum_review_level = models.PositiveSmallIntegerField(
        "Cấp xác nhận tối thiểu", null=True, blank=True
    )
    independent_review = models.BooleanField(
        "Người xác nhận độc lập người lập/phụ trách/thực hiện", null=True, blank=True
    )
    require_higher_level = models.BooleanField(
        "Người xác nhận phải cao cấp hơn người lập", null=True, blank=True
    )
    max_extensions = models.PositiveSmallIntegerField(
        "Số lần gia hạn tối đa mỗi công việc", null=True, blank=True
    )
    revision = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )
    updated_at = models.DateTimeField(auto_now=True)


class Case(models.Model):
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    title = models.CharField("Tiêu đề sai lệch", max_length=200)
    category = models.ForeignKey(
        Category, verbose_name="Nhóm sai lệch", on_delete=models.PROTECT
    )
    department = models.CharField("Phòng ban liên quan", max_length=120)
    location = models.CharField("Địa điểm", max_length=200, blank=True)
    occurred_at = models.DateTimeField(
        "Thời điểm xảy ra (nếu biết)", null=True, blank=True
    )
    detected_at = models.DateTimeField("Thời điểm phát hiện", default=timezone.now)
    actual = models.TextField("Thực tế đã xảy ra", max_length=6000)
    expected = models.TextField(
        "Yêu cầu cần đáp ứng / căn cứ", max_length=4000, blank=True
    )
    immediate_response = models.TextField(
        "Biện pháp tức thời đã thực hiện", max_length=4000, blank=True
    )
    impact = models.TextField("Phạm vi / mức độ ảnh hưởng", max_length=4000, blank=True)
    estimated_loss = models.DecimalField(
        "Ảnh hưởng ước tính (đ)",
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    severity = models.CharField("Mức độ", choices=SEVERITIES, max_length=12, blank=True)
    findings = models.TextField("Kết quả xác minh", max_length=6000, blank=True)
    direct_cause = models.TextField(
        "Nguyên nhân trực tiếp", max_length=4000, blank=True
    )
    root_cause = models.TextField("Nguyên nhân gốc rễ", max_length=4000, blank=True)
    related_people = models.TextField(
        "Người / bộ phận liên quan và căn cứ", max_length=3000, blank=True
    )
    source_document = models.ForeignKey(
        "inventory.Document", null=True, blank=True, on_delete=models.SET_NULL
    )
    source_product = models.ForeignKey(
        "inventory.Product", null=True, blank=True, on_delete=models.SET_NULL
    )
    source_stocktake = models.ForeignKey(
        "inventory.StocktakeSession", null=True, blank=True, on_delete=models.SET_NULL
    )
    creator_level = models.PositiveSmallIntegerField(default=10, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviations_created",
        on_delete=models.PROTECT,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviations_owned",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    status = models.CharField(
        max_length=16, choices=CaseStatus.choices, default=CaseStatus.DRAFT
    )
    round = models.PositiveIntegerField(default=1)
    revision = models.PositiveIntegerField(default=1)
    policy_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-pk"]
        indexes = [
            models.Index(fields=["status", "-id"]),
            models.Index(fields=["owner", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(estimated_loss__isnull=True) | Q(estimated_loss__gte=0),
                name="deviation_nonnegative_loss",
            )
        ]

    @property
    def code(self):
        return f"SL-{self.created_at.year}-{self.pk:06d}"

    @property
    def is_terminal(self):
        return self.status in TERMINAL

    def __str__(self):
        return self.code


class Action(models.Model):
    case = models.ForeignKey(Case, related_name="actions", on_delete=models.PROTECT)
    round = models.PositiveIntegerField(default=1)
    kind = models.CharField("Loại hành động", choices=ActionKind.choices, max_length=12)
    title = models.CharField("Công việc cần thực hiện", max_length=250)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người chịu trách nhiệm",
        on_delete=models.PROTECT,
    )
    collaborators = models.CharField("Người phối hợp", max_length=250, blank=True)
    due_date = models.DateField("Hạn hoàn thành", null=True, blank=True)
    status = models.CharField(
        choices=ActionStatus.choices, max_length=16, default=ActionStatus.OPEN
    )
    result = models.TextField("Kết quả thực hiện / căn cứ", max_length=5000, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["round", "pk"]

    @property
    def overdue(self):
        return bool(
            self.due_date
            and self.due_date < timezone.localdate()
            and self.status != ActionStatus.DONE
            and not self.case.is_terminal
        )


class Evaluation(models.Model):
    case = models.ForeignKey(Case, related_name="evaluations", on_delete=models.PROTECT)
    round = models.PositiveIntegerField()
    criteria = models.TextField(max_length=4000)
    result = models.TextField(max_length=5000)
    effective = models.BooleanField()
    checked_at = models.DateTimeField(default=timezone.now)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    policy_snapshot = models.JSONField(default=dict)


class Extension(models.Model):
    action = models.ForeignKey(
        Action, related_name="extensions", on_delete=models.PROTECT
    )
    old_due_date = models.DateField()
    new_due_date = models.DateField("Hạn đề nghị", null=False)
    reason = models.CharField("Lý do gia hạn", max_length=1000)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_extensions",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        default="PENDING",
        choices=[
            ("PENDING", "Chờ quyết định"),
            ("APPROVED", "Đồng ý"),
            ("REJECTED", "Không đồng ý"),
        ],
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_extension_decisions",
        null=True,
        on_delete=models.PROTECT,
    )
    decided_at = models.DateTimeField(null=True)
    decision_reason = models.CharField(max_length=1000, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["action"],
                condition=Q(status="PENDING"),
                name="one_pending_deviation_extension",
            )
        ]


class Attachment(models.Model):
    case = models.ForeignKey(Case, related_name="attachments", on_delete=models.PROTECT)
    action = models.ForeignKey(Action, null=True, blank=True, on_delete=models.PROTECT)
    file = models.ForeignKey("inventory.StoredFile", on_delete=models.PROTECT)
    stage = models.CharField(max_length=16, choices=CaseStatus.choices)
    round = models.PositiveIntegerField()
    filename = models.CharField(max_length=150)
    description = models.CharField("Nội dung / căn cứ", max_length=250)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    void_reason = models.CharField(max_length=1000, blank=True)
    voided_at = models.DateTimeField(null=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_files_voided",
        null=True,
        on_delete=models.PROTECT,
    )

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["case", "file"],
                condition=Q(voided_at__isnull=True),
                name="unique_live_deviation_file",
            )
        ]


class Event(models.Model):
    case = models.ForeignKey(Case, related_name="events", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    reason = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

    class Meta:
        ordering = ["pk"]


class PolicyEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=1000)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

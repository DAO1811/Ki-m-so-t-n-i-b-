from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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
    form_version = models.PositiveSmallIntegerField(
        default=1, db_default=1, editable=False
    )
    reporter_name = models.CharField(
        max_length=200, blank=True, editable=False, default="", db_default=""
    )
    reporter_job_title = models.CharField(
        "Chức danh người lập", max_length=120, blank=True, default="", db_default=""
    )
    reported_at = models.DateTimeField(
        "Thời điểm đã báo Trưởng bộ phận", null=True, blank=True
    )
    discoverer_name = models.CharField(
        "Họ tên người phát hiện", max_length=200, blank=True, default="", db_default=""
    )
    discoverer_job_title = models.CharField(
        "Chức danh người phát hiện",
        max_length=120,
        blank=True,
        default="",
        db_default="",
    )
    what_changed = models.TextField(
        "Cái gì thay đổi?", max_length=4000, blank=True, default="", db_default=""
    )
    detection_method = models.TextField(
        "Đã phát hiện bằng cách nào?",
        max_length=3000,
        blank=True,
        default="",
        db_default="",
    )
    gap_analysis = models.TextField(
        "Phân tích chênh lệch ban đầu",
        max_length=4000,
        blank=True,
        default="",
        db_default="",
    )
    special_comments = models.TextField(
        "Nghi vấn / nhận xét đặc biệt",
        max_length=4000,
        blank=True,
        default="",
        db_default="",
    )
    investigation_5w1h = models.JSONField(default=dict, blank=True, db_default={})
    investigation_expected = models.TextField(
        "Điều gì nên xảy ra — sau xác minh",
        max_length=4000,
        blank=True,
        default="",
        db_default="",
    )
    investigation_gap = models.TextField(
        "Phân tích chênh lệch sau xác minh",
        max_length=4000,
        blank=True,
        default="",
        db_default="",
    )
    affected_steps = models.TextField(
        "Các khâu bị ảnh hưởng", max_length=4000, blank=True, default="", db_default=""
    )
    has_history = models.BooleanField(
        "Đã từng xảy ra trước đây?", null=True, blank=True
    )
    history_details = models.TextField(
        "Lịch sử / kết quả tra cứu tái diễn",
        max_length=4000,
        blank=True,
        default="",
        db_default="",
    )
    event_sequence = models.TextField(
        "Trình tự xảy ra sự cố", max_length=5000, blank=True, default="", db_default=""
    )
    cause_factors = models.JSONField(default=dict, blank=True, db_default={})
    five_whys = models.JSONField(default=list, blank=True, db_default=[])
    causal_factors = models.TextField(
        "Nhân tố liên quan nguyên nhân và hậu quả",
        max_length=4000,
        blank=True,
        default="",
        db_default="",
    )
    likelihood = models.PositiveSmallIntegerField(
        "Khả năng xảy ra",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    consequence = models.PositiveSmallIntegerField(
        "Hậu quả",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    risk_details = models.TextField(
        "Căn cứ đánh giá rủi ro", max_length=4000, blank=True, default="", db_default=""
    )

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
    department_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_department_reviews",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    control_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_control_reviews",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    specialist_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_specialist_reviews",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    related_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_related_reviews",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    director_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="deviation_director_reviews",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
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
    def risk_score(self):
        return (
            self.likelihood * self.consequence
            if self.likelihood and self.consequence
            else None
        )

    @property
    def risk_level(self):
        from .form_schema import risk_band

        return risk_band(self.risk_score)

    @property
    def is_terminal(self):
        return self.status in TERMINAL

    def __str__(self):
        return self.code


class Action(models.Model):
    problem = models.TextField(
        "Tồn tại / vấn đề cần giải quyết",
        max_length=3000,
        blank=True,
        default="",
        db_default="",
    )
    corrective_action = models.TextField(
        "Hành động khắc phục / tức thời",
        max_length=4000,
        blank=True,
        default="",
        db_default="",
    )
    preventive_action = models.TextField(
        "Hành động ngăn ngừa", max_length=4000, blank=True, default="", db_default=""
    )
    responsible_department = models.CharField(
        "Bộ phận chịu trách nhiệm",
        max_length=120,
        blank=True,
        default="",
        db_default="",
    )

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

    @property
    def capa_code(self):
        return (
            f"CAPA-{self.case.created_at.year}-{self.case_id:06d}-{self.pk:04d}"
            if self.pk
            else "Cấp khi lưu"
        )

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
    checked_by_name = models.CharField(
        max_length=200, blank=True, editable=False, default="", db_default=""
    )
    checked_by_job_title = models.CharField(
        max_length=120, blank=True, editable=False, default="", db_default=""
    )
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


class ApprovalRun(models.Model):
    case = models.ForeignKey(
        Case, related_name="approval_runs", on_delete=models.PROTECT
    )
    stage = models.CharField(
        max_length=12,
        choices=[
            ("REPORT", "Báo cáo"),
            ("ANALYSIS", "Điều tra"),
            ("CAPA", "Kế hoạch CAPA"),
        ],
    )
    round = models.PositiveIntegerField()
    cycle = models.PositiveIntegerField()
    status = models.CharField(
        max_length=12,
        default="PENDING",
        choices=[
            ("PENDING", "Chờ xác nhận"),
            ("APPROVED", "Đã xác nhận"),
            ("RETURNED", "Trả lại bổ sung"),
            ("SUPERSEDED", "Được thay thế"),
        ],
    )
    current_step = models.PositiveSmallIntegerField(default=1)
    participants = models.JSONField(default=dict)
    payload = models.JSONField(default=dict)
    labels = models.JSONField(default=dict, editable=False)
    fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    proposer_level = models.PositiveSmallIntegerField()
    proposer_name = models.CharField(max_length=200)
    proposer_job_title = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["case", "stage", "round", "cycle"],
                name="unique_deviation_approval_cycle",
            ),
            models.UniqueConstraint(
                fields=["case"],
                condition=Q(status="PENDING"),
                name="one_pending_deviation_approval",
            ),
        ]


class ApprovalDecision(models.Model):
    classification = models.CharField(
        "Phân loại do cấp duyệt chọn",
        max_length=12,
        choices=SEVERITIES,
        default="",
        blank=True,
        db_default="",
    )
    run = models.ForeignKey(
        ApprovalRun, related_name="decisions", on_delete=models.PROTECT
    )
    step = models.PositiveSmallIntegerField()
    role = models.CharField(max_length=20)
    decision = models.CharField(
        max_length=10,
        choices=[("APPROVE", "Đồng ý"), ("RETURN", "Không duyệt / trả lại")],
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_name = models.CharField(max_length=200)
    actor_job_title = models.CharField(max_length=120, blank=True)
    reason = models.CharField(max_length=1000, blank=True)
    admin_override = models.BooleanField(default=False)
    self_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "step"], name="one_decision_per_deviation_step"
            )
        ]

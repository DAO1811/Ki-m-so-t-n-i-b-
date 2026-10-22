from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from inventory.access import has_function
from inventory.models import Product, StocktakeSession
from inventory.services import can_approve_adjustments, documents_for, warehouses_for

from .models import Action, Case, Category, WorkflowPolicy
from .services.cases import ANALYSIS_FIELDS, REPORT_FIELDS

DATETIME = forms.DateTimeInput(
    attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
)


class RevisionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class ReportForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    class Meta:
        model = Case
        fields = REPORT_FIELDS
        labels = {
            "source_document": "ID phiếu kho liên quan",
            "source_product": "ID hàng hóa liên quan",
            "source_stocktake": "ID biên bản kiểm kê liên quan",
        }
        widgets = {
            "detected_at": DATETIME,
            "occurred_at": DATETIME,
            **{
                key: forms.Textarea(attrs={"rows": 3})
                for key in ("actual", "expected", "immediate_response", "impact")
            },
            **{
                key: forms.NumberInput(attrs={"min": 1})
                for key in ("source_document", "source_product", "source_stocktake")
            },
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(active=True)
        self.fields["source_document"].queryset = documents_for(user)
        self.fields["source_product"].queryset = (
            Product.objects.all()
            if has_function(user, "products_view")
            else Product.objects.none()
        )
        self.fields["source_stocktake"].queryset = StocktakeSession.objects.all()
        # Keep compatibility with the running warehouse schema; do not upgrade it.
        if hasattr(StocktakeSession, "deletion"):
            self.fields["source_stocktake"].queryset = self.fields[
                "source_stocktake"
            ].queryset.filter(deletion__isnull=True)
        if not has_function(user, "stocktakes_view"):
            self.fields["source_stocktake"].queryset = StocktakeSession.objects.none()
        elif not can_approve_adjustments(user):
            self.fields["source_stocktake"].queryset = self.fields[
                "source_stocktake"
            ].queryset.filter(warehouse__in=warehouses_for(user))
        if self.instance.pk:
            self.initial["revision"] = self.instance.revision
        self.fields[
            "occurred_at"
        ].help_text = "Để trống nếu chưa xác định; không điền ngày giả."
        self.fields[
            "estimated_loss"
        ].help_text = "Chỉ ghi khi có căn cứ; có thể bổ sung sau."
        for key in ("source_document", "source_product", "source_stocktake"):
            self.fields[
                key
            ].help_text = "Nhập ID trong phần mềm nếu có; hệ thống kiểm tra quyền đối với hồ sơ nguồn."


class AnalysisForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = Case
        fields = ANALYSIS_FIELDS
        widgets = {
            key: forms.Textarea(attrs={"rows": 3})
            for key in ANALYSIS_FIELDS
            if key != "severity"
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["revision"] = self.instance.revision


class AssignmentForm(RevisionForm):
    owner = forms.ModelChoiceField(
        label="Người phụ trách hồ sơ",
        queryset=get_user_model().objects.filter(is_active=True).order_by("username"),
    )


class TransitionForm(RevisionForm):
    command = forms.CharField(max_length=40)
    reason = forms.CharField(
        label="Lý do / nội dung cần bổ sung",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    confirm = forms.BooleanField(
        required=False,
        label="Tôi đã kiểm tra cảnh báo Admin tự xác nhận hồ sơ liên quan chính mình",
    )
    duplicate_of = forms.ModelChoiceField(
        label="ID hồ sơ gốc nếu trùng",
        required=False,
        queryset=Case.objects.all(),
        widget=forms.NumberInput(attrs={"min": 1}),
    )


class ActionForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action_revision = forms.IntegerField(
        min_value=1, required=False, widget=forms.HiddenInput
    )

    class Meta:
        model = Action
        fields = ("kind", "title", "assignee", "collaborators", "due_date")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = (
            get_user_model().objects.filter(is_active=True).order_by("username")
        )
        self.initial["revision"] = case.revision
        self.initial["action_revision"] = (
            self.instance.revision if self.instance.pk else None
        )


class WorkForm(RevisionForm):
    action_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    status = forms.ChoiceField(
        label="Tiến độ",
        choices=[("IN_PROGRESS", "Đang thực hiện"), ("DONE", "Đã thực hiện")],
    )
    result = forms.CharField(
        label="Kết quả thực hiện / căn cứ",
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )


class ExtensionForm(RevisionForm):
    action_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    new_due_date = forms.DateField(
        label="Hạn đề nghị mới", widget=forms.DateInput(attrs={"type": "date"})
    )
    reason = forms.CharField(
        label="Lý do gia hạn", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )


class DecisionForm(RevisionForm):
    approve = forms.TypedChoiceField(
        label="Quyết định",
        choices=[("yes", "Đồng ý"), ("no", "Không đồng ý")],
        coerce=lambda v: v == "yes",
    )
    reason = forms.CharField(
        label="Căn cứ quyết định",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    confirm = forms.BooleanField(
        required=False, label="Tôi đã kiểm tra và xác nhận ngoại lệ Admin tự duyệt"
    )


class EvaluationForm(RevisionForm):
    criteria = forms.CharField(
        label="Tiêu chí / phạm vi kiểm tra",
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    result = forms.CharField(
        label="Kết quả kiểm tra và bằng chứng",
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    effective = forms.TypedChoiceField(
        label="Kết luận",
        choices=[
            ("yes", "Có hiệu quả — xác nhận kết thúc"),
            ("no", "Chưa hiệu quả — bổ sung hành động"),
        ],
        coerce=lambda v: v == "yes",
    )
    checked_at = forms.DateTimeField(
        label="Thời điểm kiểm tra", initial=timezone.now, widget=DATETIME
    )
    confirm = forms.BooleanField(
        required=False, label="Tôi đã kiểm tra và xác nhận ngoại lệ Admin tự duyệt"
    )


class UploadForm(RevisionForm):
    file = forms.FileField(
        label="Ảnh hoặc PDF",
        widget=forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf"}),
    )
    description = forms.CharField(label="Nội dung / căn cứ", max_length=250)
    action = forms.ModelChoiceField(
        label="Gắn với công việc (nếu có)",
        queryset=Action.objects.none(),
        required=False,
    )

    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["action"].queryset = case.actions.filter(round=case.round)
        self.initial["revision"] = case.revision


class VoidForm(RevisionForm):
    reason = forms.CharField(max_length=1000, label="Lý do đánh dấu không sử dụng")


class PolicyForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reason = forms.CharField(
        label="Căn cứ thay đổi / xác nhận quy trình đã được thống nhất",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    minimum_review_level = forms.TypedChoiceField(
        label="Cấp xác nhận tối thiểu",
        choices=[
            ("", "Chưa chốt"),
            (10, "Nhân viên"),
            (20, "Leader"),
            (30, "Trưởng phòng"),
            (40, "Admin tổng"),
        ],
        coerce=lambda v: int(v) if v else None,
        empty_value=None,
        required=False,
    )

    class Meta:
        model = WorkflowPolicy
        fields = (
            "enabled",
            "minimum_review_level",
            "independent_review",
            "require_higher_level",
            "max_extensions",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["revision"] = self.instance.revision
        self.fields[
            "max_extensions"
        ].help_text = "Để trống: chưa mở gia hạn. 0: không gia hạn. Không có số lần mặc định từ tài liệu tham khảo."


class CategoryForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    class Meta:
        model = Category
        fields = ("name", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["revision"].required = True
            self.initial["revision"] = self.instance.revision

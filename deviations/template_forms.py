"""Human fields and formsets for the approved company form; no JSON editors."""

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from inventory.models import FunctionAccess

from . import forms as base
from .form_schema import (
    ACTION_EXTRA,
    ANALYSIS_EXTRA,
    CONSEQUENCE,
    FACTOR_STATES,
    FACTORS,
    LIKELIHOOD,
    PARTICIPANTS,
    QUESTIONS,
    REPORT_EXTRA,
    ROLES,
)
from .models import Case
from .services.form_data import display_name, job_title


def eligible_users(permission):
    ids = [
        pk
        for pk, codes in FunctionAccess.objects.values_list("user_id", "permissions")
        if isinstance(codes, list) and permission in codes
    ]
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(pk__in=ids))
        .order_by("username")
    )


def sections(form, groups):
    return [
        {"title": title, "fields": [form[key] for key in fields]}
        for title, fields in groups
    ]


class ReportForm(base.ReportForm):
    class Meta(base.ReportForm.Meta):
        fields = base.ReportForm.Meta.fields + REPORT_EXTRA
        widgets = {
            **base.ReportForm.Meta.widgets,
            "reported_at": base.DATETIME,
            **{
                key: forms.Textarea(attrs={"rows": 3})
                for key in (
                    "what_changed",
                    "detection_method",
                    "gap_analysis",
                    "special_comments",
                )
            },
        }
        labels = {
            **base.ReportForm.Meta.labels,
            "department_reviewer": "Trưởng bộ phận phát hiện — duyệt bước 1",
            "control_reviewer": "KSNB — duyệt bước 2",
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.reporter_label = (
            self.instance.reporter_name if self.instance.pk else display_name(user)
        )
        if not self.instance.pk:
            self.initial.setdefault("reporter_job_title", job_title(user))
            self.initial.setdefault("discoverer_name", display_name(user))
            self.initial.setdefault("discoverer_job_title", job_title(user))
        for role in ("department", "control"):
            self.fields[ROLES[role][1]].queryset = eligible_users(ROLES[role][2])
        self.fields[
            "reported_at"
        ].help_text = "Thời điểm người phát hiện đã báo Trưởng bộ phận, không phải thời điểm bấm gửi trên phần mềm."
        self.fields[
            "special_comments"
        ].help_text = "Ghi rõ nếu không có; không tự lấy nội dung mẫu."
        self.sections = sections(
            self,
            [
                (
                    "1. Thông tin sai lệch",
                    (
                        "title",
                        "category",
                        "department",
                        "occurred_at",
                        "detected_at",
                        "reported_at",
                        "reporter_job_title",
                    ),
                ),
                (
                    "2. Mô tả theo 5W1H",
                    (
                        "discoverer_name",
                        "discoverer_job_title",
                        "location",
                        "actual",
                        "what_changed",
                        "detection_method",
                    ),
                ),
                (
                    "3. Phân tích chênh lệch ban đầu",
                    ("expected", "gap_analysis", "impact", "estimated_loss"),
                ),
                ("4. Nghi vấn / nhận xét đặc biệt", ("special_comments",)),
                ("5. Biện pháp tức thời", ("immediate_response",)),
                (
                    "6. Phân công xác nhận báo cáo",
                    ("department_reviewer", "control_reviewer"),
                ),
            ],
        )


class WhyForm(forms.Form):
    cause = forms.CharField(
        label="Nguyên nhân tiềm tàng",
        max_length=1500,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    why1 = forms.CharField(
        label="Tại sao 1", max_length=1500, widget=forms.Textarea(attrs={"rows": 2})
    )
    why2 = forms.CharField(
        label="Tại sao 2",
        max_length=1500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    why3 = forms.CharField(
        label="Tại sao 3",
        max_length=1500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    why4 = forms.CharField(
        label="Tại sao 4",
        max_length=1500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    why5 = forms.CharField(
        label="Tại sao 5",
        max_length=1500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


WhyFormSet = forms.formset_factory(
    WhyForm, extra=1, can_delete=True, max_num=20, validate_max=True, absolute_max=25
)


class AnalysisForm(base.AnalysisForm):
    class Meta(base.AnalysisForm.Meta):
        fields = base.AnalysisForm.Meta.fields + tuple(
            k
            for k in ANALYSIS_EXTRA
            if k not in {"investigation_5w1h", "cause_factors", "five_whys"}
        )
        widgets = {
            **base.AnalysisForm.Meta.widgets,
            **{
                key: forms.Textarea(attrs={"rows": 3})
                for key in (
                    "investigation_expected",
                    "investigation_gap",
                    "affected_steps",
                    "history_details",
                    "event_sequence",
                    "causal_factors",
                    "risk_details",
                )
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        case = self.instance
        initial_answers = {
            "who": f"{case.discoverer_name} — {case.discoverer_job_title}",
            "when": timezone.localtime(case.detected_at).strftime("%d/%m/%Y %H:%M"),
            "where": case.location,
            "what": case.actual,
            "which": case.what_changed,
            "how": case.detection_method,
        }
        self.question_rows = []
        for key, label in QUESTIONS:
            old = case.investigation_5w1h.get(key, {})
            for suffix, title in [
                ("answer", "Trả lời"),
                ("evidence", "Dữ liệu / căn cứ đối chiếu"),
            ]:
                name = f"{key}_{suffix}"
                self.fields[name] = forms.CharField(
                    label=label + " — " + title,
                    max_length=3000,
                    required=False,
                    widget=forms.Textarea(attrs={"rows": 2}),
                    initial=old.get(
                        suffix, initial_answers[key] if suffix == "answer" else ""
                    ),
                )
            self.question_rows.append(
                {
                    "label": label,
                    "answer": self[f"{key}_answer"],
                    "evidence": self[f"{key}_evidence"],
                }
            )
        self.factor_rows = []
        for key, label in FACTORS:
            old = case.cause_factors.get(key, {})
            self.fields[f"{key}_status"] = forms.ChoiceField(
                label=label + " — Kết luận",
                choices=FACTOR_STATES,
                required=False,
                initial=old.get("status", ""),
            )
            self.fields[f"{key}_details"] = forms.CharField(
                label=label + " — Giải thích / căn cứ",
                max_length=3000,
                required=False,
                initial=old.get("details", ""),
                widget=forms.Textarea(attrs={"rows": 2}),
            )
            self.factor_rows.append(
                {
                    "label": label,
                    "status": self[f"{key}_status"],
                    "details": self[f"{key}_details"],
                }
            )
        for name, choices in [("likelihood", LIKELIHOOD), ("consequence", CONSEQUENCE)]:
            self.fields[name] = forms.TypedChoiceField(
                label=self.fields[name].label,
                choices=[("", "Chưa đánh giá"), *choices],
                coerce=int,
                empty_value=None,
                required=False,
                widget=forms.Select(attrs={"data-risk-input": name}),
            )
        self.sections = sections(
            self,
            [
                (
                    "2. Phân tích sự chênh lệch",
                    (
                        "findings",
                        "investigation_expected",
                        "investigation_gap",
                        "affected_steps",
                        "impact",
                    ),
                ),
                (
                    "3a. Lịch sử và trình tự sự cố",
                    ("has_history", "history_details", "event_sequence"),
                ),
            ],
        )
        self.fields["severity"].label = "Phân loại đề xuất — cấp duyệt quyết định"
        self.fields[
            "risk_details"
        ].help_text = "Ghi căn cứ đánh giá rủi ro và đề xuất phân loại; hai kết luận không tự quy đổi cho nhau."
        self.risk_fields = [
            self[k] for k in ("likelihood", "consequence", "risk_details", "severity")
        ]
        self.conclusion_fields = [
            self[k]
            for k in ("direct_cause", "root_cause", "causal_factors", "related_people")
        ]

    def clean(self):
        data = super().clean()
        data["investigation_5w1h"] = {
            key: {
                suffix: data.get(f"{key}_{suffix}", "")
                for suffix in ("answer", "evidence")
            }
            for key, _ in QUESTIONS
        }
        data["cause_factors"] = {
            key: {
                "status": data.get(f"{key}_status", ""),
                "details": data.get(f"{key}_details", ""),
            }
            for key, _ in FACTORS
        }
        return data


class ActionForm(base.ActionForm):
    class Meta(base.ActionForm.Meta):
        fields = base.ActionForm.Meta.fields + ACTION_EXTRA
        widgets = {
            **base.ActionForm.Meta.widgets,
            **{
                key: forms.Textarea(attrs={"rows": 3})
                for key in ("problem", "corrective_action", "preventive_action")
            },
        }

    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        self.fields["assignee"].queryset = eligible_users("deviations_work")
        if not self.instance.pk:
            self.initial["responsible_department"] = case.department
        self.sections = sections(
            self,
            [
                (
                    "Dòng kế hoạch CAPA",
                    (
                        "kind",
                        "title",
                        "problem",
                        "corrective_action",
                        "preventive_action",
                    ),
                ),
                (
                    "Trách nhiệm và thời hạn",
                    ("assignee", "responsible_department", "collaborators", "due_date"),
                ),
            ],
        )


class AssignmentForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = Case
        fields = PARTICIPANTS
        labels = {
            "owner": "Người phụ trách điều tra / soạn CAPA",
            **{field: label for label, field, _ in ROLES.values()},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["revision"] = self.instance.revision
        self.fields["owner"].queryset = eligible_users("deviations_manage")
        pending = (
            self.instance.approval_runs.filter(status="PENDING").first()
            if self.instance.pk
            else None
        )
        for _, field, permission in ROLES.values():
            self.fields[field].queryset = eligible_users(permission)
            if pending:
                self.fields[field].disabled = True
                self.fields[
                    field
                ].help_text = "Đã chốt trong phiếu đang duyệt; rút phiếu nếu cần đổi."


class ApprovalForm(base.RevisionForm):
    classification = forms.ChoiceField(
        label="Phân loại sai lệch do cấp duyệt chọn",
        choices=[
            ("", "Chọn phân loại"),
            ("MINOR", "Nhỏ"),
            ("MAJOR", "Lớn"),
            ("CRITICAL", "Nghiêm trọng"),
        ],
        required=False,
    )
    owner = forms.ModelChoiceField(
        label="Người phụ trách điều tra / soạn CAPA",
        queryset=get_user_model().objects.none(),
        required=False,
    )

    def __init__(self, *args, allow_owner=False, allow_classification=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not allow_classification:
            self.fields.pop("classification")
        else:
            self.fields[
                "classification"
            ].help_text = "Chọn theo căn cứ, không tự đổi theo RIV. Nếu khác đề xuất/kết luận trước đó, ghi lý do."
        if allow_owner:
            self.fields["owner"].queryset = eligible_users("deviations_manage")
            self.fields["owner"].help_text = "KSNB phân công khi tiếp nhận báo cáo."
        else:
            self.fields.pop("owner")

    decision = forms.ChoiceField(
        label="Quyết định",
        choices=[("APPROVE", "Đồng ý"), ("RETURN", "Không duyệt — trả lại bổ sung")],
    )
    reason = forms.CharField(
        label="Căn cứ / nội dung cần bổ sung / lý do Admin xử lý thay",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    confirm = forms.BooleanField(
        label="Tôi đã kiểm tra cảnh báo Admin tự xác nhận / kiêm nhiệm nhiều vai trò",
        required=False,
    )

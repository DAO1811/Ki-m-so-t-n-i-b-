from .access import can_create_kind
from django import forms
from django.forms import formset_factory, BaseFormSet
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import Document, Product, CustomField, Warehouse, Line
from .services import (
    warehouses_for,
    documents_for,
    validate_document,
    validate_line_details,
)

DOCUMENT_DETAILS = [
    "business_date",
    "reference_number",
    "reference_date",
    "counterparty",
    "counterparty_address",
    "department",
    "handed_over_by",
    "received_by",
    "due_date",
]


def configure_document_details(form, operation):
    for name in ["business_date", "reference_date", "due_date"]:
        form.fields[name].widget = forms.DateInput(
            format="%Y-%m-%d", attrs={"type": "date"}
        )
    form.fields["business_date"].required = False
    form.fields["business_date"].label = {
        "IN": "Ngày nhập thực tế",
        "OUT": "Ngày xuất thực tế",
        "COUNT": "Ngày kiểm kê",
        "LOAN": "Ngày cho mượn",
        "RETURN": "Ngày trả thực tế",
    }.get(operation, "Ngày nghiệp vụ thực tế")
    form.fields["business_date"].widget.attrs["readonly"] = True
    form.initial["business_date"] = timezone.localdate()
    form.fields[
        "business_date"
    ].help_text = "Chỉ dùng ngày hôm nay theo quy định công ty. Tồn và giá vốn chỉ cập nhật khi người được phân công duyệt. Phiếu sang ngày mới cần người lập cập nhật lại."
    if operation != "LOAN":
        form.fields["due_date"].widget = forms.HiddenInput()


class DocumentForm(forms.ModelForm):
    submission_key = forms.UUIDField(required=False, widget=forms.HiddenInput())
    revision = forms.IntegerField(
        required=False, min_value=1, widget=forms.HiddenInput()
    )

    @property
    def core_fields(self):
        return [
            field
            for field in self
            if field.name not in DOCUMENT_DETAILS or field.name == "business_date"
        ]

    @property
    def detail_fields(self):
        return [self[name] for name in DOCUMENT_DETAILS if name != "business_date"]

    class Meta:
        model = Document
        fields = ["kind", "source", "destination", "loan", *DOCUMENT_DETAILS, "note"]
        widgets = {
            "note": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Nội dung mua hàng, mục đích xuất hoặc lý do chênh lệch…",
                }
            )
        }

    def __init__(self, *args, user, fixed_kind=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["revision"] = self.instance.revision
        self.fields["revision"].required = bool(self.instance.pk)
        self.fields["kind"].choices = [
            (code, label)
            for code, label in Document.TYPES
            if can_create_kind(user, code)
        ]
        self.fixed_kind = fixed_kind
        self.operation = fixed_kind or (
            self.data.get("kind")
            if self.is_bound
            else self.initial.get("kind", self.instance.kind or "IN")
        )
        configure_document_details(self, self.operation)
        if fixed_kind:
            self.fields["kind"].widget = forms.HiddenInput()
            self.initial["kind"] = fixed_kind
        self.fields["source"].queryset = warehouses_for(user).order_by("code")
        self.fields["destination"].queryset = (
            Warehouse.objects.all()
            if self.operation in ["TRANSFER", "LOAN", "RETURN"]
            else warehouses_for(user)
        ).order_by("code")
        self.fields["loan"].queryset = (
            documents_for(user).filter(kind="LOAN", status="POSTED").order_by("-id")
        )
        source_needed = self.operation in ["OUT", "TRANSFER", "LOAN", "RETURN"]
        destination_needed = self.operation != "OUT"
        self.fields["source"].required = source_needed
        self.fields["destination"].required = destination_needed
        self.fields["loan"].required = self.operation == "RETURN"
        self.fields["note"].required = self.operation in ["COUNT", "ADJUST"]
        self.fields["source"].label = (
            "Kho cho mượn" if self.operation == "LOAN" else "Kho xuất"
        )
        self.fields["destination"].label = {
            "COUNT": "Kho kiểm kê",
            "ADJUST": "Kho điều chỉnh",
            "LOAN": "Kho mượn",
        }.get(self.operation, "Kho nhận")
        self.fields["loan"].label = "Lệnh mượn cần trả"
        if self.operation == "RETURN":
            self.order_fields(
                ["kind", "submission_key", "loan", "source", "destination", "note"]
            )
            loan_id = (
                self.data.get("loan") if self.is_bound else self.initial.get("loan")
            )
            if hasattr(loan_id, "pk"):
                loan_id = loan_id.pk
            loan = (
                self.fields["loan"].queryset.filter(pk=loan_id).first()
                if str(loan_id).isdigit() and len(str(loan_id)) <= 18
                else None
            )
            if loan:
                self.initial.update(
                    source=loan.destination_id, destination=loan.source_id
                )
            self.fields["source"].disabled = True
            self.fields["destination"].disabled = True
        for name, needed in [
            ("source", source_needed),
            ("destination", destination_needed),
            ("loan", self.operation == "RETURN"),
        ]:
            if fixed_kind and not needed:
                self.fields[name].widget = forms.HiddenInput()
                self.fields[name].required = False

    def clean(self):
        data = super().clean()
        data["business_date"] = data.get("business_date") or timezone.localdate()
        if self.fixed_kind and data.get("kind") != self.fixed_kind:
            raise forms.ValidationError("Loại phiếu không khớp với nghiệp vụ đang mở.")
        if not self.errors:
            validate_document(Document(**{k: data.get(k) for k in self.Meta.fields}))
        return data


class LineForm(forms.Form):
    expected_quantity = forms.DecimalField(
        label="SL theo chứng từ",
        max_digits=16,
        decimal_places=3,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"step": "0.001"}),
    )
    rejected_quantity = forms.DecimalField(
        label="SL không nhận",
        max_digits=16,
        decimal_places=3,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"step": "0.001", "placeholder": "0"}),
    )
    note = forms.CharField(
        label="Tình trạng / lý do thiếu, hỏng", max_length=250, required=False
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.order_by("sku"), label="Hàng hóa"
    )
    quantity = forms.DecimalField(
        max_digits=16,
        decimal_places=3,
        label="Số lượng",
        widget=forms.NumberInput(attrs={"step": "0.001", "placeholder": "0"}),
    )
    unit_price = forms.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=0,
        required=False,
        label="Đơn giá (VNĐ)",
        widget=forms.NumberInput(attrs={"step": "0.0001", "placeholder": "0"}),
    )


class BaseLineFormSet(BaseFormSet):
    def __init__(self, *args, kind="IN", **kwargs):
        self.kind = kind
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            data = form.cleaned_data
            if not data or data.get("DELETE"):
                continue
            product = data["product"]
            if product.pk in seen:
                raise forms.ValidationError(
                    "Mỗi mã hàng chỉ nhập một lần. Hãy gộp số lượng trên cùng một dòng."
                )
            seen.add(product.pk)
            q = data["quantity"]
            data["rejected_quantity"] = data.get("rejected_quantity") or 0
            if self.kind != "IN":
                data["expected_quantity"] = None
                data["rejected_quantity"] = 0
            try:
                validate_line_details(
                    Document(kind=self.kind),
                    Line(**{k: v for k, v in data.items() if k != "DELETE"}),
                )
            except forms.ValidationError as exc:
                form.add_error(None, exc)
            zero_receipt = (
                self.kind == "IN"
                and q == 0
                and (data.get("expected_quantity") or data.get("rejected_quantity"))
            )
            if self.kind not in ["COUNT", "ADJUST"] and q <= 0 and not zero_receipt:
                form.add_error("quantity", "Số lượng phải lớn hơn 0.")
            if self.kind == "COUNT" and q < 0:
                form.add_error("quantity", "Số thực đếm không được âm.")
            if self.kind == "IN" and data.get("unit_price") is None:
                form.add_error(
                    "unit_price", "Nhập đơn giá; nhập 0 nếu là hàng miễn phí."
                )
            if self.kind not in ["IN", "COUNT", "ADJUST"]:
                data["unit_price"] = None


LineFormSet = formset_factory(
    LineForm,
    formset=BaseLineFormSet,
    extra=0,
    max_num=50,
    validate_max=True,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "unit",
            "category",
            "brand",
            "model_number",
            "specifications",
            "storage_instructions",
            "minimum",
        ]
        widgets = {
            "specifications": forms.Textarea(attrs={"rows": 3}),
            "storage_instructions": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "minimum"
        ].help_text = "Cảnh báo khi tồn khả dụng tại một kho thấp hơn mức này."
        for field in CustomField.objects.all():
            self.fields["extra_" + field.key] = forms.CharField(
                label=field.label,
                required=False,
                initial=self.instance.extra.get(field.key, ""),
            )

    def clean(self):
        data = super().clean()
        from .models import StocktakeItem

        if self.instance.pk and (
            Line.objects.filter(product=self.instance).exists()
            or StocktakeItem.objects.filter(product=self.instance).exists()
        ):
            original = Product.objects.get(pk=self.instance.pk)
            for key in ["sku", "unit"]:
                if key in data and data[key] != getattr(original, key):
                    self.add_error(
                        key,
                        "Hàng đã có chứng từ: giữ nguyên mã và đơn vị tính để bảo toàn thẻ kho. Nếu khác quy cách, tạo mã hàng mới.",
                    )
        return data

    def save(self, commit=True):
        self.instance.extra = {
            **self.instance.extra,
            **{
                f.key: self.cleaned_data.get("extra_" + f.key, "")
                for f in CustomField.objects.all()
            },
        }
        return super().save(commit=commit)


class ProductPhotoForm(forms.Form):
    image = forms.FileField(
        label="Ảnh hàng hóa (nếu có)",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"accept": "image/jpeg,image/png,image/webp"}
        ),
    )
    caption = forms.CharField(label="Mô tả ảnh", max_length=150, required=False)

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if upload:
            from .media import validate_upload

            self.validated_image = validate_upload(upload, photo=True)
        return upload


class ReceiptAttachmentForm(forms.ModelForm):
    file = forms.FileField(
        label="Tệp PDF, XML hoặc ảnh hóa đơn",
        widget=forms.ClearableFileInput(
            attrs={"accept": ".pdf,.xml,.jpg,.jpeg,.png,.webp"}
        ),
    )

    class Meta:
        from .models import ReceiptAttachment

        model = ReceiptAttachment
        fields = ["category", "invoice_number", "invoice_date"]
        widgets = {
            "invoice_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
        }

    def clean_invoice_date(self):
        day = self.cleaned_data.get("invoice_date")
        if day and day > timezone.localdate():
            raise forms.ValidationError("Ngày hóa đơn không được ở tương lai.")
        return day

    def clean_file(self):
        from .media import validate_upload

        upload = self.cleaned_data["file"]
        self.validated_file = validate_upload(upload)
        return upload


class StocktakeCountForm(forms.Form):
    code = forms.CharField(max_length=500)
    mode = forms.ChoiceField(
        choices=[("SET", "Ghi tổng số đếm"), ("ADD", "Quét cộng 1")]
    )
    quantity = forms.DecimalField(
        max_digits=16, decimal_places=3, min_value=0, required=False
    )
    unit_price = forms.DecimalField(
        max_digits=18, decimal_places=4, min_value=0, required=False
    )
    note = forms.CharField(max_length=250, required=False)
    request_id = forms.UUIDField()
    revision = forms.IntegerField(min_value=1)

    def clean(self):
        data = super().clean()
        if data.get("mode") == "SET" and data.get("quantity") is None:
            self.add_error(
                "quantity", "Nhập tổng số thực đếm; nhập 0 khi xác nhận không có hàng."
            )
        return data


class ReceiptImportForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [*DOCUMENT_DETAILS, "note"]

    warehouse = forms.ModelChoiceField(queryset=None, label="Kho nhận hàng")
    file = forms.FileField(
        label="File Excel .xlsx",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )
    note = forms.CharField(
        label="Diễn giải", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        configure_document_details(self, "IN")
        self.fields["business_date"].initial = timezone.localdate
        self.fields["warehouse"].queryset = warehouses_for(user)

    def clean(self):
        data = super().clean()
        data["business_date"] = data.get("business_date") or timezone.localdate()
        if not self.errors:
            validate_document(
                Document(
                    kind="IN",
                    destination=data["warehouse"],
                    **{k: data.get(k) for k in self.Meta.fields},
                )
            )
        return data

    def clean_file(self):
        file = self.cleaned_data["file"]
        if not file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError(
                "Chỉ nhận file .xlsx; hãy lưu lại từ Excel nếu đang dùng .xls."
            )
        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("File tối đa 5 MB.")
        return file


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["code", "name", "address", "members", "managers", "issue_approvers"]
        widgets = {
            name: forms.CheckboxSelectMultiple()
            for name in ["members", "managers", "issue_approvers"]
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .access import is_admin

        if not is_admin(actor):
            for field in ["members", "managers", "issue_approvers"]:
                self.fields.pop(field)
            return
        for name in ["members", "managers", "issue_approvers"]:
            self.fields[name].queryset = (
                get_user_model().objects.filter(is_active=True).order_by("username")
            )
        self.fields[
            "members"
        ].help_text = "Phạm vi kho. Chỉ thao tác được các chức năng admin đã cấp trong hồ sơ nhân viên."
        self.fields[
            "managers"
        ].help_text = "Xác nhận nhập và nhận hàng liên kho. Duyệt kiểm kê / điều chỉnh là quyền Tổng giám đốc được cấp riêng."
        self.fields[
            "issue_approvers"
        ].help_text = "Được duyệt xuất, chuyển đi, cho mượn và trả hàng tại kho này."


class EmployeeForm(forms.ModelForm):
    from .access import FUNCTION_CHOICES

    function_permissions = forms.MultipleChoiceField(
        label="Quyền từng chức năng",
        choices=FUNCTION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    access_revision = forms.IntegerField(
        required=False, initial=0, min_value=0, widget=forms.HiddenInput()
    )
    password = forms.CharField(
        label="Mật khẩu",
        required=False,
        strip=False,
        widget=forms.PasswordInput(render_value=False),
    )
    access_warehouses = forms.ModelMultipleChoiceField(
        queryset=Warehouse.objects.order_by("code"),
        label="Kho được truy cập",
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    managed_warehouses = forms.ModelMultipleChoiceField(
        queryset=Warehouse.objects.order_by("code"),
        label="Kho được duyệt nhập",
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    issue_warehouses = forms.ModelMultipleChoiceField(
        queryset=Warehouse.objects.order_by("code"),
        label="Kho được duyệt xuất",
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = get_user_model()
        fields = ["username", "first_name", "email", "is_active"]
        labels = {
            "first_name": "Họ và tên",
            "last_name": "Họ",
            "groups": "Vai trò nghiệp vụ",
            "is_active": "Cho phép đăng nhập",
        }
        widgets = {"groups": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields["username"].label = "Mã nhân viên / Tên đăng nhập"
        self.fields["password"].required = not self.instance.pk
        self.fields[
            "password"
        ].help_text = "Mật khẩu tự chọn, không bắt buộc độ dài hay tổ hợp ký tự. Khi sửa, để trống để giữ mật khẩu hiện tại."
        if self.instance.pk:
            from .models import FunctionAccess
            from .access import function_codes

            access = FunctionAccess.objects.filter(user=self.instance).first()
            self.initial["function_permissions"] = sorted(function_codes(self.instance))
            self.initial["access_revision"] = access.revision if access else 0
            if self.instance.is_superuser:
                self.fields["function_permissions"].disabled = True
            self.initial["first_name"] = self.instance.get_full_name()
            for field, relation in [
                ("access_warehouses", "warehouses"),
                ("managed_warehouses", "managed_warehouses"),
                ("issue_warehouses", "issue_warehouses"),
            ]:
                self.initial[field] = getattr(self.instance, relation).all()

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        from .access import is_admin, normalize_permissions
        from .models import FunctionAccess
        from django.db import transaction
        from django.core.exceptions import PermissionDenied, ValidationError

        if not is_admin(self.actor):
            raise PermissionDenied("Chỉ admin được lưu tài khoản và phân quyền.")
        user = super().save(commit=False)
        user.last_name = ""
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        if commit:
            with transaction.atomic():
                if user.pk:
                    get_user_model().objects.select_for_update().get(pk=user.pk)
                access = (
                    FunctionAccess.objects.select_for_update()
                    .filter(user_id=user.pk)
                    .first()
                    if user.pk
                    else None
                )
                if (access.revision if access else 0) != (
                    self.cleaned_data.get("access_revision") or 0
                ):
                    raise ValidationError(
                        "Quyền hoặc thông tin nhân viên đã được lưu ở cửa sổ khác. Tải lại trước khi chỉnh, không ghi đè bản mới."
                    )
                user.save()
                self.save_m2m()
                user.warehouses.set(self.cleaned_data["access_warehouses"])
                user.managed_warehouses.set(self.cleaned_data["managed_warehouses"])
                user.issue_warehouses.set(self.cleaned_data["issue_warehouses"])
                FunctionAccess.objects.update_or_create(
                    user=user,
                    defaults={
                        "permissions": normalize_permissions(
                            self.cleaned_data["function_permissions"]
                        ),
                        "updated_by": self.actor,
                        "revision": (access.revision if access else 0) + 1,
                    },
                )
        return user

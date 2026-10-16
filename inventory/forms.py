from django import forms
from django.forms import formset_factory, BaseFormSet
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from .models import Document, Product, CustomField, Warehouse
from .services import warehouses_for, documents_for, validate_document


class DocumentForm(forms.ModelForm):
    submission_key = forms.UUIDField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Document
        fields = ["kind", "source", "destination", "loan", "note"]
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
        self.fixed_kind = fixed_kind
        self.operation = fixed_kind or (
            self.data.get("kind")
            if self.is_bound
            else self.initial.get("kind", self.instance.kind or "IN")
        )
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
                if str(loan_id).isdigit()
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
        if self.fixed_kind and data.get("kind") != self.fixed_kind:
            raise forms.ValidationError("Loại phiếu không khớp với nghiệp vụ đang mở.")
        if not self.errors:
            validate_document(Document(**{k: data.get(k) for k in self.Meta.fields}))
        return data


class LineForm(forms.Form):
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
            if self.kind not in ["COUNT", "ADJUST"] and q <= 0:
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
        fields = ["sku", "name", "unit", "minimum"]

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

    def save(self, commit=True):
        self.instance.extra = {
            **self.instance.extra,
            **{
                f.key: self.cleaned_data.get("extra_" + f.key, "")
                for f in CustomField.objects.all()
            },
        }
        return super().save(commit=commit)


class ReceiptImportForm(forms.Form):
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
        self.fields["warehouse"].queryset = warehouses_for(user)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["members", "managers", "issue_approvers"]:
            self.fields[name].queryset = (
                get_user_model().objects.filter(is_active=True).order_by("username")
            )
        self.fields[
            "members"
        ].help_text = "Được xem kho và lập phiếu nếu có vai trò nhân viên kho."
        self.fields[
            "managers"
        ].help_text = "Xác nhận nhập, kiểm kê, điều chỉnh và nhận hàng liên kho."
        self.fields[
            "issue_approvers"
        ].help_text = "Được duyệt xuất, chuyển đi, cho mượn và trả hàng tại kho này."


class EmployeeForm(forms.ModelForm):
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
        fields = ["username", "first_name", "email", "groups", "is_active"]
        labels = {
            "first_name": "Họ và tên",
            "last_name": "Họ",
            "groups": "Vai trò nghiệp vụ",
            "is_active": "Cho phép đăng nhập",
        }
        widgets = {"groups": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Mã nhân viên / Tên đăng nhập"
        self.fields["groups"].queryset = Group.objects.order_by("name")
        self.fields["password"].required = not self.instance.pk
        self.fields[
            "password"
        ].help_text = "Mật khẩu tự chọn, không bắt buộc độ dài hay tổ hợp ký tự. Khi sửa, để trống để giữ mật khẩu hiện tại."
        if self.instance.pk:
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
        user = super().save(commit=False)
        user.last_name = ""
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_m2m()
            user.warehouses.set(self.cleaned_data["access_warehouses"])
            user.managed_warehouses.set(self.cleaned_data["managed_warehouses"])
            user.issue_warehouses.set(self.cleaned_data["issue_warehouses"])
        return user

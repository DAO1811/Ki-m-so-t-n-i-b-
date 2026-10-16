from django import forms
from django.forms import formset_factory
from .models import Document, Product, CustomField
from .services import warehouses_for, documents_for, validate_document


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["kind", "source", "destination", "loan", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["source", "destination"]:
            self.fields[name].queryset = warehouses_for(user)
        if not self.is_bound or self.data.get("kind", self.instance.kind) in [
            "TRANSFER",
            "LOAN",
            "RETURN",
        ]:
            from .models import Warehouse

            self.fields["destination"].queryset = Warehouse.objects.all()
        self.fields["loan"].queryset = documents_for(user).filter(
            kind="LOAN", status="POSTED"
        )

    def clean(self):
        data = super().clean()
        if not self.errors:
            doc = Document(**{k: data.get(k) for k in self.Meta.fields})
            validate_document(doc)
        return data


class LineForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label="Hàng hóa")
    quantity = forms.DecimalField(max_digits=16, decimal_places=3, label="Số lượng")
    unit_price = forms.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=0,
        required=False,
        label="Đơn giá nhập (VNĐ)",
    )


LineFormSet = formset_factory(
    LineForm, extra=5, max_num=50, validate_max=True, min_num=1, validate_min=True
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["sku", "name", "unit", "minimum"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

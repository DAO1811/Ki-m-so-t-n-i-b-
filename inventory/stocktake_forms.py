from django import forms
from django.forms import BaseModelFormSet, modelformset_factory

from .models import StocktakeItem


class PaperCountForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = StocktakeItem
        fields = ["counted_quantity", "unit_price", "note"]
        widgets = {
            "counted_quantity": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": "0.001",
                    "placeholder": "Chưa đếm",
                    "inputmode": "decimal",
                }
            ),
            "unit_price": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": "0.0001",
                    "placeholder": "Theo giá vốn",
                    "inputmode": "decimal",
                }
            ),
            "note": forms.TextInput(
                attrs={"placeholder": "Tình trạng / lý do chênh lệch"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["revision"] = self.instance.revision

    def clean(self):
        data = super().clean()
        if data.get("counted_quantity") is None and (
            self.instance.counted_quantity is not None
            or data.get("unit_price") is not None
            or data.get("note")
        ):
            self.add_error(
                "counted_quantity",
                "Nhập số thực đếm; xác nhận 0 nếu không tìm thấy hàng. Không xóa số đã ghi.",
            )
        return data


class PaperCountBaseFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        ids = [
            form.cleaned_data["id"].pk
            for form in self.forms
            if form.cleaned_data.get("id")
        ]
        if len(ids) != len(set(ids)):
            raise forms.ValidationError(
                "Có dòng hàng bị lặp. Tải lại bảng trước khi nhập số kiểm đếm."
            )


PaperCountFormSet = modelformset_factory(
    StocktakeItem,
    form=PaperCountForm,
    formset=PaperCountBaseFormSet,
    extra=0,
    max_num=25,
    absolute_max=25,
    validate_max=True,
)
